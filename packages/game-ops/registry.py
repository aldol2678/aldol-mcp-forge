"""Read-only, evidence-labeled ALDOL game inventory.

The Git-tracked catalog is a historical *index*, not a live build or release
authority. This module never fetches URLs, opens repository files or writes data.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlsplit

DEFAULT_CATALOG = Path(__file__).with_name("games.json")
MAX_CATALOG_BYTES = 128 * 1024
STAGES = frozenset(("active", "prototype", "released", "paused", "planned", "platform", "unknown"))
GAME_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class GameRegistry:
    def __init__(self, catalog_path: str | Path = DEFAULT_CATALOG):
        self.catalog_path = Path(catalog_path)

    def _load(self):
        raw = self.catalog_path.read_bytes()
        if len(raw) > MAX_CATALOG_BYTES:
            raise ValueError("Catalog is too large")
        catalog = json.loads(raw)
        if (not isinstance(catalog, dict) or catalog.get("schema_version") != 1
                or not isinstance(catalog.get("games"), list)
                or not isinstance(catalog.get("snapshot_as_of"), str)):
            raise ValueError("Invalid game catalog schema")
        seen = set()
        for game in catalog["games"]:
            if not isinstance(game, dict):
                raise ValueError("Invalid game record")
            ident = game.get("game_id")
            if (not isinstance(ident, str) or len(ident) > 64
                    or not GAME_ID.fullmatch(ident) or ident in seen):
                raise ValueError("Invalid or duplicate game ID")
            seen.add(ident)
            if (not isinstance(game.get("title"), str) or not game["title"].strip()
                    or len(game["title"]) > 160 or game.get("stage") not in STAGES):
                raise ValueError("Invalid game title or stage")
            if game.get("verification") != "UNVERIFIED":
                raise ValueError("Historical seed cannot claim verified state")
            if not isinstance(game.get("next_action"), str) or len(game["next_action"]) > 400:
                raise ValueError("Invalid next action")
            if not isinstance(game.get("last_known_version"), (str, type(None))):
                raise ValueError("Invalid last known version")
            links = game.get("links", {})
            if not isinstance(links, dict) or len(links) > 8:
                raise ValueError("Invalid game links")
            for label, link in links.items():
                if not isinstance(label, str) or not isinstance(link, str) or len(link) > 2048:
                    raise ValueError("Invalid game link")
                u = urlsplit(link)
                if (u.scheme != "https" or not u.hostname or u.username is not None
                        or u.password is not None):
                    raise ValueError("Only absolute HTTPS links without credentials allowed")
            aliases = game.get("aliases", [])
            if (not isinstance(aliases, list) or len(aliases) > 16
                    or any(not isinstance(a, str) or len(a) > 160 for a in aliases)):
                raise ValueError("Invalid aliases")
        return catalog

    @staticmethod
    def _summary(game):
        return {key: game.get(key) for key in
                ("game_id", "title", "stage", "last_known_version", "verification", "next_action")}

    def list_games(self, stage: str | None = None, query: str = "",
                   limit: int = 50, offset: int = 0) -> dict:
        if stage is not None and stage not in STAGES:
            raise ValueError("Unknown stage")
        if not isinstance(query, str) or len(query) > 100:
            raise ValueError("Search query must be at most 100 characters")
        if (type(limit) is not int or not 1 <= limit <= 100
                or type(offset) is not int or not 0 <= offset <= 10000):
            raise ValueError("Invalid pagination")
        catalog = self._load()
        term = query.casefold().strip()
        games = [
            g for g in catalog["games"]
            if (stage is None or g["stage"] == stage)
            and (not term or term in g["title"].casefold()
                 or term in g["game_id"] or any(term in a.casefold() for a in g.get("aliases", [])))
        ]
        return {
            "snapshot_as_of": catalog["snapshot_as_of"],
            "total": len(games),
            "offset": offset,
            "items": [self._summary(g) for g in games[offset:offset + limit]],
            "verification": "UNVERIFIED",
            "notice": "Historical inventory, NOT live GitHub/QA/production status.",
        }

    def get_game(self, game_id: str) -> dict:
        if not isinstance(game_id, str) or not GAME_ID.fullmatch(game_id):
            raise ValueError("Invalid game_id")
        catalog = self._load()
        for game in catalog["games"]:
            if game["game_id"] == game_id:
                return {
                    **game,
                    "snapshot_as_of": catalog["snapshot_as_of"],
                    "notice": "Historical entry; verify code, builds, deployment and QA separately.",
                }
        raise ValueError("Unknown game_id")

    def get_game_resume(self, game_id: str) -> dict:
        game = self.get_game(game_id)
        return {
            "game_id": game_id,
            "title": game["title"],
            "last_known_version": game.get("last_known_version"),
            "next_action": game["next_action"],
            "links": game.get("links", {}),
            "stage": game["stage"],
            "verification": "UNVERIFIED",
            "release_readiness": "UNKNOWN",
            "required_check": "Confirm current source, build, latest PR and QA before editing or deploying.",
            "snapshot_as_of": game["snapshot_as_of"],
        }
