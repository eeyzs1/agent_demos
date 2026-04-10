from app.mcp import MCPServer

# 创建 MCP 服务器实例
server = MCPServer()

# 获取应用实例
app = server.application

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("start_server:app", host="0.0.0.0", port=8000, reload=True)