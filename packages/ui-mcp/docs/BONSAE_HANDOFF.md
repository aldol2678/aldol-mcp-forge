# BONSAE -> ALDOL UI MCP handoff r1 (Draft)

Status: source integration proposed in a stacked Draft PR. No production release or direct
cross-service authentication is implied.

## Contract boundary

- Source: BONSAE generate_design_spec(brief) returns specification and constraints
  as JSON strings, not directly as a renderable UI tree.
- UI tool: ui_import_bonsae(bonsae_output_json, preset="forest").
  Accepts JSON text of the complete BONSAE response, or its decoded specification.
- Output: ui_spec_json (UI schema 0.3), ui_validation, unmapped intent report,
  status=HANDOFF_REVIEW_REQUIRED, release_authorized=false.
- It does NOT call BONSAE over HTTP or deploy UI. A trusted host workflow transfers
  the actual BONSAE result into the importer.

## Mapping

| BONSAE input | UI output | Treatment |
|---|---|---|
| goal | title + heading text | first 100 characters; overflow reported |
| components[].name / role | card placeholder | NOT a functional component |
| states, interaction, mobile_behavior, accessibility | unimplemented.components | ALL intent retained |
| tokens.primary/background/foreground | theme | valid six-digit hex only |
| tokens.font/density/radius | UI tokens | accepted enumerations only |
| other tokens | unmapped_tokens | not applied |
| layouts, motion, accessibility, device | unimplemented | must be implemented and tested |
| constraints | unimplemented.constraints | not a release authorization |

No code execution, URL fetch, arbitrary CSS/JS, cross-service credentials,
game actions, data binding, image assets, or production writes are performed.

## Host orchestration

1. Invoke BONSAE generate_design_spec with an explicit design brief.
2. Serialize the complete returned result to JSON and pass to UI import_bonsae.
3. Inspect ui_validation, unimplemented and unmapped_tokens.
4. Use ui_generate(ui_spec_json) only for a STRUCTURAL PREVIEW.
5. A developer or SEUM implements actions, states, responsive behavior and accessibility.
6. Recheck actual rendered UI with BONSAE and Game Ops, including Android.
7. User authorizes any publication or final acceptance separately.

## Verification gates

- Before merge: UI unit tests, MCP tool discovery, malformed input, token validation.
- Before remote rollout: official SDK stdio/HTTPS, auth/security, old 7 tool regression.
- Before product adoption: real BONSAE call, real source-to-import-to-render chain,
  browser/Android rendering, visual review and host action/state tests.
- Never treat a placeholder preview as implementation, aesthetic approval or release.

## Current limits

- Existing UI service and private plugin v0.3.2 currently report seven tools.
  This source adds an EIGHTH tool, but is not deployed by merely opening this PR.
- BONSAE backend can remain unavailable due Railway provisioning limits. Mock
  fixtures validate compatibility with documented shape, not live cross-app operation.
- The original seven UI tools and schema versions 0.1/0.2/0.3 are unchanged.
