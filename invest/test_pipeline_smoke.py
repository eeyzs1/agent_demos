"""Smoke test for ScanRecommendPipeline"""
from trading_system.pipeline.scan_recommend import ScanRecommendPipeline
from trading_system.scorer.engine import StockScorer
from trading_system.advisor.entry_exit import EntryExitAdvisor

pipeline = ScanRecommendPipeline()
stock_data_list, market_summary = pipeline.run(candidate_limit=10)

print(f"Stocks fetched: {len(stock_data_list)}")
print(f"Market summary: {market_summary}")

if stock_data_list:
    scorer = StockScorer()
    scores = scorer.rank_stocks(stock_data_list)
    advisor = EntryExitAdvisor(scorer)
    for s in scores[:5]:
        price = s.details.get("price", 0)
        rec = advisor.recommend_entry(s.symbol, price, s.details)
        print(f"  {s.rank}. {s.symbol} {s.name} score={s.total_score:.1f} "
              f"rating={s.rating.value} price={price:.2f} rec={rec.recommendation_type.value}")
    print("Pipeline smoke test PASSED")
else:
    print("WARNING: No stocks fetched, but pipeline ran without crashing")