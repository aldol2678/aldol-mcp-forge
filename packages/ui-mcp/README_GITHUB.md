# ALDOL UI MCP Alpha 0.3.2

Source inherited from PR #19 and the matching Library archive. UI schema versions 0.1/0.2/0.3 and all seven MCP tool signatures remain supported.

See `OPERATIONS.md` for authenticated stdio/HTTP setup, `OPERATIONAL_VERIFICATION_20261021.md` for current evidence, and `VERIFICATION.md` for the earlier historical snapshot.

Install `requirements.txt` (official MCP SDK 2.3.0) and run:
```
python -m unittest discover -s tests -v
python tests/sdk_smoke.py
python tests/local_http.py /tmp/ui-mcp-http
```

Private endpoint: https://ui-mcp-api-production.up.railway.app/mcp
Bearer API key required; credentials are stored in the UI Railway service, not the repository or plugin package. Public `/health` contains no UI/user data.

ChatGPT private plugin: https://chatgpt.com/plugins/plugins_6ad810ca2dd08191a4a44e8dc1bc68c6
Creation is verified; installation/authentication and host tool calls remain BLOCKED pending user connection. Keep PR #19 Draft.

## BONSAE design handoff (source-only Draft)

This branch adds `ui_import_bonsae(bonsae_output_json, preset='forest')` as the eighth MCP tool.
It accepts BONSAE `generate_design_spec` output (the JSON-encoded `specification` and `constraints` fields),
and produces a validated **structural preview**, with an explicit report of unimplemented states,
actions, responsive layout and accessibility. It never claims functional or visual completion.
See [docs/BONSAE_HANDOFF.md](docs/BONSAE_HANDOFF.md) for the contract and review gates.

The existing deployed endpoint and plugin are still on the prior seven-tool version until
separately redeployed and verified. A source branch/PR is not a production rollout.
