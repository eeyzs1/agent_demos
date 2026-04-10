from mcp.server import MCPServer

# 创建 MCP Server 实例
mcp_server = MCPServer()

# 获取 FastAPI 应用实例
app = mcp_server.application

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)