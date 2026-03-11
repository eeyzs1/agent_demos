import json
import time
import random
import socket

def generate_data():
    """生成模拟数据流"""
    while True:
        data = {
            "id": random.randint(1, 10000),
            "timestamp": int(time.time()),
            "value": round(random.uniform(0, 100), 2),
            "category": random.choice(["A", "B", "C", "D"])
        }
        yield data
        time.sleep(1)  # 每1秒生成一条数据

def send_data_to_socket():
    """将数据发送到socket"""
    while True:
        try:
            # 创建socket连接
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('localhost', 9999))
            print("Connected to Flink processor")
            
            try:
                for data in generate_data():
                    s.send((json.dumps(data) + '\n').encode('utf-8'))
            except Exception as e:
                print(f"Error sending data: {e}")
            finally:
                s.close()
        except ConnectionRefusedError:
            print("Flink processor not ready, waiting...")
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    send_data_to_socket()