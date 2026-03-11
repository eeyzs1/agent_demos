import subprocess
import time
import os
import signal
import sys

def start_process(command, description):
    """启动进程并返回进程对象"""
    print(f"Starting {description}...")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        # 打印启动信息
        print(f"{description} started with PID: {process.pid}")
        return process
    except Exception as e:
        print(f"Error starting {description}: {e}")
        return None

def print_process_output(process, description):
    """打印进程输出"""
    if process:
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(f"[{description}] {line.strip()}")
        except Exception as e:
            print(f"Error reading {description} output: {e}")

def terminate_process(process, description):
    """终止进程"""
    if process:
        try:
            print(f"Terminating {description}...")
            process.terminate()
            process.wait(timeout=5)
            print(f"{description} terminated")
        except Exception as e:
            print(f"Error terminating {description}: {e}")

def main():
    print("Starting LangGraph Data Analysis App...")
    
    # 启动Flink处理器
    flink_processor = start_process(
        ["python", "flink_processor.py"],
        "Flink processor"
    )
    
    # 等待一会儿，确保Flink处理器正常运行
    time.sleep(5)
    
    # 启动数据生成器
    data_generator = start_process(
        ["python", "data_generator.py"],
        "data generator"
    )
    
    # 等待一会儿，确保数据生成器正常运行
    time.sleep(2)
    
    # 启动LangGraph代理
    print("Starting LangGraph agent...")
    langgraph_agent = subprocess.run(
        ["python", "langgraph_agent.py"]
    )
    
    # 清理进程
    terminate_process(data_generator, "data generator")
    terminate_process(flink_processor, "Flink processor")

if __name__ == "__main__":
    main()