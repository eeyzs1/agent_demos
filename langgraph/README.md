# LangGraph数据分析应用

这是一个使用LangGraph、PyFlink和SQLite构建的智能数据分析系统，能够通过自然语言查询分析数据流。

## 项目结构

```
langgraph/
├── data_generator.py     # 数据生成器，生成模拟数据流
├── flink_processor.py    # Flink处理器，处理数据流并存储到SQLite
├── langgraph_agent.py    # LangGraph代理，用于查询和分析数据
├── main.py               # 主脚本，启动所有组件
├── requirements.txt      # 依赖文件
├── config.env            # 配置文件
└── README.md             # 项目说明
```

## 功能特性

1. **数据生成**：生成包含id、timestamp、value和category字段的模拟数据流
2. **数据处理**：使用PyFlink处理数据流，将结果存储到SQLite数据库
3. **智能查询**：使用LangGraph构建智能代理，通过自然语言查询分析数据
4. **模型支持**：支持远程模型（如OpenAI）和本地模型（如GPT-2）
5. **容错处理**：当PyFlink导入失败时，运行在模拟模式，确保应用程序能够正常运行
6. **配置管理**：通过config.env文件管理模型配置

## 技术栈

- **LangGraph**：构建智能代理，处理自然语言查询
- **PyFlink**：处理流式数据
- **SQLite**：存储处理后的数据
- **Transformers**：加载和使用本地模型
- **Requests**：调用远程模型API

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

编辑`config.env`文件，设置以下参数：

### 模型配置
- `MODEL_TYPE`：模型类型，可选值：`remote`或`local`

### 远程模型配置
- `MODEL_REMOTE_API_KEY`：远程模型API密钥
- `MODEL_REMOTE_BASE_URL`：远程模型API基础URL
- `MODEL_REMOTE_MODEL`：远程模型名称

### 本地模型配置
- `MODEL_LOCAL_MODEL_NAME`：本地模型名称（如`gpt2`）
- `MODEL_LOCAL_MODEL_PATH`：本地模型存储路径
- `MODEL_LOCAL_DEVICE`：设备类型，可选值：`cpu`或`gpu`

## 使用方法

1. **启动应用程序**：
   ```bash
   python main.py
   ```

2. **应用程序启动流程**：
   - 首先启动Flink处理器，初始化数据库并准备接收数据
   - 然后启动数据生成器，生成模拟数据流并发送给Flink处理器
   - 最后启动LangGraph代理，等待用户输入自然语言查询

3. **输入自然语言查询**，例如：
   - "Show me all data points"
   - "What's the average value for category A"
   - "How many records are there in total?"
   - "What's the highest value recorded?"

4. **输入'exit'退出应用程序**。

## 数据流处理

1. **数据生成**：`data_generator.py`生成模拟数据，每秒生成一条包含id、timestamp、value和category字段的数据
2. **数据传输**：数据通过socket发送给Flink处理器
3. **数据处理**：`flink_processor.py`接收数据，计算窗口平均值，并存储到SQLite数据库
4. **数据查询**：`langgraph_agent.py`通过自然语言查询分析数据库中的数据

## 模型使用

### 远程模型
- 使用配置的API密钥和基础URL调用远程模型（如OpenAI API）
- 生成SQL查询和自然语言响应

### 本地模型
- 从Hugging Face下载模型到指定目录
- 本地加载模型，生成SQL查询和自然语言响应
- 模型会缓存到本地，避免重复下载

## 容错处理

- 当PyFlink导入失败时，自动运行在模拟模式，确保应用程序能够正常运行
- 当模型生成失败时，回退到简单的规则生成，确保查询能够正常执行

## 示例查询

- **查询所有数据**："Show me all data points"
- **按类别查询平均值**："What's the average value for category A"
- **查询总记录数**："How many records are there in total?"
- **查询最高值**："What's the highest value recorded?"

## 注意事项

- 首次运行本地模型时，会从Hugging Face下载模型，可能需要一些时间
- 使用远程模型时，需要确保API密钥和基础URL配置正确
- 应用程序默认使用SQLite数据库，存储在当前目录的`data.db`文件中

## 扩展建议

1. **使用真实的消息队列**：将socket连接替换为Kafka等真实的消息队列，提高系统的可靠性和可扩展性
2. **添加更多的查询模式**：扩展LangGraph代理的查询能力，支持更复杂的查询和分析
3. **添加数据可视化**：集成数据可视化工具，将查询结果以图表形式展示
4. **使用更强大的本地模型**：使用更大、更强大的本地模型，提高SQL查询和响应生成的质量
5. **优化数据处理**：增加更复杂的数据处理逻辑，如窗口计算、聚合操作等

## 许可证

本项目采用MIT许可证。