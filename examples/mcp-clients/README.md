# Connecting other agents to Dabwayo over MCP

Dabwayo's MCP server (`python -m dabwayo.mcp_server`) is **provider-
neutral** — it speaks the Model Context Protocol over stdio, so any MCP-capable
client can drive the engine, not just Claude Code. They all run the *same*
tools (`create_project`, `add_text`, `add_callout`, `add_effect`, `set_camera`,
`update_clip`, `render_project`, …) against the **same shared store**, so a
human in the Studio UI and any of these agents collaborate on the same project.

Point every client at the **same** `DABWAYO_STORE` (and `DABWAYO_OUTPUT`)
so edits are shared. Each file here is a drop-in template; the schemas evolve,
so check your client's MCP docs if a key was renamed.

| Client | Config file | Key | Template |
|---|---|---|---|
| Claude Code / Cursor / Windsurf / Cline / Roo | `.mcp.json` (repo root) | `mcpServers` | `../../.mcp.json`, `cline_mcp_settings.json` |
| GitHub Copilot (VS Code agent mode) | `.vscode/mcp.json` | `servers` | `vscode-mcp.json` |
| opencode | `opencode.json` | `mcp` | `opencode.json` |

The common stdio shape is:

```jsonc
{
  "command": "python",
  "args": ["-m", "dabwayo.mcp_server"],
  "env": { "PYTHONPATH": ".", "DABWAYO_STORE": ".vf_projects", "DABWAYO_OUTPUT": "output" }
}
```

After wiring it up, ask the agent something like *"create a 1080p project, add a
red title '신제품' centered, and render it"* — it will call the Dabwayo MCP
tools, and the result appears in the Studio preview if you have it open on the
same store.

> The Studio's built-in chat panel is a separate convenience and is **also**
> provider-agnostic (Anthropic or any OpenAI-compatible endpoint) — see
> `dabwayo/studio/chat.py`. Use the MCP route above when you'd rather drive
> Dabwayo from your existing agent (Copilot, opencode, …) instead of the UI.
