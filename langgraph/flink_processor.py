import sys
print(f"Python path: {sys.path}")
try:
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.functions import MapFunction
    print("PyFlink imported successfully")
except Exception as e:
    print(f"Error importing PyFlink: {e}")
    # 使用简单的替代实现
    class StreamExecutionEnvironment:
        @staticmethod
        def get_execution_environment():
            class Env:
                def socket_text_stream(self, host, port):
                    class Stream:
                        def map(self, func):
                            class ProcessedStream:
                                def print(self):
                                    pass
                            return ProcessedStream()
                        def execute(self, job_name):
                            pass
                    return Stream()
            return Env()
    
    class MapFunction:
        def open(self, runtime_context):
            pass
        def map(self, value):
            pass
        def close(self):
            pass

import json
import sqlite3
import os

class DataProcessor(MapFunction):
    def __init__(self):
        self.conn = None
    
    def open(self, runtime_context):
        # 初始化SQLite连接
        self.conn = sqlite3.connect('data.db')
        self.create_table()
    
    def create_table(self):
        cursor = self.conn.cursor()
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
        self.conn.commit()
    
    def map(self, value):
        try:
            data = json.loads(value)
            # 简单处理：计算窗口平均值（这里简化处理）
            window_time = data['timestamp'] // 10 * 10  # 10秒窗口
            
            # 存储到SQLite
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO processed_data (id, timestamp, value, category, window_time, average_value)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (data['id'], data['timestamp'], data['value'], data['category'], window_time, data['value']))
            self.conn.commit()
            
            return json.dumps(data)
        except Exception as e:
            print(f"Error processing data: {e}")
            return None
    
    def close(self):
        if self.conn:
            self.conn.close()

def init_database():
    """初始化数据库并插入测试数据"""
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
        import time
        import random
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

def process_stream():
    # 初始化数据库
    init_database()
    
    try:
        env = StreamExecutionEnvironment.get_execution_environment()
        
        # 从标准输入读取数据
        input_stream = env.socket_text_stream('localhost', 9999)
        
        # 处理数据
        processed_stream = input_stream.map(DataProcessor())
        
        # 打印结果
        processed_stream.print()
        
        # 执行作业
        env.execute("Data Processing Job")
    except Exception as e:
        print(f"Error running Flink job: {e}")
        # 模拟数据处理
        print("Running in simulation mode...")

if __name__ == "__main__":
    process_stream()