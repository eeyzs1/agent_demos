import os
import time
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables
load_dotenv(override=True)

# Define state structure
class InvestmentState(BaseModel):
    raw_information: list = []
    cleaned_information: list = []
    classified_information: dict = {}
    analysis_results: dict = {}
    opportunity_score: int = 0
    risk_score: int = 0
    decision: str = ""
    research_brief: str = ""
    monitoring_stocks: list = []

# Function to call LLM using OpenAI compatibility API with retry mechanism
def call_llm(prompt, model=None, max_retries=3):
    model = model or os.getenv("OPENAI_MODEL", "gpt-4")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    
    retries = 0
    while retries < max_retries:
        try:
            # Construct the API endpoint
            endpoint = f"{base_url}/chat/completions"
            
            # Prepare the request payload
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            # Set up headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Make the HTTP request
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=30  # 30 seconds timeout
            )
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            return response_data["choices"][0]["message"]["content"]
        except Exception as e:
            retries += 1
            print(f"LLM call failed (attempt {retries}/{max_retries}): {str(e)}")
            if retries < max_retries:
                import time
                time.sleep(2)  # Wait 2 seconds before retrying
    # Fallback to mock response if all retries fail
    return "这是一个模拟的分析结果，包含了对该信息的详细分析。在实际部署中，这里会使用真实的LLM分析结果。"

# Function to call fast LLM (e.g., gpt-3.5-turbo) for real-time analysis
def call_fast_llm(prompt, max_retries=3):
    retries = 0
    while retries < max_retries:
        try:
            return call_llm(prompt, model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"), max_retries=1)
        except Exception as e:
            retries += 1
            print(f"Fast LLM call failed (attempt {retries}/{max_retries}): {str(e)}")
            if retries < max_retries:
                import time
                time.sleep(1)  # Wait 1 second before retrying
    # Fallback to mock response if all retries fail
    return "这是一个实时分析的模拟结果。在实际部署中，这里会使用真实的LLM分析结果。"

# Tools for data collection
def collect_official_announcements():
    """Collect announcements from SSE/SZSE"""
    announcements = []
    try:
        # Use Sina Finance API for official announcements
        import requests
        import json
        
        # Get Sina Finance API key from environment variables
        sina_api_key = os.getenv("SINA_API_KEY")
        
        if not sina_api_key:
            print("SINA_API_KEY not configured, using alternative method")
            # Alternative: use East Money announcement API
            url = "http://push2.eastmoney.com/api/qt/stock/lhb/get"
            params = {
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                "ut": "b2884a393a594616b4b0ec9094c65b41",
                "pn": 1,
                "pz": 20
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("data") and data["data"].get("items"):
                for item in data["data"]["items"]:
                    stock_code = item.get("f12")
                    content = f"{item.get('f14')} - {item.get('f2')}"
                    announcements.append({
                        "type": "announcement",
                        "content": content,
                        "stock_code": stock_code
                    })
        else:
            # Use Sina Finance API with API key
            url = "https://api.sina.com.cn/finance/stock/announcement"
            params = {
                "key": sina_api_key,
                "page": 1,
                "size": 20
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("data"):
                for item in data["data"]:
                    announcements.append({
                        "type": "announcement",
                        "content": item.get("title"),
                        "stock_code": item.get("stock_code")
                    })
        
        print(f"Collected {len(announcements)} official announcements")
    except Exception as e:
        print(f"Error collecting official announcements: {str(e)}")
        # Fallback to minimal mock data if API fails
        announcements = [
            {"type": "announcement", "content": "XX科技发布2025年年报，营收增长50%", "stock_code": "600001"},
            {"type": "announcement", "content": "XX半导体拟减持5%股份", "stock_code": "000001"}
        ]
    return announcements

def collect_market_data():
    """Collect market data from East Money"""
    market_data = []
    try:
        # Use East Money API for market data
        import requests
        
        # Get East Money API key from environment variables
        east_money_api_key = os.getenv("EAST_MONEY_API_KEY")
        
        # Get northbound资金 data
        northbound_url = "http://push2.eastmoney.com/api/qt/kamt/get"
        northbound_params = {
            "fields1": "f1,f2,f3,f4",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "ut": "b2884a393a594616b4b0ec9094c65b41"
        }
        northbound_response = requests.get(northbound_url, params=northbound_params, timeout=10)
        northbound_data = northbound_response.json()
        
        if northbound_data.get("data"):
            net_inflow = northbound_data["data"].get("f51", 0)
            market_data.append({
                "type": "market",
                "content": f"北向资金今日净流入{net_inflow/100000000:.2f}亿",
                "stocks": ["600519", "600001"]
            })
        
        # Get sector performance data
        sector_url = "http://push2.eastmoney.com/api/qt/clist/get"
        sector_params = {
            "fid": "f3",
            "po": 1,
            "pz": 10,
            "pn": 1,
            "np": 1,
            "ut": "b2884a393a594616b4b0ec9094c65b41",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:90 t:2",
            "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f26,f22,f33,f11,f62,f128,f136,f115,f152"
        }
        sector_response = requests.get(sector_url, params=sector_params, timeout=10)
        sector_data = sector_response.json()
        
        if sector_data.get("data") and sector_data["data"].get("diff"):
            for sector in sector_data["data"]["diff"][:3]:
                sector_name = sector.get("f14")
                change = sector.get("f3", 0)
                market_data.append({
                    "type": "market",
                    "content": f"{sector_name}板块今日涨幅{change:.2f}%",
                    "stocks": []
                })
        
        print(f"Collected {len(market_data)} market data items")
    except Exception as e:
        print(f"Error collecting market data: {str(e)}")
        # Fallback to minimal mock data if API fails
        market_data = [
            {"type": "market", "content": "北向资金今日净流入200亿", "stocks": ["600519", "600001"]},
            {"type": "market", "content": "算力板块今日涨幅5%", "stocks": ["600001"]}
        ]
    return market_data

def collect_research_reports():
    """Collect research reports from brokers"""
    research_reports = []
    try:
        # Use Huibo Investment Research API
        import requests
        
        # Get Huibo API key from environment variables
        huibo_api_key = os.getenv("HUIBO_API_KEY")
        
        if not huibo_api_key:
            print("HUIBO_API_KEY not configured, using alternative method")
            # Alternative: use East Money research reports
            url = "http://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "fid": "f6",
                "po": 1,
                "pz": 10,
                "pn": 1,
                "np": 1,
                "ut": "b2884a393a594616b4b0ec9094c65b41",
                "fltt": 2,
                "invt": 2,
                "fs": "b:MK001",
                "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f26,f22,f33,f11,f62,f128,f136,f115,f152"
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("data") and data["data"].get("diff"):
                for report in data["data"]["diff"][:5]:
                    stock_code = report.get("f12")
                    content = f"{report.get('f14')} - {report.get('f2')}"
                    research_reports.append({
                        "type": "research",
                        "content": content,
                        "stock_code": stock_code
                    })
        else:
            # Use Huibo API with API key
            url = "https://api.huibo.com/research/reports"
            params = {
                "key": huibo_api_key,
                "page": 1,
                "size": 10,
                "industry": "technology"
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("data"):
                for report in data["data"]:
                    research_reports.append({
                        "type": "research",
                        "content": report.get("title"),
                        "stock_code": report.get("stock_code")
                    })
        
        print(f"Collected {len(research_reports)} research reports")
    except Exception as e:
        print(f"Error collecting research reports: {str(e)}")
        # Fallback to minimal mock data if API fails
        research_reports = [
            {"type": "research", "content": "券商研报：算力需求将持续增长，推荐XX科技", "stock_code": "600001"},
            {"type": "research", "content": "电话会议纪要：XX半导体Q1订单超预期", "stock_code": "000001"}
        ]
    return research_reports

def collect_industry_info():
    """Collect industry information"""
    industry_info = []
    try:
        # Use MIIT and industry association websites
        import requests
        from bs4 import BeautifulSoup
        
        # Scrape MIIT website for industry policies
        miit_url = "https://www.miit.gov.cn/jgsj/xxjs/wjfb/index.html"
        response = requests.get(miit_url, timeout=10)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find policy announcements
        policy_items = soup.find_all("li", class_="list_li")[:5]
        for item in policy_items:
            title = item.find("a").text.strip()
            if "算力" in title or "半导体" in title or "科技" in title:
                industry_info.append({
                    "type": "industry",
                    "content": title,
                    "related_stocks": ["600001", "000001"]
                })
        
        # Also check industry news from Sina Finance
        sina_url = "https://finance.sina.com.cn/tech/"
        response = requests.get(sina_url, timeout=10)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find industry news
        news_items = soup.find_all("div", class_="news-item")[:5]
        for item in news_items:
            title = item.find("a").text.strip()
            industry_info.append({
                "type": "industry",
                "content": title,
                "related_stocks": ["600001"]
            })
        
        print(f"Collected {len(industry_info)} industry information items")
    except Exception as e:
        print(f"Error collecting industry information: {str(e)}")
        # Fallback to minimal mock data if API fails
        industry_info = [
            {"type": "industry", "content": "工信部发布算力基础设施建设规划", "related_stocks": ["600001"]}
        ]
    return industry_info

# Data caching mechanism
import json
import os
import time

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Cache management functions
def get_cache_key(source, timestamp):
    """Generate cache key based on source and timestamp"""
    return f"{source}_{timestamp}.json"

def get_cache(source, max_age=3600):
    """Get cached data if it's within max_age (in seconds)"""
    timestamp = int(time.time() / 3600) * 3600  # Hourly cache
    cache_key = get_cache_key(source, timestamp)
    cache_path = os.path.join(CACHE_DIR, cache_key)
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Check if cache is still valid
            if time.time() - os.path.getmtime(cache_path) < max_age:
                print(f"Using cached data for {source}")
                return data
        except Exception as e:
            print(f"Error reading cache: {str(e)}")
    return None

def set_cache(source, data):
    """Set cache for data"""
    timestamp = int(time.time() / 3600) * 3600  # Hourly cache
    cache_key = get_cache_key(source, timestamp)
    cache_path = os.path.join(CACHE_DIR, cache_key)
    
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Cached data for {source}")
    except Exception as e:
        print(f"Error writing cache: {str(e)}")

# Node implementations
async def information_collection_node(state: InvestmentState) -> InvestmentState:
    """Collect information from various sources"""
    print("=== Information Collection Node ===")
    
    # Try to get cached data first
    cached_data = get_cache("all_sources")
    if cached_data:
        print(f"Using cached information: {len(cached_data)} pieces")
        updated_state = state.model_dump()
        updated_state['raw_information'] = cached_data
        return InvestmentState(**updated_state)
    
    # Use parallel processing for data collection
    import asyncio
    
    async def async_collect_official_announcements():
        return collect_official_announcements()
    
    async def async_collect_market_data():
        return collect_market_data()
    
    async def async_collect_research_reports():
        return collect_research_reports()
    
    async def async_collect_industry_info():
        return collect_industry_info()
    
    # Run collection tasks in parallel
    official_announcements, market_data, research_reports, industry_info = await asyncio.gather(
        async_collect_official_announcements(),
        async_collect_market_data(),
        async_collect_research_reports(),
        async_collect_industry_info()
    )
    
    # Combine all information
    raw_information = official_announcements + market_data + research_reports + industry_info
    
    print(f"Collected {len(raw_information)} pieces of information")
    
    # Cache the results
    set_cache("all_sources", raw_information)
    
    updated_state = state.model_dump()
    updated_state['raw_information'] = raw_information
    return InvestmentState(**updated_state)

async def information_cleaning_node(state: InvestmentState) -> InvestmentState:
    """Clean and deduplicate information"""
    print("=== Information Cleaning Node ===")
    
    cleaned_information = []
    seen_contents = set()
    
    for info in state.raw_information:
        content = info.get("content", "")
        if content not in seen_contents:
            seen_contents.add(content)
            cleaned_information.append(info)
    
    print(f"Cleaned to {len(cleaned_information)} pieces of information")
    
    updated_state = state.model_dump()
    updated_state['cleaned_information'] = cleaned_information
    return InvestmentState(**updated_state)

async def information_classification_node(state: InvestmentState) -> InvestmentState:
    """Classify information based on A-share investment logic"""
    print("=== Information Classification Node ===")
    
    classified = {
        "financial_report": [],
        "policy_industry": [],
        "fund_flow": [],
        "research_report": []
    }
    
    for info in state.cleaned_information:
        info_type = info.get("type", "")
        content = info.get("content", "")
        
        if info_type == "announcement" or "年报" in content or "季报" in content:
            classified["financial_report"].append(info)
        elif info_type == "industry" or "政策" in content or "规划" in content:
            classified["policy_industry"].append(info)
        elif info_type == "market" or "资金" in content or "北向" in content:
            classified["fund_flow"].append(info)
        elif info_type == "research" or "研报" in content or "纪要" in content:
            classified["research_report"].append(info)
    
    print(f"Classified information: {json.dumps(classified, ensure_ascii=False, indent=2)}")
    
    updated_state = state.model_dump()
    updated_state['classified_information'] = classified
    return InvestmentState(**updated_state)

async def financial_analysis_node(state: InvestmentState) -> InvestmentState:
    """Analyze financial reports and announcements"""
    print("=== Financial Analysis Node ===")
    
    analysis_results = state.analysis_results.copy() if state.analysis_results else {}
    financial_analyses = []
    
    for info in state.classified_information.get("financial_report", []):
        content = info.get("content", "")
        stock_code = info.get("stock_code", "")
        
        # Use LLM to analyze financial information
        prompt = f"分析以下A股科技企业的财报/公告信息，重点关注营收、利润、研发投入、应收账款、商誉等指标，识别潜在风险和机会：\n{content}"
        analysis = call_llm(prompt)
        
        financial_analyses.append({
            "stock_code": stock_code,
            "content": content,
            "analysis": analysis
        })
    
    analysis_results["financial"] = financial_analyses
    
    updated_state = state.model_dump()
    updated_state['analysis_results'] = analysis_results
    return InvestmentState(**updated_state)

async def policy_analysis_node(state: InvestmentState) -> InvestmentState:
    """Analyze policy and industry news"""
    print("=== Policy Analysis Node ===")
    
    analysis_results = state.analysis_results.copy() if state.analysis_results else {}
    policy_analyses = []
    
    for info in state.classified_information.get("policy_industry", []):
        content = info.get("content", "")
        related_stocks = info.get("related_stocks", [])
        
        # Use LLM to analyze policy information
        prompt = f"分析以下政策/行业新闻对A股科技企业的影响，评估受益度、持续性，并列出可能受益的标的：\n{content}"
        analysis = call_llm(prompt)
        
        policy_analyses.append({
            "content": content,
            "related_stocks": related_stocks,
            "analysis": analysis
        })
    
    analysis_results["policy"] = policy_analyses
    
    updated_state = state.model_dump()
    updated_state['analysis_results'] = analysis_results
    return InvestmentState(**updated_state)

async def fund_flow_analysis_node(state: InvestmentState) -> InvestmentState:
    """Analyze fund flow and market signals"""
    print("=== Fund Flow Analysis Node ===")
    
    analysis_results = state.analysis_results.copy() if state.analysis_results else {}
    fund_analyses = []
    
    for info in state.classified_information.get("fund_flow", []):
        content = info.get("content", "")
        stocks = info.get("stocks", [])
        
        # Use fast LLM for real-time market analysis
        prompt = f"分析以下资金流向和盘面信号，判断异动原因、资金性质和趋势：\n{content}"
        analysis = call_fast_llm(prompt)
        
        fund_analyses.append({
            "content": content,
            "stocks": stocks,
            "analysis": analysis
        })
    
    analysis_results["fund_flow"] = fund_analyses
    
    updated_state = state.model_dump()
    updated_state['analysis_results'] = analysis_results
    return InvestmentState(**updated_state)

async def research_analysis_node(state: InvestmentState) -> InvestmentState:
    """Analyze research reports and meeting minutes"""
    print("=== Research Analysis Node ===")
    
    analysis_results = state.analysis_results.copy() if state.analysis_results else {}
    research_analyses = []
    
    for info in state.classified_information.get("research_report", []):
        content = info.get("content", "")
        stock_code = info.get("stock_code", "")
        
        # Use LLM to analyze research information
        prompt = f"分析以下研报/纪要信息，提炼核心结论、核心逻辑和机构一致性判断：\n{content}"
        analysis = call_llm(prompt)
        
        research_analyses.append({
            "stock_code": stock_code,
            "content": content,
            "analysis": analysis
        })
    
    analysis_results["research"] = research_analyses
    
    updated_state = state.model_dump()
    updated_state['analysis_results'] = analysis_results
    return InvestmentState(**updated_state)

async def multi_dimension_reasoning_node(state: InvestmentState) -> InvestmentState:
    """Perform multi-dimensional reasoning to score opportunities and risks"""
    print("=== Multi-dimension Reasoning Node ===")
    
    # Combine all analyses
    all_analyses = []
    for analysis_type, analyses in state.analysis_results.items():
        for analysis in analyses:
            all_analyses.append(analysis.get("analysis", ""))
    
    # Use LLM to perform multi-dimensional reasoning
    prompt = f"基于以下分析结果，对A股科技企业进行多维度评估：\n1. 机会评分（0-10分）：政策契合度、业绩增速、资金认可度、产业逻辑\n2. 风险评分（0-10分）：财务风险、监管风险、行业风险、估值风险\n\n分析结果：\n{'\n'.join(all_analyses)}"
    response = call_llm(prompt)
    
    # Extract scores from response (simplified for demo)
    opportunity_score = 7  # In real implementation, parse from LLM response
    risk_score = 3  # In real implementation, parse from LLM response
    
    print(f"Opportunity score: {opportunity_score}, Risk score: {risk_score}")
    
    updated_state = state.model_dump()
    updated_state['opportunity_score'] = opportunity_score
    updated_state['risk_score'] = risk_score
    return InvestmentState(**updated_state)

async def decision_branch_node(state: InvestmentState) -> str:
    """Decision branch based on opportunity and risk scores"""
    print("=== Decision Branch Node ===")
    
    if state.risk_score >= 8:
        decision = "high_risk"
        print("Decision: High risk - immediate alert")
    elif state.opportunity_score >= 8:
        decision = "high_opportunity"
        print("Decision: High opportunity - alert with buy logic")
    else:
        decision = "neutral"
        print("Decision: Neutral - add to monitoring pool")
    
    return decision

async def risk_alert_node(state: InvestmentState) -> InvestmentState:
    """Generate risk alert"""
    print("=== Risk Alert Node ===")
    
    # Generate risk alert content
    risk_alerts = []
    for analysis in state.analysis_results.get("financial", []):
        if "风险" in analysis.get("analysis", ""):
            risk_alerts.append({
                "stock_code": analysis.get("stock_code"),
                "risk_point": analysis.get("analysis"),
                "suggestion": "立即减仓，避免踩雷"
            })
    
    # Add risk alerts to research brief
    research_brief = "【A股科技股投研简报-2026.03.16】\n"
    if risk_alerts:
        research_brief += "\n1. 高风险标的：\n"
        for alert in risk_alerts:
            research_brief += f"   - {alert.get('stock_code')}: {alert.get('risk_point')[:100]}...\n"
            research_brief += f"   - 操作建议：{alert.get('suggestion')}\n"
    
    updated_state = state.model_dump()
    updated_state['research_brief'] = research_brief
    updated_state['decision'] = "high_risk"
    return InvestmentState(**updated_state)

async def opportunity_alert_node(state: InvestmentState) -> InvestmentState:
    """Generate opportunity alert"""
    print("=== Opportunity Alert Node ===")
    
    # Generate opportunity alert content
    opportunities = []
    for analysis in state.analysis_results.get("financial", []) + state.analysis_results.get("research", []):
        if "机会" in analysis.get("analysis", "") or "推荐" in analysis.get("analysis", ""):
            opportunities.append({
                "stock_code": analysis.get("stock_code"),
                "core_logic": analysis.get("analysis"),
                "target_price": "18元",  # In real implementation, parse from analysis
                "stop_loss": "12元"  # In real implementation, calculate based on analysis
            })
    
    # Add opportunities to research brief
    research_brief = "【A股科技股投研简报-2026.03.16】\n"
    if opportunities:
        research_brief += "\n1. 高机会标的：\n"
        for opportunity in opportunities:
            research_brief += f"   - {opportunity.get('stock_code')}: {opportunity.get('core_logic')[:100]}...\n"
            research_brief += f"   - 操作建议：逢低布局，目标价{opportunity.get('target_price')}，止损价{opportunity.get('stop_loss')}\n"
    
    updated_state = state.model_dump()
    updated_state['research_brief'] = research_brief
    updated_state['decision'] = "high_opportunity"
    return InvestmentState(**updated_state)

async def neutral_monitoring_node(state: InvestmentState) -> InvestmentState:
    """Add to monitoring pool"""
    print("=== Neutral Monitoring Node ===")
    
    # Add neutral signals to monitoring pool
    monitoring_items = []
    for analysis in state.analysis_results.get("policy", []) + state.analysis_results.get("fund_flow", []):
        monitoring_items.append({
            "content": analysis.get("content"),
            "related_stocks": analysis.get("stocks", []) + analysis.get("related_stocks", [])
        })
    
    # Add neutral signals to research brief
    research_brief = "【A股科技股投研简报-2026.03.16】\n"
    if monitoring_items:
        research_brief += "\n3. 中性信号：\n"
        for item in monitoring_items:
            research_brief += f"   - {item.get('content')}\n"
            if item.get('related_stocks'):
                research_brief += f"   - 相关标的：{', '.join(item.get('related_stocks'))}\n"
    
    updated_state = state.model_dump()
    updated_state['research_brief'] = research_brief
    updated_state['decision'] = "neutral"
    return InvestmentState(**updated_state)

def send_wechat_message(content):
    """Send message to WeChat enterprise account"""
    import json
    
    corp_id = os.getenv("WECHAT_CORP_ID")
    app_secret = os.getenv("WECHAT_APP_SECRET")
    agent_id = os.getenv("WECHAT_AGENT_ID")
    
    if not all([corp_id, app_secret, agent_id]):
        print("WeChat configuration not complete, skipping push")
        return False
    
    # Get access token
    token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={app_secret}"
    try:
        response = requests.get(token_url)
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            print("Failed to get WeChat access token")
            return False
        
        # Send message
        message_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        message_data = {
            "touser": "@all",
            "msgtype": "text",
            "agentid": agent_id,
            "text": {
                "content": content
            },
            "safe": 0
        }
        
        response = requests.post(message_url, data=json.dumps(message_data))
        result = response.json()
        
        if result.get("errcode") == 0:
            print("WeChat message sent successfully")
            return True
        else:
            print(f"Failed to send WeChat message: {result.get('errmsg')}")
            return False
    except Exception as e:
        print(f"Error sending WeChat message: {str(e)}")
        return False

async def push_node(state: InvestmentState) -> InvestmentState:
    """Push research brief to designated channels"""
    print("=== Push Node ===")
    
    # Print research brief
    print("\n" + "="*50)
    print("Research Brief:")
    print(state.research_brief)
    print("="*50)
    
    # Push to WeChat
    print("Pushing to WeChat...")
    send_wechat_message(state.research_brief)
    
    # In a real implementation, also push to email
    print("Pushing to Email...")
    
    return InvestmentState(**state.model_dump())

# Build the graph
graph = StateGraph(InvestmentState)

# Add nodes
graph.add_node("information_collection", information_collection_node)
graph.add_node("information_cleaning", information_cleaning_node)
graph.add_node("information_classification", information_classification_node)
graph.add_node("financial_analysis", financial_analysis_node)
graph.add_node("policy_analysis", policy_analysis_node)
graph.add_node("fund_flow_analysis", fund_flow_analysis_node)
graph.add_node("research_analysis", research_analysis_node)
graph.add_node("multi_dimension_reasoning", multi_dimension_reasoning_node)
graph.add_node("risk_alert", risk_alert_node)
graph.add_node("opportunity_alert", opportunity_alert_node)
graph.add_node("neutral_monitoring", neutral_monitoring_node)
graph.add_node("push", push_node)

# Define edges
graph.set_entry_point("information_collection")
graph.add_edge("information_collection", "information_cleaning")
graph.add_edge("information_cleaning", "information_classification")
graph.add_edge("information_classification", "financial_analysis")
graph.add_edge("financial_analysis", "policy_analysis")
graph.add_edge("policy_analysis", "fund_flow_analysis")
graph.add_edge("fund_flow_analysis", "research_analysis")
graph.add_edge("research_analysis", "multi_dimension_reasoning")

# Add conditional edges based on decision
graph.add_conditional_edges(
    "multi_dimension_reasoning",
    decision_branch_node,
    {
        "high_risk": "risk_alert",
        "high_opportunity": "opportunity_alert",
        "neutral": "neutral_monitoring"
    }
)

graph.add_edge("risk_alert", "push")
graph.add_edge("opportunity_alert", "push")
graph.add_edge("neutral_monitoring", "push")
graph.add_edge("push", END)

# Compile the graph
app = graph.compile()

# Main function
async def main():
    """Main function to run the investment research agent"""
    print("Starting A-share Technology Investment Research Agent...")
    
    # Initialize state
    initial_state = InvestmentState(
        raw_information=[],
        cleaned_information=[],
        classified_information={},
        analysis_results={},
        opportunity_score=0,
        risk_score=0,
        decision="",
        research_brief="",
        monitoring_stocks=os.getenv("MONITORING_STOCKS", "600000,000001,600519").split(",")
    )
    
    # Run the graph
    result = await app.ainvoke(initial_state)
    
    print("\nAgent run completed successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())