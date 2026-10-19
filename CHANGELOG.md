# Changelog

## v0.3.2 (2026-10-20)

- Generate `dict[str, Any]` tool return annotations for structured responses with official MCP Python SDK 2.0.0; regenerate CI servers and checksums.
- Wrap stdio parameters with `stdio_client` when constructing the SDK client.
- Stop ignoring `workspace/projects` so CI targets can be committed; ignore `ci-results/`.
