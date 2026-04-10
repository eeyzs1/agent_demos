from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any
from .tools import stock_tools

class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = {}

class MCPRequest(BaseModel):
    toolcall: ToolCall

class MCPResponse(BaseModel):
    toolresult: Dict[str, Any]

class MCPServer:
    """MCP Server 实现"""
    
    def __init__(self):
        self.app = FastAPI()
        self.tools = stock_tools
        self._setup_routes()
    
    def _setup_routes(self):
        """设置路由"""
        @self.app.post("/mcp/v1/toolcall")
        async def toolcall(request: MCPRequest):
            """处理工具调用请求"""
            toolcall = request.toolcall
            tool_name = toolcall.name
            tool_args = toolcall.args
            
            if not tool_name:
                raise HTTPException(status_code=400, detail="Missing tool name")
            
            # 查找对应的工具
            tool = None
            for t in self.tools:
                if t["name"] == tool_name:
                    tool = t
                    break
            
            if not tool:
                raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
            
            # 调用工具
            try:
                result = tool["function"](**tool_args)
                return MCPResponse(toolresult={
                    "name": tool_name,
                    "result": result
                })
            except Exception as e:
                return MCPResponse(toolresult={
                    "name": tool_name,
                    "error": str(e)
                })
            
        @self.app.get("/mcp/v1/tools")
        async def get_tools():
            """获取可用工具列表"""
            return {
                "tools": [
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"]
                    } for tool in self.tools
                ]
            }
            
    @property
    def application(self):
        return self.app
    
    def create_app(self):
        """创建应用实例"""
        return self.app