import os
import json
import requests
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional

class MCPClient:
    """MCP Client 实现"""
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 从环境变量中读取配置
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
        self.llm_api_key = os.getenv("LLM_API_KEY")
        self.llm_model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        self.llm_base_url = os.getenv("LLM_BASE_URL")
        
        # 确保 LLM 配置存在
        if not self.llm_api_key:
            raise ValueError("LLM_API_KEY is required in .env file")
        if not self.llm_base_url:
            raise ValueError("LLM_BASE_URL is required in .env file")
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        try:
            response = requests.get(f"{self.mcp_server_url}/mcp/v1/tools")
            response.raise_for_status()
            data = response.json()
            return data.get("tools", [])
        except Exception as e:
            print(f"Error getting tools: {e}")
            return []
    
    def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        try:
            payload = {
                "toolcall": {
                    "name": tool_name,
                    "args": tool_args
                }
            }
            response = requests.post(f"{self.mcp_server_url}/mcp/v1/toolcall", json=payload)
            response.raise_for_status()
            
            # 尝试解析响应
            try:
                data = response.json()
                return data.get("toolresult", {})
            except json.JSONDecodeError as e:
                # 打印原始响应内容
                print(f"JSON decode error: {e}")
                print(f"Raw response: {response.text}")
                return {"error": f"JSON decode error: {str(e)}"}
        except Exception as e:
            print(f"Error calling tool: {e}")
            return {"error": str(e)}
    
    def query_llm(self, prompt: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """查询 LLM"""
        try:
            # 构建请求体
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Use the available tools to answer questions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # 构建工具列表
            tools_for_llm = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"]
                    }
                }
                for tool in tools
            ]
            
            # 发送请求到 LLM
            response = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.llm_model,
                    "messages": messages,
                    "tools": tools_for_llm,
                    "tool_choice": "auto"
                }
            )
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error querying LLM: {e}")
            return {"error": str(e)}
    
    def process_llm_response(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """处理 LLM 响应"""
        try:
            # 检查是否有工具调用
            if "choices" in llm_response:
                choice = llm_response["choices"][0]
                if "message" in choice:
                    message = choice["message"]
                    if "tool_calls" in message:
                        # 处理工具调用
                        tool_calls = message["tool_calls"]
                        results = []
                        
                        for tool_call in tool_calls:
                            tool_name = tool_call["function"]["name"]
                            tool_args = json.loads(tool_call["function"]["arguments"])
                            
                            # 调用工具
                            tool_result = self.call_tool(tool_name, tool_args)
                            results.append({
                                "tool_call_id": tool_call["id"],
                                "tool_name": tool_name,
                                "result": tool_result
                            })
                        
                        return {
                            "tool_calls": tool_calls,
                            "tool_results": results
                        }
                    else:
                        # 直接返回 LLM 回答
                        return {
                            "answer": message.get("content", "")
                        }
            
            return {"error": "Invalid LLM response"}
        except Exception as e:
            print(f"Error processing LLM response: {e}")
            return {"error": str(e)}
    
    def chat(self, prompt: str) -> Dict[str, Any]:
        """与 LLM 聊天并使用工具"""
        # 获取可用工具
        tools = self.get_available_tools()
        
        if not tools:
            return {"error": "No tools available"}
        
        # 构建初始消息
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Use the available tools to answer questions."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        # 构建工具列表
        tools_for_llm = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            }
            for tool in tools
        ]
        # 第一次查询 LLM
        try:
            response = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.llm_model,
                    "messages": messages,
                    "tools": tools_for_llm,
                    "tool_choice": "auto"
                }
            )
            
            response.raise_for_status()
            llm_response = response.json()
        except Exception as e:
            print(f"Error querying LLM: {e}")
            return {"error": str(e)}
        
        print(f"LLM Response: {json.dumps(llm_response, indent=2)}")
        # 处理 LLM 响应
        if "choices" not in llm_response:
            return {"error": f"No choices in LLM response: {llm_response}"}
        
        choice = llm_response["choices"][0]
        if "message" not in choice:
            return {"error": f"No choice in choices: {llm_response}"}
        
        message = choice["message"]
        
        # 检查是否有工具调用
        if "tool_calls" in message:
            tool_calls = message["tool_calls"]
            
            # 执行工具调用
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                
                # 尝试解析工具参数
                try:
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    print(f"Tool arguments: {tool_args}")
                except json.JSONDecodeError as e:
                    print(f"Error parsing tool arguments: {e}")
                    print(f"Raw arguments: {tool_call['function']['arguments']}")
                    tool_args = {}
                
                # 调用工具
                result = self.call_tool(tool_name, tool_args)
                print(f"Tool result: {result}")
                tool_results.append({
                    "tool_call_id": tool_call["id"],
                    "tool_name": tool_name,
                    "result": result
                })
            
            # 将工具调用添加到消息历史
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls
            })
            
            # 将工具结果添加到消息历史
            for tool_result in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_result["tool_call_id"],
                    "name": tool_result["tool_name"],
                    "content": json.dumps(tool_result["result"])
                })
            print(f"Messages after tool calls: {json.dumps(messages, indent=2)}")
            
            # 第二次查询 LLM 获取最终答案
            try:
                response = requests.post(
                    f"{self.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.llm_model,
                        "messages": messages
                    }
                )
                print(f"LLM Final Response: {response.text}")
                response.raise_for_status()
                final_response = response.json()
                
                if "choices" in final_response:
                    final_choice = final_response["choices"][0]
                    if "message" in final_choice:
                        final_message = final_choice["message"]
                        return {
                            "answer": final_message.get("content", ""),
                            "tool_results": tool_results
                        }
            except Exception as e:
                print(f"Error getting final answer: {e}")
                return {"error": str(e)}
        else:
            # 直接返回 LLM 回答
            return {
                "answer": message.get("content", "")
            }
        
        return {"error": "Unknown error occurred"}