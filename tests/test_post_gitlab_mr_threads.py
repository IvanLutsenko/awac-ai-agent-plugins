import importlib.util
import json
import tempfile
import unittest
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


def make_glab_api(head_sha):
    """Fake glab_api: GET returns diff_refs with head_sha, POST 'succeeds'."""

    def fake(path, method=None, headers=None, input_file=None):
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


if __name__ == "__main__":
    unittest.main()
