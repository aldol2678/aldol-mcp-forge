# ALDOL specialist MCPs: SEUM / BONSAE / MAJUNG

Functional, read-only MVP implementing the 9 MCP tool names and output fields
from the existing Forge v0.4 example contracts in examples/.

These are three **separate opt-in stdio MCP servers**, not a change to
deployed Forge Studio v9. Forge-generated scaffold handlers remain
NOT_IMPLEMENTED. No merging or production deployment is performed here.

## Run

At repository root with Python 3.11+ and mcp==2.0.0:

    python -m pip install 'mcp==2.0.0'
    python -m enterprise_mcps seum
    python -m enterprise_mcps bonsae
    python -m enterprise_mcps majung

No external HTTP, shell command, local filesystem mutation, paid AI, key access,
or repository deployment in these tool handlers. Inputs are bounded to 4096
characters per string, and results must match the source Forge contract.

## Input conventions

Every MCP parameter is a string. For structured arguments, pass JSON text.

SEUM:
- analyze_code(repository, focus?): repository JSON with path, language
  (python or json) and content. AST or JSON parsing, import/function counts
  and selected dynamic execution risk patterns. Does not execute source.
- implement_change(repository,request): repository JSON with path/content;
  request JSON with find, replace, expected_sha256. Returns checksum-guarded
  unified diff without modifying the filesystem.
- review_release(release_ref): JSON with revision and checks map for ci, tests,
  security, cost and mobile. All PASS required for technical readiness PASS.
  Never authorizes launch.

BONSAE:
- analyze_design(reference,target?): raw HTML and optional raw CSS; static
  checks for alt, labels, viewport, duplicate ID and potential clipping.
- generate_design_spec(brief): JSON with goal, components each with name,
  role, states, mobile_behavior; optionally tokens and device. Lists absent
  loading/empty/error/disabled states without inventing design intent.
- review_visual(artifact): JSON with artifact_id, viewport, observations and
  screenshot_refs. Reports HOLD_UNINSPECTED until actual rendered inspection.
  Passing screenshot links is not proof that pixels were inspected.

MAJUNG:
- research_market(question,region?): question JSON with question and dated
  sources (title,url,claim,observed_at). Organizes user-supplied evidence,
  flags stale observations and missing independent sources. No web fetching.
- analyze_competitors(product): JSON with name, price, currency and competitor
  records (name, price, currency, source_url, observed_at). Only price math.
  Mixed currencies are rejected; no invented feature differentiation.
- evaluate_opportunity(brief): JSON with name, price, variable_cost,
  acquisition_cost, expected_customers and evidence_urls. Computes
  per-customer contribution and scenario totals. Advisory HOLD/NO-GO only,
  never permission to launch, pay or alter a canonical strategy.

All URLs are user-provided metadata. No external information is independently
verified by these MCP tools. No actual browser visual QA occurs here.

## Tests

Without SDK:
    python -m unittest discover -s enterprise_mcps/tests -p test_logic.py -v

Official Python MCP SDK v2 in-memory and real stdio:
    python -m unittest discover -s enterprise_mcps/tests -p test_sdk.py -v

Canonical contract validation uses contract_forge.py from the same Forge
repository. No private account credentials are needed for unit testing.
