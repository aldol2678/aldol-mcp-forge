"""Game portfolio registry: conservative historical evidence and safe read-only API."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry import GameRegistry, DEFAULT_CATALOG


def test_seed_inventory_and_handoff():
    registry = GameRegistry()
    all_games = registry.list_games()
    assert all_games["total"] >= 20
    assert all_games["verification"] == "UNVERIFIED"
    assert len({g["game_id"] for g in all_games["items"]}) == all_games["total"]
    assert registry.list_games(query="군단")["total"] == 1
    assert registry.list_games(query="little legion")["total"] == 1
    assert registry.list_games(stage="active")["total"] > 0
    assert registry.list_games(limit=1, offset=1)["items"][0]["game_id"]
    game = registry.get_game("tiny-army-expedition")
    assert game["links"]["github"].startswith("https://github.com/")
    assert game["verification"] == "UNVERIFIED"
    resume = registry.get_game_resume("tiny-army-expedition")
    assert resume["release_readiness"] == "UNKNOWN"
    assert "Confirm current source" in resume["required_check"]


@pytest.mark.parametrize("options", [
    {"stage": "nonsense"}, {"query": "x" * 101}, {"limit": 0},
    {"limit": 101}, {"offset": -1}, {"limit": True}, {"offset": 1.5},
])
def test_invalid_filters_are_rejected(options):
    with pytest.raises(ValueError):
        GameRegistry().list_games(**options)


@pytest.mark.parametrize("game_id", ["../games.json", "NO", "not-found", "", "x" * 100])
def test_unknown_or_unsafe_game_id_is_rejected(game_id):
    with pytest.raises(ValueError):
        GameRegistry().get_game(game_id)


@pytest.mark.parametrize("change", [
    lambda c: c["games"].append(dict(c["games"][0])),
    lambda c: c["games"][0].update(verification="VERIFIED"),
    lambda c: c["games"][0].update(stage="done"),
    lambda c: c["games"][0].update(links={"evil": "file:///etc/passwd"}),
    lambda c: c["games"][0].update(links={"evil": "https://name:token@example.com/x"}),
    lambda c: c.update(schema_version=999),
])
def test_invalid_catalog_fails_closed(tmp_path, change):
    catalog = json.loads(DEFAULT_CATALOG.read_text())
    change(catalog)
    path = tmp_path / "games.json"
    path.write_text(json.dumps(catalog))
    with pytest.raises(ValueError):
        GameRegistry(path).list_games()


def test_registry_never_modifies_catalog(tmp_path):
    path = tmp_path / "games.json"
    path.write_bytes(DEFAULT_CATALOG.read_bytes())
    before = path.read_bytes()
    registry = GameRegistry(path)
    registry.list_games(query="INHA")
    registry.get_game_resume("time-clone-factory")
    assert path.read_bytes() == before


def test_oversized_catalog_is_rejected(tmp_path):
    path = tmp_path / "games.json"
    path.write_bytes(b" " * (128 * 1024 + 1))
    with pytest.raises(ValueError):
        GameRegistry(path).list_games()
