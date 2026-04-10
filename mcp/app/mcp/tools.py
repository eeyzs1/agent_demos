from app.stock import StockData

stock_data = StockData()

stock_tools = [
    {
        "name": "get_stock_list",
        "description": "获取A股股票列表",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "function": stock_data.get_stock_list
    },
    {
        "name": "get_stock_quote",
        "description": "获取股票实时行情",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码，例如：600000"
                }
            },
            "required": ["symbol"]
        },
        "function": stock_data.get_stock_quote
    },
    {
        "name": "get_stock_history",
        "description": "获取股票历史数据",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码，例如：600000"
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期，格式：YYYY-MM-DD"
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期，格式：YYYY-MM-DD"
                },
                "period": {
                    "type": "string",
                    "description": "周期类型：daily, weekly, monthly",
                    "default": "daily"
                }
            },
            "required": ["symbol", "start_date", "end_date"]
        },
        "function": stock_data.get_stock_history
    },
    {
        "name": "search_stock",
        "description": "根据关键词搜索股票",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，可以是股票代码或名称"
                }
            },
            "required": ["keyword"]
        },
        "function": stock_data.search_stock
    }
]