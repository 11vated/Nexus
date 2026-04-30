# Custom MCP Server Framework
Run any open-source MCP server with this launcher

## Quick Start - Add Popular MCPs

```bash
# Start Ollama first
ollama serve

# Then run Goose with MCP servers configured in config.yaml
```

## MCP Servers to Add

### High Value Open Source MCPs (Install via npm/pip/uv)

1. **Filesystem** - Full file system access
   `npx @modelcontextprotocol/server-filesystem /`

2. **GitHub** - Issues, PRs, repos
   `npx @modelcontextprotocol/server-github`

3. **Playwright** - Browser automation
   `npx @modelcontextprotocol/server-playwright`

4. **Postgres** - Database queries
   `npx @modelcontextprotocol/server-postgres`

5. **Brave Search** - Web search
   `npx @modelcontextprotocol/server-brave-search`

6. **Memory** - Persistent context
   `npx @modelcontextprotocol/server-memory`

## Custom MCP Server Template

Create your own in `mcp-servers/custom/`:

```python
# my-custom-mcp.py
from mcp.server import Server
from mcp.types import Tool, Resource

server = Server("my-custom-mcp")

@server.tool()
def my_tool(arg1: str) -> str:
    """My custom tool"""
    return f"Result: {arg1}"

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run())
```

## Goose MCP Config

Add to `config.yaml`:

```yaml
mcp_servers:
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/"]
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
  memory:
    command: python
    args: ["-m", "mcp.server.memory"]
```

## Useful MCPs for Development

| MCP | Use Case | Install |
|------|---------|---------|
| filesystem | Read/write any file | npx @modelcontextprotocol/server-filesystem ~ |
| github | GitHub API | npx @modelcontextprotocol/server-github |
| puppeteer | Browser automation | npx @modelcontextprotocol/server-puppeteer |
| postgres | Database | npx @modelcontextprotocol/server-postgres |
| sqlite | Local DB | npx @modelcontextprotocol/server-sqlite |
| sequential-thinking | Better reasoning | npx @modelcontextprotocol/server-sequential-thinking |

## Notes

- MCP servers run as stdio processes
- Goose auto-discovers servers in PATH
- Use uv for Python MCPs: `uvx mcp-server-*`