"""Include the standalone RIGHTS regression suite in MCP Forge's root unittest discovery."""
from pathlib import Path
import importlib.util

_rights_tests = Path(__file__).resolve().parents[1] / "packages" / "rights" / "tests" / "test_rights.py"
_spec = importlib.util.spec_from_file_location("aldol_rights_tests", _rights_tests)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
RightsTests = _module.RightsTests
