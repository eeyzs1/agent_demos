import akshare as ak
import pandas as pd
import requests
from typing import List, Dict, Optional

class StockData:
    """股票数据获取类"""
    
    def __init__(self):
        # 缓存股票列表，避免重复请求
        self.stock_list_cache = None
    
    def _get_stock_list(self) -> pd.DataFrame:
        """获取股票列表并缓存"""
        if self.stock_list_cache is None:
            try:
                print("正在获取股票列表...")
                # 使用 akshare 获取股票实时行情
                self.stock_list_cache = ak.stock_zh_a_spot()
                print(f"获取成功，共 {len(self.stock_list_cache)} 条数据")
                # 确保数据包含所有必要的列
                required_columns = ['代码', '名称', '最新价', '涨跌额', '涨跌幅', '买入', '卖出', '昨收', '今开', '最高', '最低', '成交量', '成交额', '时间戳']
                for col in required_columns:
                    if col not in self.stock_list_cache.columns:
                        print(f"警告: 数据缺少列 {col}")
                # 打印前几行数据，确认数据格式正确
                print("数据前 5 行:")
                print(self.stock_list_cache.head())
            except Exception as e:
                print(f"获取股票列表失败: {e}")
                # 如果获取失败，使用模拟数据
                print("使用模拟数据...")
                self.stock_list_cache = pd.DataFrame({
                    '代码': ['sh600000', 'sz000001', 'sh600519', 'bj920000'],
                    '名称': ['浦发银行', '平安银行', '贵州茅台', '安徽凤凰'],
                    '最新价': [10.28, 12.34, 1800.0, 15.81],
                    '涨跌额': [-0.04, 0.12, 5.0, -0.47],
                    '涨跌幅': [-0.388, 0.98, 0.278, -2.887],
                    '买入': [10.28, 12.33, 1799.0, 15.81],
                    '卖出': [10.29, 12.35, 1801.0, 15.97],
                    '昨收': [10.32, 12.22, 1795.0, 16.28],
                    '今开': [10.33, 12.25, 1798.0, 16.28],
                    '最高': [10.46, 12.40, 1805.0, 16.69],
                    '最低': [10.28, 12.20, 1790.0, 15.59],
                    '成交量': [74883607.0, 56789012.0, 1234567.0, 564457.0],
                    '成交额': [776364417.0, 699876543.0, 2222222222.0, 9126099.0],
                    '时间戳': ['15:00:03', '15:00:03', '15:00:03', '15:30:01']
                })
        return self.stock_list_cache

    def get_stock_list(self) -> List[Dict]:
        """获取A股股票列表"""
        try:
            stock_list = self._get_stock_list()
            if stock_list.empty:
                return [{'error': '获取股票列表失败'}]
            return stock_list.to_dict('records')
        except Exception as e:
            print(f"get_stock_list 错误: {e}")
            return [{'error': str(e)}]
    
    def get_stock_quote(self, symbol: str) -> Dict:
        """获取股票实时行情"""
        try:
            print(f"正在获取股票 {symbol} 的实时行情...")
            stock_quote = self._get_stock_list()
            
            if stock_quote.empty:
                return {'error': '获取股票数据失败'}
            
            # 尝试直接匹配
            stock_data = stock_quote[stock_quote['代码'] == symbol]
            if not stock_data.empty:
                result = stock_data.iloc[0].to_dict()
                print(f"获取成功: {result['名称']} - {result['最新价']}")
                return result
            
            # 如果直接匹配失败，尝试添加交易所前缀
            if not symbol.startswith(('sh', 'sz')):
                # 尝试添加 sh 前缀
                sh_symbol = f'sh{symbol}'
                stock_data = stock_quote[stock_quote['代码'] == sh_symbol]
                if not stock_data.empty:
                    result = stock_data.iloc[0].to_dict()
                    print(f"获取成功: {result['名称']} - {result['最新价']}")
                    return result
                
                # 尝试添加 sz 前缀
                sz_symbol = f'sz{symbol}'
                stock_data = stock_quote[stock_quote['代码'] == sz_symbol]
                if not stock_data.empty:
                    result = stock_data.iloc[0].to_dict()
                    print(f"获取成功: {result['名称']} - {result['最新价']}")
                    return result
            
            print(f"股票代码 {symbol} 不存在")
            return {'error': '股票代码不存在'}
        except Exception as e:
            print(f"get_stock_quote 错误: {e}")
            return {'error': str(e)}
    
    def get_stock_history(self, symbol: str, start_date: str, end_date: str, period: str = 'daily') -> List[Dict]:
        """获取股票历史数据"""
        try:
            print(f"正在获取股票 {symbol} 的历史数据...")
            if period == 'daily':
                stock_history = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date, end_date=end_date)
            elif period == 'weekly':
                stock_history = ak.stock_zh_a_weekly(symbol=symbol, start_date=start_date, end_date=end_date)
            elif period == 'monthly':
                stock_history = ak.stock_zh_a_monthly(symbol=symbol, start_date=start_date, end_date=end_date)
            else:
                return [{'error': '不支持的周期类型'}]
            
            result = stock_history.reset_index().to_dict('records')
            print(f"获取成功，共 {len(result)} 条数据")
            return result
        except Exception as e:
            print(f"get_stock_history 错误: {e}")
            return [{'error': str(e)}]
    
    def search_stock(self, keyword: str) -> List[Dict]:
        """根据关键词搜索股票"""
        try:
            print(f"正在搜索关键词 {keyword} 的股票...")
            stock_list = self._get_stock_list()
            
            if stock_list.empty:
                return [{'error': '获取股票数据失败'}]
            
            result = stock_list[(stock_list['代码'].str.contains(keyword)) | (stock_list['名称'].str.contains(keyword))]
            result_list = result.to_dict('records')
            print(f"搜索成功，共 {len(result_list)} 条结果")
            return result_list
        except Exception as e:
            print(f"search_stock 错误: {e}")
            return [{'error': str(e)}]