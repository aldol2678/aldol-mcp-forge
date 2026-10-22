"""Disposable QA worker. Static checks NEVER evaluate artifact JavaScript."""

import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import html_qa


def main():
    target, kind, profile_path, out = map(
        Path, [sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]]
    )
    if os.name == "posix":
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    files, entry, _ = html_qa.read_artifact(target)
    checks = []
    if str(kind) == "static":
        html_qa.static_checks(files, entry, checks)
    else:
        profile = json.loads(profile_path.read_text())
        if str(kind) == "browser":
            profile["scenarios"] = []
        elif str(kind) == "scenarios":
            profile["viewports"] = []
        html = html_qa.embed_for_browser(
            files[entry].decode("utf-8", "replace"), entry, files
        )
        html_qa.browser_checks(html, profile, checks, out)
    (out / "result.json").write_text(json.dumps(checks), encoding="utf-8")


if __name__ == "__main__":
    main()
