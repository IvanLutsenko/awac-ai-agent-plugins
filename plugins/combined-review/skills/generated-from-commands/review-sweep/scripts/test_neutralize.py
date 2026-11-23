"""Run: python3 plugins/combined-review/scripts/test_neutralize.py"""
import importlib.util, pathlib

Z = "​"
here = pathlib.Path(__file__).parent
for name in ("post-gitlab-mr-threads.py", "post-github-pr-threads.py"):
    spec = importlib.util.spec_from_file_location("m", here / name)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    n = m.neutralize
    assert n("Finding\n/merge\n  /approve") == f"Finding\n/{Z}merge\n  /{Z}approve", name
    assert n("ask @alice and @bob-x") == f"ask @{Z}alice and @{Z}bob-x", name
    assert n("mail a@b.kz") == f"mail a@{Z}b.kz", name  # over-eager but harmless
    fenced = "see\n```kotlin\n/merge\n@Inject val x\n```\n@carol"
    assert n(fenced) == f"see\n```kotlin\n/merge\n@Inject val x\n```\n@{Z}carol", name
    assert n("use `@Composable` and `/tmp`") == "use `@Composable` and `/tmp`", name
    assert n("path a/b stays") == "path a/b stays", name
    assert n("unclosed\n```\n/merge") == f"unclosed\n```\n/{Z}merge", name  # unclosed = prose
    assert n("a ` b\n\n/merge\n\nc ` d") == f"a ` b\n\n/{Z}merge\n\nc ` d", name  # stray backticks
    assert n("- item\n\n    ```\n    /merge\n    ```") == f"- item\n\n    ```\n    /{Z}merge\n    ```", name
    assert n("x\n``` a`b\n/merge\n```") == f"x\n``` a`b\n/{Z}merge\n```", name  # invalid opener
    assert n("~~~\n/merge\n~~~") == "~~~\n/merge\n~~~", name
    assert n("` @alice ``") == f"` @{Z}alice ``", name  # unequal runs are not code
    assert n("````\n```\n@in\n````\n@out") == f"````\n```\n@{Z}in\n````\n@{Z}out", name  # unparsed fence = prose
    assert n("``a`b`` @x") == f"``a`b`` @{Z}x", name
print("ok")
