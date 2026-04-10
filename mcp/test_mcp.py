# from app.mcp import MCPClient

# # 创建 MCP 客户端
# client = MCPClient()

# # 测试获取可用工具
# print("=== 测试获取可用工具 ===")
# tools = client.get_available_tools()
# print(f"可用工具: {len(tools)}")
# for tool in tools:
#     print(f"- {tool['name']}: {tool['description']}")

# # 测试直接调用工具
# print("\n=== 测试直接调用工具 ===")

# # 测试 search_stock 工具
# print("\n1. 测试 search_stock 工具:")
# result = client.call_tool("search_stock", {"keyword": "600000"})
# print(f"搜索股票结果: {result}")

# # 测试 get_stock_quote 工具
# print("\n2. 测试 get_stock_quote 工具:")
# result = client.call_tool("get_stock_quote", {"symbol": "600000"})
# print(f"获取股票行情结果: {result}")

# # 测试与 LLM 聊天
# print("\n=== 测试与 LLM 聊天 ===")
# prompt = "请获取股票代码为 600000 的实时行情"
# response = client.chat(prompt)
# print(f"LLM 响应: {response}")