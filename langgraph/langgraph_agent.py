from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
import sqlite3
import os
import json
import requests
import subprocess

# 配置管理
class Config:
    def __init__(self, config_file="config.env"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        config = {
            "model": {
                "type": "remote",  # remote or local
                "remote": {
                    "api_key": "your-api-key",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-3.5-turbo"
                },
                "local": {
                    "model_name": "gpt2",
                    "model_path": "./models",
                    "device": "gpu"
                }
            }
        }
        
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"')
                        
                        # 解析嵌套配置
                        if key == 'MODEL_TYPE':
                            config["model"]["type"] = value
                        elif key == 'MODEL_REMOTE_API_KEY':
                            config["model"]["remote"]["api_key"] = value
                        elif key == 'MODEL_REMOTE_BASE_URL':
                            config["model"]["remote"]["base_url"] = value
                        elif key == 'MODEL_REMOTE_MODEL':
                            config["model"]["remote"]["model"] = value
                        elif key == 'MODEL_LOCAL_MODEL_NAME':
                            config["model"]["local"]["model_name"] = value
                        elif key == 'MODEL_LOCAL_MODEL_PATH':
                            config["model"]["local"]["model_path"] = value
                        elif key == 'MODEL_LOCAL_DEVICE':
                            config["model"]["local"]["device"] = value
        else:
            # 保存默认配置
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write("# Model Configuration\n")
                f.write("MODEL_TYPE=remote\n")
                f.write("\n# Remote Model Configuration\n")
                f.write("MODEL_REMOTE_API_KEY=your-api-key\n")
                f.write("MODEL_REMOTE_BASE_URL=https://api.openai.com/v1\n")
                f.write("MODEL_REMOTE_MODEL=gpt-3.5-turbo\n")
                f.write("\n# Local Model Configuration\n")
                f.write("MODEL_LOCAL_MODEL_NAME=gpt2\n")
                f.write("MODEL_LOCAL_MODEL_PATH=./models\n")
                f.write("MODEL_LOCAL_DEVICE=gpu\n")
        
        return config

# 大模型管理器
class ModelManager:
    def __init__(self, config):
        self.config = config
        self.model_type = config["model"]["type"]
        self.model = None
        self.tokenizer = None
        self.load_model()
    
    def load_model(self):
        """加载模型"""
        if self.model_type == "remote":
            print("Using remote model")
        elif self.model_type == "local":
            print("Using local model")
            self.load_local_model()
    
    def load_local_model(self):
        """加载本地模型"""
        model_name = self.config["model"]["local"]["model_name"]
        model_path = self.config["model"]["local"]["model_path"]
        
        # 确保模型目录存在
        os.makedirs(model_path, exist_ok=True)
        
        # 构建模型存储路径，使用模型名称作为目录名
        model_dir = os.path.join(model_path, model_name.split("/")[-1])
        os.makedirs(model_dir, exist_ok=True)
        
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            # 尝试从指定目录加载模型
            print(f"Attempting to load model from: {model_dir}")
            
            # 检查目录是否为空
            if not os.listdir(model_dir):
                # 目录为空，从Hugging Face下载模型
                print(f"Model not found locally, downloading from Hugging Face: {model_name}")
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForCausalLM.from_pretrained(model_name)
                
                # 保存模型到指定目录
                print(f"Saving model to: {model_dir}")
                self.tokenizer.save_pretrained(model_dir)
                self.model.save_pretrained(model_dir)
                print("Model downloaded and saved successfully")
            else:
                # 目录不为空，从本地加载模型
                print(f"Loading model from local directory: {model_dir}")
                self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
                self.model = AutoModelForCausalLM.from_pretrained(model_dir)
                print("Model loaded successfully from local directory")
        except Exception as e:
            print(f"Error loading model: {e}")
            # 回退到简单的规则生成
            pass
    
    def generate_sql(self, user_input, table_schema):
        """生成SQL查询"""
        if self.model_type == "remote":
            return self.generate_sql_remote(user_input, table_schema)
        else:
            return self.generate_sql_local(user_input, table_schema)
    
    def generate_sql_remote(self, user_input, table_schema):
        """使用远程模型生成SQL查询"""
        remote_config = self.config["model"]["remote"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {remote_config['api_key']}"
        }
        data = {
            "model": remote_config["model"],
            "messages": [
                {
                    "role": "system",
                    "content": f"Based on the user's request, generate a SQLite query to retrieve relevant data from the processed_data table.\nThe table schema is:\n{table_schema}\nReturn only the SQL query without any explanation or markdown formatting."
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{remote_config['base_url']}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            sql = result["choices"][0]["message"]["content"].strip()
            return self.clean_sql(sql)
        except Exception as e:
            print(f"Error generating SQL with remote model: {e}")
            # 回退到简单的规则生成
            return self.generate_sql_fallback(user_input)
    
    def generate_sql_local(self, user_input, table_schema):
        """使用本地模型生成SQL查询"""
        # 直接使用回退方法，因为本地模型生成的SQL查询可能不够可靠
        return self.generate_sql_fallback(user_input)
    
    def generate_sql_fallback(self, user_input):
        """简单的回退方法，根据用户输入生成SQL查询"""
        if "all data" in user_input.lower():
            return "SELECT * FROM processed_data"
        elif "average value" in user_input.lower() and "category" in user_input.lower():
            category = user_input.split("category")[-1].strip().upper()
            return f"SELECT AVG(value) FROM processed_data WHERE category = '{category}'"
        elif "total records" in user_input.lower():
            return "SELECT COUNT(*) FROM processed_data"
        elif "highest value" in user_input.lower():
            return "SELECT MAX(value) FROM processed_data"
        else:
            return "SELECT * FROM processed_data LIMIT 10"
    
    def clean_sql(self, sql):
        """清理SQL查询，移除markdown格式化"""
        # 移除markdown格式化
        if sql.startswith("```sql") and sql.endswith("```"):
            sql = sql[6:-3].strip()
        elif sql.startswith("```") and sql.endswith("```"):
            sql = sql[3:-3].strip()
        return sql
    
    def generate_response(self, user_input, query_result):
        """生成响应"""
        if self.model_type == "remote":
            return self.generate_response_remote(user_input, query_result)
        else:
            return self.generate_response_local(user_input, query_result)
    
    def generate_response_remote(self, user_input, query_result):
        """使用远程模型生成响应"""
        remote_config = self.config["model"]["remote"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {remote_config['api_key']}"
        }
        data = {
            "model": remote_config["model"],
            "messages": [
                {
                    "role": "system",
                    "content": "Based on the user's request and the query result, generate a natural language response. If there's an error in the query result, explain the error and suggest a better approach. Otherwise, summarize the results in a clear, concise manner."
                },
                {
                    "role": "user",
                    "content": f"User request: {user_input}\nQuery result: {query_result}"
                }
            ],
            "temperature": 0.3
        }
        try:
            response = requests.post(
                f"{remote_config['base_url']}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error generating response with remote model: {e}")
            # 回退到简单的响应生成
            return self.generate_response_fallback(query_result)
    
    def generate_response_local(self, user_input, query_result):
        """使用本地模型生成响应"""
        # 直接使用回退方法，因为本地模型生成的响应可能不够可靠
        return self.generate_response_fallback(query_result)
    
    def generate_response_fallback(self, query_result):
        """简单的回退方法，根据查询结果生成响应"""
        if "error" in query_result:
            return f"Error: {query_result['error']}"
        else:
            columns = query_result.get("columns", [])
            data = query_result.get("data", [])
            if not data:
                return "No results found."
            else:
                response = f"Found {len(data)} results:\n"
                for row in data:
                    row_str = ", ".join([f"{col}: {val}" for col, val in zip(columns, row)])
                    response += f"- {row_str}\n"
                return response

# 初始化数据库
def init_database():
    """初始化数据库并插入测试数据"""
    import sqlite3
    import time
    import random
    
    # 创建SQLite数据库和表
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_data (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER,
            value REAL,
            category TEXT,
            window_time INTEGER,
            average_value REAL
        )
    ''')
    
    # 检查是否已有数据
    cursor.execute("SELECT COUNT(*) FROM processed_data")
    count = cursor.fetchone()[0]
    
    if count == 0:
        # 插入一些模拟数据
        print("Inserting test data...")
        for i in range(10):
            data = {
                "id": i + 1,
                "timestamp": int(time.time()) - i * 10,
                "value": round(random.uniform(0, 100), 2),
                "category": random.choice(["A", "B", "C", "D"])
            }
            window_time = data['timestamp'] // 10 * 10
            cursor.execute('''
                INSERT INTO processed_data (id, timestamp, value, category, window_time, average_value)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (data['id'], data['timestamp'], data['value'], data['category'], window_time, data['value']))
        conn.commit()
        print("Test data inserted successfully")
    else:
        print(f"Database already has {count} records")
    
    conn.close()

# 全局配置和模型管理器
config = Config()
model_manager = ModelManager(config.config)

# 初始化数据库
init_database()

# 表结构
TABLE_SCHEMA = """
processed_data (
    id INTEGER PRIMARY KEY,
    timestamp INTEGER,
    value REAL,
    category TEXT,
    window_time INTEGER,
    average_value REAL
)
"""

# 定义工具函数
def query_database(query):
    """查询SQLite数据库"""
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        # 获取列名
        columns = [description[0] for description in cursor.description]
        return {"columns": columns, "data": results}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

# 定义节点函数
def generate_query(state):
    """生成SQL查询"""
    last_message = state["messages"][-1].content
    query = model_manager.generate_sql(last_message, TABLE_SCHEMA)
    # 返回包含之前状态的新状态
    new_state = state.copy()
    new_state["query"] = query
    return new_state

def execute_query(state):
    """执行SQL查询"""
    query = state.get("query", "")
    if not query:
        # 返回包含之前状态的新状态
        new_state = state.copy()
        new_state["query_result"] = {"error": "No query generated"}
        return new_state
    
    result = query_database(query)
    # 返回包含之前状态的新状态
    new_state = state.copy()
    new_state["query_result"] = result
    return new_state

def generate_response(state):
    """生成响应"""
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1].content
    else:
        last_message = ""
    
    query_result = state.get("query_result", {})
    response = model_manager.generate_response(last_message, query_result)
    
    # 返回包含之前状态的新状态
    new_state = state.copy()
    new_state["messages"] = messages + [AIMessage(content=response)]
    return new_state

# 构建图
def create_agent():
    # 使用字典作为状态，而不是自定义类
    graph = StateGraph(dict)
    
    # 添加节点
    graph.add_node("generate_query", generate_query)
    graph.add_node("execute_query", execute_query)
    graph.add_node("generate_response", generate_response)
    
    # 添加边
    graph.add_edge(START, "generate_query")
    graph.add_edge("generate_query", "execute_query")
    graph.add_edge("execute_query", "generate_response")
    graph.add_edge("generate_response", END)
    
    # 编译图
    return graph.compile()

# 主函数
def main():
    agent = create_agent()
    
    print("LangGraph Data Analysis Agent")
    print("Type 'exit' to quit")
    
    # 测试模式：如果有命令行参数，直接使用第一个参数作为查询
    import sys
    if len(sys.argv) > 1:
        user_input = ' '.join(sys.argv[1:])
        # 运行代理
        result = agent.invoke({
            "messages": [HumanMessage(content=user_input)]
        })
        
        # 打印响应
        print("\nAgent Response:")
        print(result["messages"][-1].content)
        return
    
    while True:
        user_input = input("\nEnter your query: ")
        if user_input.lower() == 'exit':
            break
        
        # 运行代理
        result = agent.invoke({
            "messages": [HumanMessage(content=user_input)]
        })
        
        # 打印响应
        print("\nAgent Response:")
        print(result["messages"][-1].content)

if __name__ == "__main__":
    main()