# ALDOL UI MCP Alpha 0.3.2

Source restored from the owned Library ZIP and integrated with two additional anti-slop rules.
See UI_MCP_README.md, docs/ANTI_AI_SLOP.md and VERIFICATION.md.

## Run tests

```sh
python -m unittest discover -s tests -q
python tests/browser_03.py
```

## MCP entrypoint

`python -m ui_core.server` needs official Python MCP SDK v2.0 or compatible release. This runtime could not access the dependency index; actual SDK connection is NOT VERIFIED. This code is not an already-deployed remote server.
