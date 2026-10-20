# ALDOL MCP Forge — Sites read-only adapter

An independent, dependency-free JavaScript Worker adapter for **three** existing
Forge preview tools. The Python entrypoints, generators, verification and packaging
remain unchanged. MIT, as with the parent repository.

## Exposed tools

| Tool | Input | Result |
| --- | --- | --- |
| `forge_list_templates` | `{}` | Existing three-template name/description mapping |
| `forge_preview` | `description`: string, 1–2000 code points | Existing `supported`, `template`, `capabilities`, `note` |
| `forge_preview_openapi` | `spec_json`: string, 2–120000 code points | Existing operation names, count, skipped non-GETs and no-network default |

Schemas preserve the legacy contract and SDK v2 field bounds. Unknown arguments
are rejected, matching the SDK entrypoint's rejection middleware. Success returns
the same domain object in textual JSON and `structuredContent`; this adapter does
not promise byte-identical SDK-generated titles, wrapper metadata or error prose.
Expected validation failures return `isError: true` with no structured success body.

Natural-language preview uses the **existing keyword selector**, not an LLM and
not arbitrary code generation. OpenAPI preview uses the existing conservative
3.0.x/3.1.x JSON GET subset: max 64 paths, max 12 operations and max 12 inline
scalar path/query parameters per operation. Parameter references, advanced
serialization, duplicate identifiers, unsafe paths and Python keywords are
refused. Non-GET methods are reported as skipped. No spec URLs are fetched and
no imported source is executed. Security declarations, servers, response schemas
and components do not grant network or authentication capabilities.

The HTTP JSON parser requires standard JSON; Python's nonstandard NaN/Infinity
constants are intentionally not accepted. JSON-RPC body size is bounded at
1,500,000 UTF-8 bytes (including chunked bodies) in addition to per-field limits.

## Local checks

Requires Node 24 and Python 3.11+ only; no npm or pip installation is needed.
Run from this directory in the **full Forge repository**:

```sh
node --test --test-reporter=tap tests/*.test.mjs
bash scripts/build.sh
node scripts/validate-artifact.mjs
```

The differential tests execute the unchanged Python handlers and compare schemas,
successful objects and rejected inputs against the Worker. Protocol tests cover
stateless discovery, list/call, malformed requests, notifications, bounds,
cross-origin requests, no external network and user input independence. A separate
loopback HTTP test invokes all three tools. This is not a substitute for actual
ChatGPT plugin calls or Cloudflare runtime testing.

`npm start` is an optional loopback-only developer harness. It has **no Sites
authentication** and must not be exposed publicly. The deployed artifact contains
only the Worker and hosting manifest, not this Node harness or the Python tests.

## Sites deployment

1. Copy `worker/`, `scripts/build.sh`, `scripts/validate-artifact.mjs`, `package.json`
   and `.openai/hosting.json` into a separate Sites deployment checkout. The public
   manifest intentionally has no project ID; reuse a registered Site's ID if one
   already exists.
2. Use the supported Sites registration/source workflow to persist the returned
   `project_id`, build, validate and push the exact source. No manual credentials
   belong in the manifest or source. The manifest declares `capabilities: ["mcp"]`
   and leaves both `d1` and `r2` null.
3. Publish only to the authorized audience. For an owner-private Site, use the
   owner-private operation and retain its version/deployment IDs. Every Sites
   deployment URL is a production URL, including private Sites; it is not a
   separate preview tier.
4. Read the connection using `get_site(include_mcp_connection: true)`. Use the
   actual returned MCP endpoint and plugin ID. Sites creates the private plugin
   and owns OAuth/viewer authentication for `/mcp`.
5. Install/connect that existing plugin. If it is already installed but tools
   do not appear in the current conversation, start a new conversation and select
   the plugin, then invoke each read-only tool. Installation is not a tool-call
   success. Do not describe the whole integration as live-verified before that.

POST `/mcp` implements Sites MCP `2026-07-28`: `server/discover`, `tools/list`,
`tools/call`. `initialize`, `notifications/initialized` and `ping` are supplied
for client compatibility. No sessions, global initialization flag or user data
are retained. Auth is supplied by Sites dispatch; this file is not an independent
OAuth server and should not be deployed to an unauthenticated generic Worker.

The optional `scripts/verify-remote.mjs` takes a single JSON line on stdin with
`url`, optional `token` and optional `output`. PTY echo is disabled before reading
credentials. It never prints auth headers. A Sites **service** credential may
authenticate ordinary Site routes but must not be assumed to authenticate the
OAuth MCP endpoint. HTTP 401 is an authentication test failure, not an application
crash and not permission to add an unauthenticated bypass route.

## Extension boundary

The five writing/testing tools (`forge_create`, `forge_add_tool`, `forge_test`,
`forge_package`, `forge_import_openapi`) are **not exposed or implemented** here.
See [the assessment and execution report](../../docs/sites-integration-20261020.md)
for evidence, restrictions and the minimal future Python execution bridge.

There is no writable path, project selector, persistent data or outbound fetch
in this version. Consequently there is no shared working directory to traverse
or overwrite. Future persisted work must use Site-authenticated identity and
server-generated object keys; user-provided workspace paths must never cross
the bridge.
