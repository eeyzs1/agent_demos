import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 研究 akshare 接口的返回值
def research_akshare():
    print("=== 研究 akshare 接口 ===")
    try:
        # 调用 akshare 获取股票列表
        print("调用 ak.stock_zh_a_spot()...")
        stock_data = ak.stock_zh_a_spot()
        print(f"获取成功，返回类型: {type(stock_data)}")
        
        # 检查返回数据的结构
        if isinstance(stock_data, pd.DataFrame):
            print(f"DataFrame 形状: {stock_data.shape}")
            print("\n列名:")
            print(stock_data.columns.tolist())
            print("\n前 5 行数据:")
            print(stock_data.head())
            print("\n数据类型:")
            print(stock_data.dtypes)
        else:
            print(f"意外的返回类型: {type(stock_data)}")
            print(f"返回值: {stock_data}")
    except Exception as e:
        print(f"调用 akshare 失败: {e}")
        
        # 尝试直接请求新浪接口
        print("\n=== 尝试直接请求新浪接口 ===")
        try:
            url = "http://vip.stock.finance.sina.com.cn/mkt/#hs_a"
            response = requests.get(url)
            print(f"HTTP 状态码: {response.status_code}")
            print(f"响应内容长度: {len(response.text)}")
            
            # 保存响应内容到文件，以便分析
            with open("sina_response.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("\n响应内容已保存到 sina_response.html 文件")
            
            # 尝试解析 HTML
            print("\n=== 尝试解析 HTML ===")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找表格
            tables = soup.find_all('table')
            print(f"找到 {len(tables)} 个表格")
            
            if tables:
                # 分析第一个表格
                table = tables[0]
                print("\n第一个表格的结构:")
                
                # 提取表头
                header_row = table.find('tr')
                if header_row:
                    headers = [th.text.strip() for th in header_row.find_all('th')]
                    print(f"表头: {headers}")
                
                # 提取前几行数据
                rows = table.find_all('tr')[1:4]  # 跳过表头，取前3行
                print("\n前 3 行数据:")
                for i, row in enumerate(rows):
                    cells = [td.text.strip() for td in row.find_all('td')]
                    print(f"第 {i+1} 行: {cells}")
        except Exception as e2:
            print(f"请求新浪接口失败: {e2}")

if __name__ == "__main__":
    research_akshare()