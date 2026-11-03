"""Stage only reviewed MAJUNG Python modules; never edit originals or deploy.

Run from the repository root: python adapters/majung-cloudflare/prepare.py
"""
from pathlib import Path
import shutil
import hashlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "enterprise_mcps"
DEST = HERE / "src" / "enterprise_mcps"
# Git blob hashes from MAJUNG parent PR #22; fail rather than silently bundle
# changed unreviewed Python code on a new deployment.
PINNED_BLOBS = {
    "majung.py": "cd377aa81753e5a7b8460b98635c0ec2d5519818",
    "majung_research.py": "9f1b71499cc01f3d3fa853631ddc3d985d9c2bec",
    "common.py": "98fd8d98bc327eaa245983591bb6b05c7abb86ca",
}

def verify_blob(path, expected):
    content = path.read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\\0" + content).hexdigest()
    if actual != expected:
        raise RuntimeError("Source changed; review before staging: " + path.name)

def prepare():
    for name, expected in PINNED_BLOBS.items():
        verify_blob(SOURCE / name, expected)
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "__init__.py").write_text('"""Isolated, generated MAJUNG source package."""\n', encoding="utf-8")
    for name in ("majung.py", "majung_research.py"):
        shutil.copyfile(SOURCE / name, DEST / name)
    common = (SOURCE / "common.py").read_text(encoding="utf-8")
    assert "from contract_forge import parse_contract\n" in common
    assert "\ndef contract(" in common
    pure = common.replace("from contract_forge import parse_contract\n", "").split("\ndef contract(", 1)[0] + "\n"
    (DEST / "common.py").write_text(pure, encoding="utf-8")
    print("Staged unchanged MAJUNG analysis/source logic and bounded common helpers.")

if __name__ == "__main__":
    prepare()
