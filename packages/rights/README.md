# ALDOL RIGHTS v0.1.0

Evidence-first, local-first asset rights preflight MCP. Five tools: `register_asset`, `inspect_license`, `check_usage`, `generate_credits`, `rights_report`.

## Quickstart

Python 3.11+ and official MCP Python SDK 2.x:

```sh
python -m pip install -r packages/rights/requirements.txt
python packages/rights/server.py
```

Configure any MCP client to launch `python /ABSOLUTE/PATH/aldol-mcp-forge/packages/rights/server.py` over stdio. **Not hosted or registered with ChatGPT automatically.** Run pure unit tests without dependencies via `python -m unittest discover -s packages/rights/tests -v`.

Default database: `$XDG_DATA_HOME/aldol-rights/rights.sqlite3` or `~/.local/share/aldol-rights/rights.sqlite3`. Set `ALDOL_RIGHTS_DB` to an absolute path to override. Avoid synced/public directories containing rights records. On POSIX the database file is chmod 0600 and newly created parent directory uses mode 0700. Do not commit the database. Evidence links are supplied by the user, not fetched or validated. No automatic external calls, file scans, scraping, deletions, public postings or uploads.

## Decisions and boundaries

- Standard shorthand recognizes six CC 4.0 variants and CC0 1.0, plus `MIT`, `APACHE-2.0`, `OFL-1.1`, `OWNED`, `CUSTOM`, `UNKNOWN`. The latter six are **manual-review-only**; none proves rights. Not yet automated: notice handling under MIT/OFL/Apache, platform-specific audio rights, stock image contracts, trademark/personality rights, AI training-data provenance, exceptions and territorial restrictions.
- Asset registration is only an **unverified claim**, even when the evidence_url field is populated. `READY_FOR_HUMAN_REVIEW` is **not** licensing approval. `BLOCKED` is a detected contradiction under the license *recorded by the user*, pending any separate grants.
- Checks are deliberately conservative. CC ND only blocks **sharing** an adaptation, not making a private modification. CC SA when redistributing an adaptation still needs a human compatibility check. Credit output is a draft; full license notice and modification notes must be verified before distribution.
- Any missing source or evidence URL produces `NEEDS_EVIDENCE` unless there is a direct blocking rule. URLs are accepted as metadata but never downloaded or considered authentic. A fully populated record still needs source-level inspection.
- `asset_ids_json="[]"` means all assets, but returns an explicit error if more than 500 are registered (no silently incomplete reports). To target particular assets, pass a JSON string array of IDs. No asset changes or deletions after registration in this MVP; corrections require a reviewed future workflow.

## Example (import core with `PYTHONPATH=packages/rights`)

```python
from core import register_asset, check_usage
asset = register_asset(title="Example CC BY-NC artwork", kind="image", license_id="CC-BY-NC-4.0",
                       creator="Example author", source_url="https://example.org/asset",
                       evidence_url="https://example.org/original-license")
print(check_usage(asset["asset_id"], commercial=True)) # BLOCKED (NC)
```

References: [CC license information](https://creativecommons.org/cc-licenses/), [Korea Copyright Commission public license guide](https://gongu.copyright.or.kr/gongu/main/contents.do?menuNo=200093), [MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/).
