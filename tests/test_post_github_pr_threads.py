import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT / "plugins" / "combined-review" / "scripts" / "post-github-pr-threads.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("post_github_pr_threads", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ANALYZED_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CURRENT_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

THREADS = [{"path": "foo.py", "line": 3, "body": "nit"}]


def make_comment(cid, path, line, author, body="see PR", outdated=False):
    """A thread-starting review comment. Outdated ones report `line: null`."""
    return {
        "id": cid,
        "path": path,
        "line": None if outdated else line,
        "original_line": line,
        "user": {"login": author},
        "body": body,
    }


def make_gh_api(head_sha, comments=(), comments_raw=None, sent_payloads=None):
    """Fake gh_api: GET returns head.sha / user / review comments, POST 'succeeds'.

    The payload file is deleted right after the call, so what was sent is captured here.
    """

    def fake(path, method=None, headers=None, input_file=None, paginate=False):
        if method == "POST":
            sent = json.loads(Path(input_file).read_text())
            if sent_payloads is not None:
                sent_payloads.append(sent)
            return (
                json.dumps(
                    {"id": 111, "path": sent["path"], "line": sent["line"]}
                ),
                "",
            )
        if path == "user":
            return json.dumps({"login": "me"}), ""
        if "/comments" in path:
            if comments_raw is not None:
                return comments_raw, ""
            return json.dumps(list(comments)), ""
        return json.dumps({"head": {"sha": head_sha}}), ""

    return fake


class PostGithubPrThreadsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.threads_file = Path(self.temp_dir.name) / "threads.json"
        self.write_threads(THREADS)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_threads(self, threads):
        self.threads_file.write_text(json.dumps(threads), encoding="utf-8")

    def run_main(self, module):
        with patch(
            "sys.argv",
            [
                "post-github-pr-threads.py",
                "--repo",
                "owner/repo",
                "--pr",
                "1",
                "--threads",
                str(self.threads_file),
                "--expected-head",
                ANALYZED_SHA,
            ],
        ):
            with self.assertRaises(SystemExit) as cm:
                module.main()
        return cm.exception

    def test_head_mismatch_posts_nothing_and_exits_nonzero(self):
        module = load_module()
        with patch.object(module, "gh_api", side_effect=make_gh_api(CURRENT_SHA)) as mock_api:
            exc = self.run_main(module)

        self.assertNotEqual(exc.code, 0)
        message = str(exc.code)
        self.assertIn(ANALYZED_SHA, message)
        self.assertIn(CURRENT_SHA, message)

        # Only the pull GET happened; no POST was ever sent.
        mock_api.assert_called_once()
        for call in mock_api.call_args_list:
            self.assertNotEqual(call.kwargs.get("method"), "POST")

    def test_head_match_posts_threads_normally(self):
        module = load_module()
        sent_payloads = []
        fake = make_gh_api(ANALYZED_SHA, sent_payloads=sent_payloads)
        with patch.object(module, "gh_api", side_effect=fake) as mock_api:
            exc = self.run_main(module)

        self.assertEqual(exc.code, 0)
        posts = [c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"]
        self.assertEqual(len(posts), 1)
        sent = sent_payloads[0]
        # The line goes as an integer on the RIGHT side, pinned to the verified head.
        self.assertEqual(sent["line"], 3)
        self.assertEqual(sent["side"], "RIGHT")
        self.assertEqual(sent["commit_id"], ANALYZED_SHA)
        self.assertNotIn("position", sent)

    def test_own_thread_on_the_same_line_is_not_posted_again(self):
        module = load_module()
        existing = [make_comment(7, "foo.py", 3, "me")]
        with patch.object(
            module, "gh_api", side_effect=make_gh_api(ANALYZED_SHA, existing)
        ) as mock_api:
            exc = self.run_main(module)

        # A dedup skip is not a failure.
        self.assertEqual(exc.code, 0)
        self.assertEqual(
            [c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"], []
        )

    def test_outdated_own_thread_still_dedups_via_original_line(self):
        module = load_module()
        existing = [make_comment(7, "foo.py", 3, "me", outdated=True)]
        with patch.object(
            module, "gh_api", side_effect=make_gh_api(ANALYZED_SHA, existing)
        ) as mock_api:
            exc = self.run_main(module)

        self.assertEqual(exc.code, 0)
        self.assertEqual(
            [c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"], []
        )

    def test_second_page_of_comments_is_read(self):
        module = load_module()
        # `gh api --paginate` concatenates one JSON array per page.
        page1 = json.dumps([make_comment(1, "other.py", 10, "someone")])
        page2 = json.dumps([make_comment(2, "foo.py", 3, "someone", body="ABC-123 known")])
        with patch.object(
            module,
            "gh_api",
            side_effect=make_gh_api(ANALYZED_SHA, comments_raw=page1 + "\n" + page2),
        ) as mock_api:
            exc = self.run_main(module)

        # The match lives on page 2: without multi-page decoding it would be posted again.
        self.assertEqual(exc.code, 0)
        self.assertEqual(
            [c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"], []
        )

    def test_one_failed_thread_makes_the_exit_code_nonzero(self):
        module = load_module()
        self.write_threads(
            [
                {"path": "foo.py", "line": 3, "body": "nit"},
                {"path": "bar.py", "line": 9, "body": "nit"},
            ]
        )
        base = make_gh_api(ANALYZED_SHA)

        def fake(path, method=None, headers=None, input_file=None, paginate=False):
            if method == "POST":
                sent = json.loads(Path(input_file).read_text())
                if sent["path"] == "bar.py":
                    return "", "422 Unprocessable Entity: line must be part of the diff"
            return base(path, method, headers, input_file, paginate)

        with patch.object(module, "gh_api", side_effect=fake) as mock_api:
            exc = self.run_main(module)

        # One posted, one rejected -> partial success is still a failure.
        self.assertNotEqual(exc.code, 0)
        self.assertEqual(
            len([c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"]), 2
        )

    def test_unreadable_comments_abort_instead_of_posting(self):
        module = load_module()
        base = make_gh_api(ANALYZED_SHA)

        def fake(path, method=None, headers=None, input_file=None, paginate=False):
            if "/comments" in path and method != "POST":
                return "", "401 Unauthorized"       # gh failed: empty stdout
            return base(path, method, headers, input_file, paginate)

        with patch.object(module, "gh_api", side_effect=fake) as mock_api:
            exc = self.run_main(module)

        # Can't tell own threads from new lines -> abort, never post blind duplicates.
        self.assertNotEqual(exc.code, 0)
        self.assertEqual(
            [c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"], []
        )


if __name__ == "__main__":
    unittest.main()
