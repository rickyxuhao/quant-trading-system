"""
龙头股策略 - 按行业挑选财务表现最好的股票
"""
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime
from pathlib import Path

import sys
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from projects.quant_trading.backtest.strategy import BaseStrategy, Signal
from projects.quant_trading.backtest.data_manager import DataManager
from core.storage.relational.connection import DatabaseManager

# 配置日志
logger = logging.getLogger(__name__)


class LeadingStockStrategy(BaseStrategy):
    """
    龙头股策略

    按行业分类，挑选每个行业中财务表现最好的股票。

    财务指标：
    - ROE（净资产收益率）：衡量盈利能力
    - ROA（总资产收益率）：衡量资产利用效率
    - 净利润增长率：衡量成长性
    - 毛利率：衡量竞争优势

    参数:
        top_n_per_industry: 每个行业选几只龙头股，默认1只
        min_roe: 最小ROE要求，默认0.10（10%）
        lookback_period: 回看周期（交易日），默认60日
        financial_score_weight: 财务指标综合评分权重
        weight_method: 权重分配方法，可选 'equal'/'financial_score'/'market_cap'/'inverse_volatility'
    """

    def __init__(
        self,
        top_n_per_industry: int = 1,
        min_roe: float = 0.10,
        lookback_period: int = 60,
        financial_score_weight: Optional[Dict[str, float]] = None,
        weight_method: str = 'equal'
    ):
        super().__init__(name="LeadingStockStrategy")
        self.top_n_per_industry = top_n_per_industry
        self.min_roe = min_roe
        self.lookback_period = lookback_period

        # 验证权重方法
        valid_methods = ['equal', 'financial_score', 'market_cap', 'inverse_volatility']
        if weight_method not in valid_methods:
            raise ValueError(f"无效的weight_method: {weight_method}，可选: {valid_methods}")
        self.weight_method = weight_method

        # 财务指标权重（默认：ROE 40%, ROA 25%, 净利润增长 20%, 毛利率 15%）
        self.financial_weights = financial_score_weight or {
            'roe': 0.40,
            'roa': 0.25,
            'profit_growth': 0.20,
            'gross_margin': 0.15
        }

        # 缓存行业和财务数据
        self._industry_cache: Dict[str, str] = {}  # ts_code -> industry
        self._financial_cache: Dict[str, pd.DataFrame] = {}  # ts_code -> financial_data
        self._market_cap_cache: Dict[str, float] = {}  # ts_code -> market_cap
        self._volatility_cache: Dict[str, float] = {}  # ts_code -> volatility
    
    def generate_signals(
        self,
        data: Dict[str, pd.DataFrame],
        current_date: datetime,
        available_stocks: List[str]
    ) -> List[str]:
        """
        生成交易信号 - 按行业挑选龙头股
        
        Returns:
            目标持仓股票代码列表
        """
        # 1. 获取股票行业分类
        stock_industries = self._get_stock_industries(available_stocks)
        
        # 2. 按行业分组
        industry_groups: Dict[str, List[str]] = {}
        for ts_code, industry in stock_industries.items():
            if industry not in industry_groups:
                industry_groups[industry] = []
            industry_groups[industry].append(ts_code)
        
        print(f"  [龙头股策略] 发现 {len(industry_groups)} 个行业")
        
        # 3. 在每个行业中挑选龙头股
        selected_stocks = []
        
        for industry, stocks in industry_groups.items():
            if len(stocks) < 2:  # 跳过股票太少的行业
                continue
            
            # 获取该行业股票的财务数据
            financial_scores = []
            
            for ts_code in stocks:
                if ts_code not in data:
                    continue
                
                # 获取财务指标
                fin_data = self._get_financial_indicators(ts_code, current_date)
                if fin_data is None:
                    continue
                
                # 计算综合财务得分
                score = self._calculate_financial_score(fin_data)
                
                # ROE过滤
                roe = fin_data.get('roe', 0) or 0
                if roe < self.min_roe:
                    continue
                
                financial_scores.append({
                    'ts_code': ts_code,
                    'score': score,
                    'roe': roe,
                    'industry': industry
                })
            
            if not financial_scores:
                continue
            
            # 按财务得分排序，选择前N只
            financial_scores.sort(key=lambda x: x['score'], reverse=True)
            industry_leaders = financial_scores[:self.top_n_per_industry]
            
            selected_stocks.extend([s['ts_code'] for s in industry_leaders])
            
            print(f"    {industry}: 选中 {len(industry_leaders)} 只")
            for leader in industry_leaders:
                print(f"      - {leader['ts_code']}: ROE={leader['roe']*100:.1f}%, 得分={leader['score']:.2f}")
        
        print(f"  [龙头股策略] 共选中 {len(selected_stocks)} 只股票")
        return selected_stocks
    
    def _get_stock_industries(self, ts_codes: List[str]) -> Dict[str, str]:
        """
        获取股票的行业分类
        
        Returns:
            {ts_code: industry}
        """
        # 检查缓存
        result = {}
        codes_to_query = []
        
        for ts_code in ts_codes:
            if ts_code in self._industry_cache:
                result[ts_code] = self._industry_cache[ts_code]
            else:
                codes_to_query.append(ts_code)
        
        if not codes_to_query:
            return result
        
        # 批量查询数据库
        try:
            placeholders = ','.join(['%s'] * len(codes_to_query))
            sql = f"""
                SELECT ts_code, industry 
                FROM t_stock_basic 
                WHERE ts_code IN ({placeholders}) 
                AND industry IS NOT NULL
            """
            
            data = DatabaseManager.fetchall('tushare_biz', sql, tuple(codes_to_query))
            
            for row in data:
                ts_code = row['ts_code']
                industry = row['industry']
                result[ts_code] = industry
                self._industry_cache[ts_code] = industry
        
        except Exception as e:
            print(f"[警告] 获取行业数据失败: {e}")
        
        return result
    
    def _get_financial_indicators(self, ts_code: str, current_date: datetime) -> Optional[Dict]:
        """
        获取股票的财务指标
        
        Returns:
            财务指标字典，包含 roe, roa, profit_growth, gross_margin
        """
        # 检查缓存
        if ts_code in self._financial_cache:
            df = self._financial_cache[ts_code]
        else:
            # 从数据库查询最近4个季度的财务指标
            try:
                sql = """
                    SELECT end_date, roe, roa, q_sales_yoy, grossprofit_margin
                    FROM t_stock_fina_indicator
                    WHERE ts_code = %s
                    ORDER BY end_date DESC
                    LIMIT 4
                """
                data = DatabaseManager.fetchall('tushare_biz', sql, (ts_code,))
                
                if not data:
                    return None
                
                df = pd.DataFrame(data)
                self._financial_cache[ts_code] = df
            
            except Exception as e:
                print(f"[警告] 获取财务数据失败 {ts_code}: {e}")
                return None
        
        if df.empty:
            return None
        
        # 计算平均财务指标（最近4个季度）
        fin_data = {
            'roe': df['roe'].mean() / 100 if df['roe'].notna().any() else 0,  # 转为小数
            'roa': df['roa'].mean() / 100 if df['roa'].notna().any() else 0,
            'profit_growth': df['q_sales_yoy'].mean() / 100 if df['q_sales_yoy'].notna().any() else 0,
            'gross_margin': df['grossprofit_margin'].mean() / 100 if df['grossprofit_margin'].notna().any() else 0
        }
        
        return fin_data
    
    def _calculate_financial_score(self, fin_data: Dict) -> float:
        """
        计算综合财务得分
        
        加权平均：
        - ROE: 40%
        - ROA: 25%
        - 净利润增长率: 20%
        - 毛利率: 15%
        """
        score = 0.0
        
        # ROE（净资产收益率）
        roe = fin_data.get('roe', 0) or 0
        # ROE标准化（假设优秀ROE为20%，即0.2）
        roe_score = min(roe / 0.20, 1.0)  # 封顶1.0
        score += roe_score * self.financial_weights['roe']
        
        # ROA（总资产收益率）
        roa = fin_data.get('roa', 0) or 0
        # ROA标准化（假设优秀ROA为10%，即0.1）
        roa_score = min(roa / 0.10, 1.0)
        score += roa_score * self.financial_weights['roa']
        
        # 净利润增长率
        profit_growth = fin_data.get('profit_growth', 0) or 0
        # 增长率标准化（假设优秀增长率为30%，即0.3）
        # 负增长得0分
        if profit_growth > 0:
            growth_score = min(profit_growth / 0.30, 1.0)
        else:
            growth_score = 0
        score += growth_score * self.financial_weights['profit_growth']
        
        # 毛利率
        gross_margin = fin_data.get('gross_margin', 0) or 0
        # 毛利率标准化（假设优秀毛利率为40%，即0.4）
        margin_score = min(gross_margin / 0.40, 1.0)
        score += margin_score * self.financial_weights['gross_margin']
        
        return score
    
    def get_industry_distribution(self, selected_stocks: List[str]) -> Dict[str, int]:
        """获取选中股票的行业分布"""
        distribution = {}
        for ts_code in selected_stocks:
            industry = self._industry_cache.get(ts_code, '未知')
            distribution[industry] = distribution.get(industry, 0) + 1
        return distribution


if __name__ == "__main__":
    # 测试龙头股策略
    print("=" * 60)
    print("龙头股策略测试")
    print("=" * 60)
    
    strategy = LeadingStockStrategy(
        top_n_per_industry=1,
        min_roe=0.10
    )
    
    print(f"\n策略名称: {strategy.get_name()}")
    print(f"参数: 每行业选{strategy.top_n_per_industry}只, 最小ROE={strategy.min_roe*100}%")
    
    # 模拟测试（需要真实数据库数据才能运行完整测试）
    print("\n提示：完整测试需要连接数据库获取行业和财务数据")
