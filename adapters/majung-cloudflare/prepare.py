"""Stage only reviewed MAJUNG Python modules; never edit originals or deploy.

Run from the repository root: python adapters/majung-cloudflare/prepare.py
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "enterprise_mcps"
DEST = HERE / "src" / "enterprise_mcps"

def prepare():
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
