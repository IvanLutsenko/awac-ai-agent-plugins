import importlib.util
import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT / "plugins" / "combined-review" / "scripts" / "post-gitlab-mr-threads.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("post_gitlab_mr_threads", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ANALYZED_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CURRENT_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

THREADS = [{"path": "foo.py", "line": 3, "body": "nit"}]


def make_discussion(disc_id, path, line, author, body="see MR", position=True):
    note = {"author": {"username": author}, "body": body}
    note["position"] = {"new_path": path, "new_line": line} if position else None
    return {"id": disc_id, "notes": [note]}


def make_glab_api(head_sha, discussions=()):
    """Fake glab_api: GET returns diff_refs / user / discussions, POST 'succeeds'."""

    def fake(path, method=None, headers=None, input_file=None, paginate=False):
        if method == "POST":
            return (
                json.dumps(
                    {
                        "id": "1234567890abcdef",
                        "notes": [
                            {"type": "DiffNote", "position": {"new_line": 3}}
                        ],
                    }
                ),
                "",
            )
        if path == "user":
            return json.dumps({"username": "me"}), ""
        if "/discussions" in path:
            return json.dumps(list(discussions)), ""
        return (
            json.dumps(
                {
                    "diff_refs": {
                        "base_sha": "base",
                        "start_sha": "start",
                        "head_sha": head_sha,
                    }
                }
            ),
            "",
        )

    return fake


class PostGitlabMrThreadsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.threads_file = Path(self.temp_dir.name) / "threads.json"
        self.threads_file.write_text(json.dumps(THREADS), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_head_mismatch_posts_nothing_and_exits_nonzero(self):
        module = load_module()
        fake_glab_api = make_glab_api(CURRENT_SHA)

        with patch.object(module, "glab_api", side_effect=fake_glab_api) as mock_api:
            with patch(
                "sys.argv",
                [
                    "post-gitlab-mr-threads.py",
                    "--repo",
                    "group/project",
                    "--mr",
                    "1",
                    "--threads",
                    str(self.threads_file),
                    "--expected-head",
                    ANALYZED_SHA,
                ],
            ):
                with self.assertRaises(SystemExit) as cm:
                    module.main()

        self.assertNotEqual(cm.exception.code, 0)
        self.assertIsNotNone(cm.exception.code)
        message = str(cm.exception.code)
        self.assertIn(ANALYZED_SHA, message)
        self.assertIn(CURRENT_SHA, message)

        # Only the diff_refs GET happened; no POST was ever sent.
        mock_api.assert_called_once()
        for call in mock_api.call_args_list:
            self.assertNotEqual(call.kwargs.get("method"), "POST")

    def test_head_match_posts_threads_normally(self):
        module = load_module()
        fake_glab_api = make_glab_api(ANALYZED_SHA)

        with patch.object(module, "glab_api", side_effect=fake_glab_api) as mock_api:
            with patch(
                "sys.argv",
                [
                    "post-gitlab-mr-threads.py",
                    "--repo",
                    "group/project",
                    "--mr",
                    "1",
                    "--threads",
                    str(self.threads_file),
                    "--expected-head",
                    ANALYZED_SHA,
                ],
            ):
                with self.assertRaises(SystemExit) as cm:
                    module.main()

        self.assertEqual(cm.exception.code, 0)

        post_calls = [
            call for call in mock_api.call_args_list if call.kwargs.get("method") == "POST"
        ]
        self.assertEqual(len(post_calls), 1)

    def test_own_thread_on_the_same_line_is_not_posted_again(self):
        module = load_module()
        existing = [make_discussion("d1", "foo.py", 3, "me")]
        fake_glab_api = make_glab_api(ANALYZED_SHA, existing)

        with patch.object(module, "glab_api", side_effect=fake_glab_api) as mock_api:
            with patch(
                "sys.argv",
                [
                    "post-gitlab-mr-threads.py",
                    "--repo",
                    "group/project",
                    "--mr",
                    "1",
                    "--threads",
                    str(self.threads_file),
                    "--expected-head",
                    ANALYZED_SHA,
                ],
            ):
                with self.assertRaises(SystemExit) as cm:
                    module.main()

        # A dedup skip is not a failure.
        self.assertEqual(cm.exception.code, 0)
        post_calls = [
            call for call in mock_api.call_args_list if call.kwargs.get("method") == "POST"
        ]
        self.assertEqual(post_calls, [])


    def test_second_page_of_discussions_is_read(self):
        module = load_module()
        # `glab api --paginate` concatenates one JSON array per page.
        page1 = json.dumps([make_discussion("d1", "other.py", 10, "someone")])
        page2 = json.dumps([make_discussion("d2", "foo.py", 3, "someone")])
        base = make_glab_api(ANALYZED_SHA)

        def fake(path, method=None, headers=None, input_file=None, paginate=False):
            if "/discussions" in path and method != "POST":
                return page1 + "\n" + page2, ""
            return base(path, method, headers, input_file, paginate)

        with patch.object(module, "glab_api", side_effect=fake) as mock_api:
            with patch(
                "sys.argv",
                [
                    "post-gitlab-mr-threads.py",
                    "--repo", "group/project", "--mr", "1",
                    "--threads", str(self.threads_file),
                    "--expected-head", ANALYZED_SHA,
                ],
            ):
                with self.assertRaises(SystemExit) as cm:
                    module.main()

        # The match lives on page 2: without multi-page decoding it would be posted again.
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(
            [c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"], []
        )

    def test_one_failed_thread_makes_the_exit_code_nonzero(self):
        module = load_module()
        self.threads_file.write_text(
            json.dumps(
                [
                    {"path": "foo.py", "line": 3, "body": "nit"},
                    {"path": "bar.py", "line": 9, "body": "nit"},
                ]
            ),
            encoding="utf-8",
        )
        base = make_glab_api(ANALYZED_SHA)
        seen = []

        def fake(path, method=None, headers=None, input_file=None, paginate=False):
            if method == "POST":
                sent = json.loads(Path(input_file).read_text())
                seen.append(sent)
                if sent["position"]["new_path"] == "bar.py":
                    return "", "400 Bad Request: line not part of the diff"
            return base(path, method, headers, input_file, paginate)

        with patch.object(module, "glab_api", side_effect=fake):
            with patch(
                "sys.argv",
                [
                    "post-gitlab-mr-threads.py",
                    "--repo", "group/project", "--mr", "1",
                    "--threads", str(self.threads_file),
                    "--expected-head", ANALYZED_SHA,
                ],
            ):
                with self.assertRaises(SystemExit) as cm:
                    module.main()

        # One posted, one rejected -> partial success is still a failure.
        self.assertNotEqual(cm.exception.code, 0)
        self.assertEqual(len(seen), 2)

    def test_paginated_call_that_fails_midway_aborts(self):
        module = load_module()
        # Page 1 arrived, page 2 died: stdout is valid JSON but incomplete.
        completed = SimpleNamespace(
            stdout=json.dumps([make_discussion("d1", "foo.py", 3, "me")]),
            stderr="429 Too Many Requests",
            returncode=1,
        )
        with patch.object(module.subprocess, "run", return_value=completed):
            with self.assertRaises(SystemExit) as cm:
                module.glab_api("projects/1/merge_requests/1/discussions", paginate=True)

        # A partial page read as complete is what makes the dedup post duplicates.
        self.assertNotEqual(cm.exception.code, 0)
        self.assertIn("429", str(cm.exception.code))

    def test_unreadable_discussions_abort_instead_of_posting(self):
        module = load_module()
        base = make_glab_api(ANALYZED_SHA)

        def fake(path, method=None, headers=None, input_file=None, paginate=False):
            if "/discussions" in path and method != "POST":
                return "", "401 Unauthorized"       # glab failed: empty stdout
            return base(path, method, headers, input_file, paginate)

        with patch.object(module, "glab_api", side_effect=fake) as mock_api:
            with patch(
                "sys.argv",
                [
                    "post-gitlab-mr-threads.py",
                    "--repo",
                    "group/project",
                    "--mr",
                    "1",
                    "--threads",
                    str(self.threads_file),
                    "--expected-head",
                    ANALYZED_SHA,
                ],
            ):
                with self.assertRaises(SystemExit) as cm:
                    module.main()

        # Can't tell own threads from new lines -> abort, never post blind duplicates.
        self.assertNotEqual(cm.exception.code, 0)
        post_calls = [
            call for call in mock_api.call_args_list if call.kwargs.get("method") == "POST"
        ]
        self.assertEqual(post_calls, [])


class MatchThreadTest(unittest.TestCase):
    def match(self, discussions, path="foo.py", line=3):
        return load_module().match_thread(discussions, path, line, "me")

    def test_no_threads_at_all(self):
        self.assertEqual(self.match([]), ("post", None, None))

    def test_own_thread_on_the_line(self):
        d = make_discussion("d1", "foo.py", 3, "me")
        self.assertEqual(self.match([d]), ("mine", "d1", None))

    def test_other_thread_on_the_line(self):
        d = make_discussion("d1", "foo.py", 3, "reviewer")
        self.assertEqual(self.match([d]), ("theirs", "d1", None))

    def test_other_thread_names_a_ticket(self):
        d = make_discussion("d1", "foo.py", 3, "reviewer", body="known, ABC-123 covers it")
        self.assertEqual(self.match([d]), ("theirs", "d1", "ABC-123"))

    def test_standard_name_is_not_a_ticket(self):
        d = make_discussion("d1", "foo.py", 3, "reviewer", body="decode as UTF-8, then SHA-256 it")
        self.assertEqual(self.match([d]), ("theirs", "d1", None))

    def test_thread_without_position_never_matches(self):
        d = make_discussion("d1", "foo.py", 3, "reviewer", position=False)
        self.assertEqual(self.match([d]), ("post", None, None))

    def test_same_line_other_path(self):
        d = make_discussion("d1", "bar.py", 3, "me")
        self.assertEqual(self.match([d]), ("post", None, None))

    def test_same_path_other_line(self):
        d = make_discussion("d1", "foo.py", 4, "me")
        self.assertEqual(self.match([d]), ("post", None, None))


if __name__ == "__main__":
    unittest.main()
