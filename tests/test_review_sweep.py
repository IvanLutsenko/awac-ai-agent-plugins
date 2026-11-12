"""review-sweep.py: what a PR/MR needs is decided from what was reviewed, not from who typed last."""
import importlib.util
import stat
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "plugins/combined-review/scripts/review-sweep.py"


def load_module():
    spec = importlib.util.spec_from_file_location("review_sweep", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load_module()


def pr(**kw):
    base = {"draft": False, "files": 5, "head": "h2", "ball": "mine", "reviewed_sha": None,
            "open_threads": 0, "answered": 0, "commits": [{"sha": "h1", "parents": 1}, {"sha": "h2", "parents": 1}]}
    return {**base, **kw}


class ClassifyTest(unittest.TestCase):
    def check(self, bucket, steps, **kw):
        got = M.classify(pr(**kw))
        self.assertEqual((got[0], got[2]), (bucket, steps), got[1])

    def test_never_looked(self):
        self.check("review", ["review"])

    def test_draft_and_large_are_held(self):
        self.check("hold", [], draft=True)
        self.check("hold", [], files=M.LARGE + 1)

    def test_new_commits_after_my_review_are_a_delta(self):
        self.check("delta", ["review --since h1"], reviewed_sha="h1")

    def test_delta_rechecks_my_threads_first(self):
        self.check("delta", ["rereview", "review --since h1"], reviewed_sha="h1", open_threads=2)

    def test_approval_does_not_cover_commits_pushed_after_it(self):
        self.check("delta", ["review --since h1"], reviewed_sha="h1", ball="done")

    def test_only_merges_after_my_review(self):
        commits = [{"sha": "h1", "parents": 1}, {"sha": "h2", "parents": 2}]
        self.check("merge_only", [], reviewed_sha="h1", commits=commits)
        self.check("rereview", ["rereview"], reviewed_sha="h1", commits=commits, open_threads=1)

    def test_reviewed_head_gone_means_full_review(self):
        self.check("review", ["review"], reviewed_sha="gone")
        self.check("review", ["rereview", "review"], reviewed_sha="gone", open_threads=1)

    def test_waiting_on_author(self):
        self.check("waiting", [], ball="author", reviewed_sha="h2", open_threads=3)

    def test_push_while_waiting_on_author_is_still_reviewed(self):
        """GitLab keeps `requested_changes` after a push; unread code is not 'waiting'."""
        self.check("delta", ["rereview", "review --since h1"], ball="author", reviewed_sha="h1", open_threads=1)

    def test_reply_while_waiting_is_read(self):
        self.check("rereview", ["rereview"], ball="author", reviewed_sha="h2", open_threads=3, answered=1)

    def test_approved_at_head_is_done_but_listed(self):
        self.check("done", [], ball="done", reviewed_sha="h2")
        self.check("rereview", ["rereview"], ball="done", reviewed_sha="h2", open_threads=1, answered=1)

    def test_rerequested_without_changes(self):
        self.check("rereview", ["rereview"], reviewed_sha="h2", open_threads=1)
        self.check("review", ["review"], reviewed_sha="h2")


def thread(opener, last, sha="h1", at="2026-01-01", resolved=False):
    return {"isResolved": resolved,
            "first": {"nodes": [{"author": {"login": opener}, "createdAt": at, "originalCommit": {"oid": sha}}]},
            "last": {"nodes": [{"author": {"login": last}}]}}


class GithubTest(unittest.TestCase):
    PR = {"isDraft": False, "changedFiles": 3, "headRefOid": "h2"}
    COMMITS = [{"sha": "h1", "parents": [{}]}, {"sha": "h2", "parents": [{}]}]

    def norm(self, reviews=(), threads=(), requested=False):
        return M.github_pr("me", self.PR, requested, list(reviews), list(threads), self.COMMITS)

    def test_a_reply_after_a_push_does_not_move_the_reviewed_head(self):
        """Thread opened on h1, author pushed h2, I replied in the thread: h2 is still unreviewed."""
        got = self.norm(threads=[thread("me", "me", sha="h1")])
        self.assertEqual(got["reviewed_sha"], "h1")
        self.assertEqual(M.classify(got)[2], ["rereview", "review --since h1"])

    def test_someone_elses_thread_is_not_mine(self):
        got = self.norm(threads=[thread("other", "me")])
        self.assertEqual((got["open_threads"], got["reviewed_sha"]), (0, None))

    def test_changes_requested_at_head_waits_on_author(self):
        got = self.norm(reviews=[{"user": {"login": "me"}, "state": "CHANGES_REQUESTED", "commit_id": "h2",
                                  "submitted_at": "2026-01-02"}], threads=[thread("me", "me", sha="h2")])
        self.assertEqual(M.classify(got)[0], "waiting")

    def test_review_with_a_summary_counts_and_a_bare_reply_does_not(self):
        review = {"user": {"login": "me"}, "state": "COMMENTED", "commit_id": "h2", "submitted_at": "2026-01-05T00:00:00Z"}
        self.assertEqual(self.norm(reviews=[{**review, "body": "looked through"}])["reviewed_sha"], "h2")
        self.assertIsNone(self.norm(reviews=[{**review, "body": ""}])["reviewed_sha"])

    def test_newest_compares_times_not_strings(self):
        """'...:00Z' sorts after '...:00.405Z' as text although it is earlier."""
        self.assertEqual(M.newest([("2026-01-01T10:00:00Z", "old"), ("2026-01-01T10:00:00.405Z", "new")]), "new")

    def test_deleted_account_does_not_crash(self):
        t = thread("me", "ghost")
        t["last"]["nodes"][0]["author"] = None
        self.assertEqual(self.norm(threads=[t])["answered"], 1)


class GitlabTest(unittest.TestCase):
    MR = {"draft": False, "changes_count": "1000+", "sha": "h2"}

    def note(self, who, body="x", at="2026-01-02", system=False, **kw):
        return {"author": {"username": who}, "body": body, "created_at": at, "system": system, **kw}

    def test_approval_head_is_the_version_that_existed_then(self):
        versions = [{"head_commit_sha": "h2", "created_at": "2026-01-03"},
                    {"head_commit_sha": "h1", "created_at": "2026-01-01"}]
        discussions = [{"notes": [self.note("me", "approved this merge request", system=True)]}]
        commits = [{"id": "h2", "parent_ids": ["a"]}, {"id": "h1", "parent_ids": ["a"]}]  # newest first
        got = M.gitlab_mr("me", {**self.MR, "changes_count": "4"}, [], "unapproved", discussions, versions, commits)
        self.assertEqual(got["reviewed_sha"], "h1")
        self.assertEqual(M.classify(got)[2], ["review --since h1"])

    def test_requested_changes_waits_and_counts_replies(self):
        mine = self.note("me", resolvable=True, resolved=False, position={"head_sha": "h2"})
        discussions = [{"notes": [mine, self.note("author")]}]
        got = M.gitlab_mr("me", {**self.MR, "changes_count": "4"}, [], "requested_changes", discussions, [], [])
        self.assertEqual((got["ball"], got["open_threads"], got["answered"]), ("author", 1, 1))

    def test_changes_count_with_a_plus_is_large(self):
        got = M.gitlab_mr("me", self.MR, [], "unreviewed", [], [], [])
        self.assertEqual(M.classify(got)[0], "hold")


class RunTest(unittest.TestCase):
    def run_with(self, script):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "claude"
            fake.write_text(f"#!/bin/sh\n{script}\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            item = {"number": 7, "ref": "7", "head": "h", "steps": ["/combined-review:review 7"]}
            return M.run_item(item, Path(d), 20, str(fake))["results"][0]["status"]

    def test_report_on_stdout_is_ok(self):
        self.assertEqual(self.run_with('echo "## Code Review"'), "ok")

    def test_crash_is_not_no_findings(self):
        self.assertTrue(self.run_with("echo partial; exit 3").startswith("failed"))

    def test_pane_command_quotes_what_the_forge_sent(self):
        item = {"url": "https://x/1'; rm -rf ~ #", "steps": ["/combined-review:rereview !1", "/combined-review:review !1 --since ab"]}
        cmd = M.pane_command(item)
        self.assertIn(item["url"] + ";", M.shlex.split(cmd))  # one token: the quote in it closed nothing
        self.assertTrue(cmd.endswith("claude '/combined-review:rereview !1'"))
        self.assertIn("then: /combined-review:review !1 --since ab", cmd)

    def test_exit_zero_without_a_report_is_not_a_review(self):
        self.assertTrue(self.run_with('echo "Cannot check out pr/7 - stopping."').startswith("failed"))

    def test_empty_output_is_not_no_findings(self):
        self.assertTrue(self.run_with("exit 0").startswith("failed"))


if __name__ == "__main__":
    unittest.main()
