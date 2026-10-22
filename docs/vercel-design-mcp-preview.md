# ALDOL Design MCP on Vercel (preview)

Separate logical MCP endpoints in one isolated Vercel FastAPI deployment:
- `/bonsae/mcp` (three specialist tools, actual BONSAE source from PR #21)
- `/ui/mcp` (eight ALDOL UI MCP tools, includes `ui_import_bonsae`)
- `/health` (minimal readiness only)

All MCP routes require `Authorization: Bearer <ALDOL_DESIGN_MCP_KEY>` and accepted Host/Origin. No secret is stored in Git. The Vercel preview project must set `ALDOL_DESIGN_MCP_KEY` in its environment before deployment. Stateless JSON Streamable HTTP; parent FastAPI lifespan starts both MCP session managers. Vercel's Python runtime must support ASGI lifespan and mounted routes; verify with authenticated live MCP tool discovery and calls before claiming success. This is a single-host preview, not server-to-server transport across two independent hosts. Deployment protection may block external ChatGPT clients; test Android actual calls separately. Neither GitHub main nor Railway is modified.
