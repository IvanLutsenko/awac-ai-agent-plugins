import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_ROOT))

from helpers import (
    make_cc_marketplace,
    make_cc_plugin,
    make_codex_marketplace,
    make_codex_plugin,
    read_json,
    write_json,
)


def load_module():
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "reconcile", PLUGIN_ROOT / "scripts" / "reconcile.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reconcile = load_module()


def file_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def reconciler(self):
        return reconcile.Reconciler(self.repo)

    def test_attach_cc_marketplace_converts_all_plugins_and_preserves_order(self):
        make_cc_marketplace(self.repo, ["two", "one"])
        make_cc_plugin(self.repo, "two")
        make_cc_plugin(self.repo, "one")

        report = self.reconciler().attach_marketplace("claude-code")

        names = [p["name"] for p in read_json(self.repo / ".agents/plugins/marketplace.json")["plugins"]]
        self.assertEqual(report.exit_code, 0)
        self.assertEqual(names, ["two", "one"])
        self.assertTrue((self.repo / "plugins/two/.codex-plugin/plugin.json").exists())
        self.assertTrue((self.repo / "plugins/one/.codex-plugin/plugin.json").exists())

    def test_attach_codex_marketplace_generates_cc_sibling(self):
        make_codex_marketplace(self.repo, ["one"])
        make_codex_plugin(self.repo, "one")

        report = self.reconciler().attach_marketplace("codex")

        names = [p["name"] for p in read_json(self.repo / ".claude-plugin/marketplace.json")["plugins"]]
        self.assertEqual(report.exit_code, 0)
        self.assertEqual(names, ["one"])
        self.assertTrue((self.repo / "plugins/one/.claude-plugin/plugin.json").exists())

    def test_sync_supports_mixed_plugin_sources(self):
        make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        make_cc_plugin(self.repo, "two")
        self.reconciler().attach_marketplace("claude-code")

        one_cc = self.repo / "plugins/one/.claude-plugin/plugin.json"
        one_payload = read_json(one_cc)
        one_payload["version"] = "2.0.0"
        write_json(one_cc, one_payload)

        two_state = self.repo / "plugins/two/.plugin-cross-port.yaml"
        two_state.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugin": "two",
                    "source_of_truth": "codex",
                    "status": "synced",
                    "manually_maintained": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        two_codex = self.repo / "plugins/two/.codex-plugin/plugin.json"
        two_payload = read_json(two_codex)
        two_payload["version"] = "3.0.0"
        write_json(two_codex, two_payload)

        report = self.reconciler().sync()

        self.assertEqual(report.exit_code, 0)
        self.assertEqual(read_json(self.repo / "plugins/one/.codex-plugin/plugin.json")["version"], "2.0.0")
        self.assertEqual(read_json(self.repo / "plugins/two/.claude-plugin/plugin.json")["version"], "3.0.0")

    def test_codex_first_metadata_updates_canonical_cc_entry(self):
        make_cc_marketplace(self.repo, ["two"])
        make_cc_plugin(self.repo, "two")
        self.reconciler().attach_marketplace("claude-code")
        state = self.repo / "plugins/two/.plugin-cross-port.yaml"
        state.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugin": "two",
                    "source_of_truth": "codex",
                    "status": "synced",
                    "manually_maintained": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        codex_manifest = self.repo / "plugins/two/.codex-plugin/plugin.json"
        payload = read_json(codex_manifest)
        payload["version"] = "2.0.0"
        write_json(codex_manifest, payload)

        report = self.reconciler().sync()

        self.assertEqual(report.exit_code, 0)
        entry = read_json(self.repo / ".claude-plugin/marketplace.json")["plugins"][0]
        self.assertEqual(entry["version"], "2.0.0")

    def test_failed_codex_target_is_not_available_and_other_plugins_continue(self):
        make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        (self.repo / "plugins/two").mkdir(parents=True)

        report = self.reconciler().attach_marketplace("claude-code")

        plugins = read_json(self.repo / ".agents/plugins/marketplace.json")["plugins"]
        policies = {p["name"]: p["policy"]["installation"] for p in plugins}
        self.assertEqual(report.exit_code, 1)
        self.assertEqual(policies["one"], "AVAILABLE")
        self.assertEqual(policies["two"], "NOT_AVAILABLE")

    def test_failed_cc_target_is_omitted_and_other_plugins_continue(self):
        make_codex_marketplace(self.repo, ["one", "two"])
        make_codex_plugin(self.repo, "one")
        (self.repo / "plugins/two").mkdir(parents=True)

        report = self.reconciler().attach_marketplace("codex")

        names = [p["name"] for p in read_json(self.repo / ".claude-plugin/marketplace.json")["plugins"]]
        failed = [r.name for r in report.results if r.status == "failed"]
        self.assertEqual(report.exit_code, 1)
        self.assertEqual(names, ["one"])
        self.assertEqual(failed, ["two"])

    def test_deleted_canonical_entry_removes_plugin_directory(self):
        marketplace = make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        make_cc_plugin(self.repo, "two")
        self.reconciler().attach_marketplace("claude-code")
        payload = read_json(marketplace)
        payload["plugins"] = [payload["plugins"][0]]
        write_json(marketplace, payload)

        report = self.reconciler().sync()

        self.assertEqual(report.exit_code, 0)
        self.assertFalse((self.repo / "plugins/two").exists())

    def test_delete_rejects_path_escape_without_filesystem_changes(self):
        marketplace = make_cc_marketplace(self.repo, ["one"])
        make_cc_plugin(self.repo, "one")
        self.reconciler().attach_marketplace("claude-code")
        outside = self.repo / "outside-sentinel"
        outside.mkdir()
        state_path = self.repo / ".plugin-cross-port.marketplace.yaml"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["plugins"]["two"] = {
            "path": "../outside-sentinel",
            "source_of_truth": "claude-code",
            "status": "synced",
        }
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        payload = read_json(marketplace)
        payload["plugins"] = []
        write_json(marketplace, payload)

        report = self.reconciler().sync()

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(outside.exists())

    def test_check_reports_stale_output_without_writes(self):
        make_cc_marketplace(self.repo, ["one"])
        make_cc_plugin(self.repo, "one")
        self.reconciler().attach_marketplace("claude-code")
        generated = self.repo / "plugins/one/.codex-plugin/plugin.json"
        payload = read_json(generated)
        payload["version"] = "stale"
        write_json(generated, payload)
        before = file_hashes(self.repo)

        report = self.reconciler().check()

        self.assertEqual(report.exit_code, 1)
        self.assertEqual(file_hashes(self.repo), before)

    def test_codex_exclude_skips_generation_and_removes_artifacts(self):
        make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        make_cc_plugin(self.repo, "two")
        self.reconciler().attach_marketplace("claude-code")
        self.assertTrue((self.repo / "plugins/two/.codex-plugin/plugin.json").exists())

        state_path = self.repo / ".plugin-cross-port.marketplace.yaml"
        state = read_json(state_path)
        state["codex_exclude"] = ["two"]
        write_json(state_path, state)

        report = self.reconciler().sync()

        self.assertEqual(report.exit_code, 0)
        self.assertFalse((self.repo / "plugins/two/.codex-plugin").exists())
        codex_names = [
            p["name"]
            for p in read_json(self.repo / ".agents/plugins/marketplace.json")["plugins"]
        ]
        self.assertNotIn("two", codex_names)
        self.assertIn("one", codex_names)
        self.assertTrue((self.repo / "plugins/one/.codex-plugin/plugin.json").exists())
        # CC side of the excluded plugin is left intact; cross-port marker removed
        self.assertTrue((self.repo / "plugins/two/.claude-plugin/plugin.json").exists())
        self.assertFalse((self.repo / "plugins/two/.plugin-cross-port.yaml").exists())


if __name__ == "__main__":
    unittest.main()
