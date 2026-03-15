"""
财务分析器
分析股票财务指标和评分
"""
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

from projects.broker_gold_stock.data.models import FinancialAnalysis, FinancialScore
from projects.broker_gold_stock.data.repository import FinancialRepository
from core.data_access.tushare.client import TushareClient


class FinancialAnalyzer:
    """财务分析器 - 分析财务指标并生成评分"""

    def __init__(self):
        self.ts_client = TushareClient()

    def analyze(self, ts_code: str) -> tuple:
        """
        对股票进行财务分析

        Args:
            ts_code: 股票代码

        Returns:
            (FinancialScore对象, 数据源信息字典)
        """
        # 获取财务数据
        financial_data, data_source_info = self._fetch_financial_data(ts_code)

        if not financial_data:
            return FinancialScore(total=50), data_source_info

        scores = {}

        # 1. 估值水平 (权重35%)
        scores['valuation'] = self._analyze_valuation(financial_data)

        # 2. 盈利能力 (权重30%)
        scores['profitability'] = self._analyze_profitability(financial_data)

        # 3. 成长性 (权重20%)
        scores['growth'] = self._analyze_growth(financial_data)

        # 4. 财务健康 (权重15%)
        scores['health'] = self._analyze_health(financial_data)

        # 计算总分
        total = int(
            scores['valuation'] * 0.35 +
            scores['profitability'] * 0.30 +
            scores['growth'] * 0.20 +
            scores['health'] * 0.15
        )

        # 保存分析结果
        self._save_analysis(ts_code, financial_data, total)

        # 更新数据源信息中的实际数据日期
        if financial_data:
            if financial_data.get('daily_basic') is not None and not financial_data['daily_basic'].empty:
                daily_basic_date = str(financial_data['daily_basic'].iloc[0].get('trade_date', ''))
                data_source_info['daily_basic_date'] = daily_basic_date
            if financial_data.get('income') is not None and not financial_data['income'].empty:
                income_date = str(financial_data['income'].iloc[0].get('report_date', ''))
                data_source_info['income_date'] = income_date

        return FinancialScore(
            total=min(100, max(0, total)),
            valuation_score=scores['valuation'],
            profitability_score=scores['profitability'],
            growth_score=scores['growth'],
            health_score=scores['health']
        ), data_source_info

    def _fetch_financial_data(self, ts_code: str) -> tuple:
        """
        获取财务数据 - 优先从本地数据库读取

        Returns:
            (财务数据字典, 数据源信息字典)
        """
        from datetime import datetime
        from core.storage.relational.connection import DatabaseManager

        # 获取最近4个季度的数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = str((datetime.now().year - 1) * 10000 + 101)

        data_source_info = {
            'source_type': '',
            'tables_used': [],
            'daily_basic': {'source': '', 'table': '', 'date': '', 'records': 0},
            'income': {'source': '', 'table': '', 'date': '', 'records': 0},
            'balance': {'source': '', 'table': '', 'date': '', 'records': 0}
        }

        try:
            # 1. 优先从本地数据库读取 daily_basic
            daily_basic = self._get_local_daily_basic(ts_code)
            if not daily_basic.empty:
                data_source_info['daily_basic']['source'] = '本地数据库'
                data_source_info['daily_basic']['table'] = 'tushare_biz.t_stock_daily_basic'
                data_source_info['daily_basic']['date'] = str(daily_basic.iloc[0].get('trade_date', ''))
                data_source_info['daily_basic']['records'] = len(daily_basic)
            else:
                daily_basic = self.ts_client.get_daily_basic(ts_code=ts_code)
                if not daily_basic.empty:
                    data_source_info['daily_basic']['source'] = 'Tushare API'
                    data_source_info['daily_basic']['table'] = 'api.t_stock_daily_basic'
                    data_source_info['daily_basic']['date'] = str(daily_basic.iloc[0].get('trade_date', ''))
                    data_source_info['daily_basic']['records'] = len(daily_basic)

            # 2. 获取利润表数据
            income = self._get_local_income(ts_code, start_date, end_date)
            if not income.empty:
                data_source_info['income']['source'] = '本地数据库'
                data_source_info['income']['table'] = 'tushare_biz.t_stock_income'
                data_source_info['income']['date'] = str(income.iloc[0].get('report_date', ''))
                data_source_info['income']['records'] = len(income)
            else:
                income = self.ts_client.get_income(ts_code, start_date, end_date)
                if not income.empty:
                    data_source_info['income']['source'] = 'Tushare API'
                    data_source_info['income']['table'] = 'api.t_stock_income'
                    data_source_info['income']['date'] = str(income.iloc[0].get('end_date', ''))
                    data_source_info['income']['records'] = len(income)

            # 3. 获取资产负债表数据
            balance = self._get_local_balance(ts_code, start_date, end_date)
            if not balance.empty:
                data_source_info['balance']['source'] = '本地数据库'
                data_source_info['balance']['table'] = 'tushare_biz.t_stock_balancesheet'
                data_source_info['balance']['date'] = str(balance.iloc[0].get('report_date', ''))
                data_source_info['balance']['records'] = len(balance)
            else:
                balance = self.ts_client.get_balance_sheet(ts_code, start_date, end_date)
                if not balance.empty:
                    data_source_info['balance']['source'] = 'Tushare API'
                    data_source_info['balance']['table'] = 'api.t_stock_balancesheet'
                    data_source_info['balance']['date'] = str(balance.iloc[0].get('end_date', ''))
                    data_source_info['balance']['records'] = len(balance)

            # 打印数据源信息
            source_summary = []
            for key in ['daily_basic', 'income', 'balance']:
                src = data_source_info[key]
                if src['source']:
                    source_summary.append(f"{key}: {src['source']}({src['date']})")
            if source_summary:
                print(f"   [数据源] {', '.join(source_summary)}")

            if income.empty and balance.empty and daily_basic.empty:
                return None, data_source_info

            return {
                'income': income,
                'balance': balance,
                'daily_basic': daily_basic
            }, data_source_info

        except Exception as e:
            print(f"获取财务数据失败 {ts_code}: {e}")
            return None, data_source_info

    def _get_local_daily_basic(self, ts_code: str) -> pd.DataFrame:
        """从本地数据库获取每日指标数据"""
        from core.storage.relational.connection import DatabaseManager

        sql = """
            SELECT trade_date, pe, pe_ttm, pb, ps_ttm, total_mv
            FROM t_stock_daily_basic
            WHERE ts_code = %s
            ORDER BY trade_date DESC
            LIMIT 1
        """
        rows = DatabaseManager.fetchall('tushare_biz', sql, (ts_code,))
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def _get_local_income(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从本地数据库获取利润表数据"""
        from core.storage.relational.connection import DatabaseManager

        sql = """
            SELECT end_date as report_date, revenue, total_revenue,
                   n_income as net_income, total_profit, income_tax,
                   operate_profit, basic_eps as eps
            FROM t_stock_income
            WHERE ts_code = %s AND end_date BETWEEN %s AND %s
            ORDER BY end_date DESC
            LIMIT 4
        """
        rows = DatabaseManager.fetchall('tushare_biz', sql, (ts_code, start_date, end_date))
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def _get_local_balance(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从本地数据库获取资产负债表数据"""
        from core.storage.relational.connection import DatabaseManager

        sql = """
            SELECT end_date as report_date,
                   total_assets, total_liab, total_hldr_eqy_exc_min_int,
                   total_cur_assets, total_cur_liab
            FROM t_stock_balancesheet
            WHERE ts_code = %s AND end_date BETWEEN %s AND %s
            ORDER BY end_date DESC
            LIMIT 1
        """
        rows = DatabaseManager.fetchall('tushare_biz', sql, (ts_code, start_date, end_date))

        if rows:
            df = pd.DataFrame(rows)
            # 计算资产负债率和流动比率
            for _, row in df.iterrows():
                total_assets = row.get('total_assets', 0)
                total_liab = row.get('total_liab', 0)
                current_assets = row.get('total_cur_assets', 0)
                current_liab = row.get('total_cur_liab', 0)

                if total_assets and total_assets > 0:
                    row['debt_to_assets'] = (total_liab / total_assets) * 100 if total_liab else 0
                else:
                    row['debt_to_assets'] = None

                if current_liab and current_liab > 0:
                    row['current_ratio'] = current_assets / current_liab if current_assets else 0
                else:
                    row['current_ratio'] = None

            return df

        return pd.DataFrame()

    def _analyze_valuation(self, data: Dict[str, Any]) -> int:
        """
        估值水平分析

        基于PE、PB、PS、PEG等指标
        """
        score = 50
        daily_basic = data.get('daily_basic')

        if daily_basic is None or daily_basic.empty:
            return score

        latest = daily_basic.iloc[0]

        # PE TTM评分 (越低越好，但排除负值)
        pe = latest.get('pe_ttm')
        if pe and pe > 0:
            if pe < 15:
                score += 20
            elif pe < 25:
                score += 10
            elif pe < 40:
                score += 0
            else:
                score -= 10

        # PB评分
        pb = latest.get('pb')
        if pb and pb > 0:
            if pb < 1.5:
                score += 15
            elif pb < 3:
                score += 5
            elif pb > 6:
                score -= 10

        # PEG评分 (市盈率相对盈利增长比率)
        peg = latest.get('peg')
        if peg and peg > 0:
            if peg < 1:
                score += 15  # 低估
            elif peg < 2:
                score += 5
            else:
                score -= 5

        return min(100, max(0, score))

    def _analyze_profitability(self, data: Dict[str, Any]) -> int:
        """
        盈利能力分析

        ROE、ROA、毛利率、净利率
        """
        score = 50
        income = data.get('income')
        balance = data.get('balance')

        if income is None or income.empty:
            return score

        latest = income.iloc[0]

        # ROE分析 (使用最新一期)
        roe = latest.get('roe')
        if roe and roe > 0:
            if roe > 20:
                score += 25
            elif roe > 15:
                score += 15
            elif roe > 10:
                score += 5
            else:
                score -= 5

        # 毛利率
        gross_margin = latest.get('grossprofit_margin')
        if gross_margin:
            if gross_margin > 40:
                score += 15
            elif gross_margin > 25:
                score += 5

        # 净利率
        net_margin = latest.get('netprofit_margin')
        if net_margin:
            if net_margin > 20:
                score += 15
            elif net_margin > 10:
                score += 5
            elif net_margin < 5:
                score -= 5

        # ROA
        if balance is not None and not balance.empty:
            roa = latest.get('roa')
            if roa and roa > 10:
                score += 10

        return min(100, max(0, score))

    def _analyze_growth(self, data: Dict[str, Any]) -> int:
        """
        成长性分析

        营收增长率、净利润增长率
        """
        score = 50
        income = data.get('income')

        if income is None or income.empty or len(income) < 2:
            return score

        # 计算同比增长率
        try:
            # 营收增长
            latest_revenue = income.iloc[0].get('total_revenue')
            prev_revenue = income.iloc[-1].get('total_revenue')

            if latest_revenue and prev_revenue and prev_revenue > 0:
                revenue_growth = (latest_revenue - prev_revenue) / prev_revenue * 100

                if revenue_growth > 50:
                    score += 25
                elif revenue_growth > 30:
                    score += 15
                elif revenue_growth > 15:
                    score += 5
                elif revenue_growth < 0:
                    score -= 10

            # 净利润增长
            latest_profit = income.iloc[0].get('net_income')
            prev_profit = income.iloc[-1].get('net_income')

            if latest_profit and prev_profit and prev_profit > 0:
                profit_growth = (latest_profit - prev_profit) / prev_profit * 100

                if profit_growth > 50:
                    score += 25
                elif profit_growth > 30:
                    score += 15
                elif profit_growth > 15:
                    score += 5
                elif profit_growth < 0:
                    score -= 15

        except Exception as e:
            print(f"计算增长率失败: {e}")

        return min(100, max(0, score))

    def _analyze_health(self, data: Dict[str, Any]) -> int:
        """
        财务健康分析

        资产负债率、流动比率
        """
        score = 50
        balance = data.get('balance')

        if balance is None or balance.empty:
            return score

        latest = balance.iloc[0]

        # 资产负债率
        debt_ratio = latest.get('debt_to_assets')
        if debt_ratio:
            if debt_ratio < 40:
                score += 20
            elif debt_ratio < 60:
                score += 10
            elif debt_ratio > 80:
                score -= 20
            elif debt_ratio > 70:
                score -= 10

        # 流动比率
        current_ratio = latest.get('current_ratio')
        if current_ratio:
            if current_ratio > 2:
                score += 15
            elif current_ratio > 1.5:
                score += 5
            elif current_ratio < 1:
                score -= 10

        return min(100, max(0, score))

    def _save_analysis(self, ts_code: str, data: Dict[str, Any], score: int):
        """保存分析结果到数据库"""
        try:
            daily_basic = data.get('daily_basic')
            income = data.get('income')
            balance = data.get('balance')

            if daily_basic is None or daily_basic.empty:
                return

            latest_daily = daily_basic.iloc[0]
            latest_income = income.iloc[0] if income is not None and not income.empty else None
            latest_balance = balance.iloc[0] if balance is not None and not balance.empty else None

            # 计算同比增长率
            revenue_growth = None
            profit_growth = None
            if income is not None and len(income) >= 2:
                try:
                    if income.iloc[-1].get('total_revenue', 0) > 0:
                        revenue_growth = (income.iloc[0]['total_revenue'] - income.iloc[-1]['total_revenue']) / income.iloc[-1]['total_revenue'] * 100
                    if income.iloc[-1].get('net_income', 0) > 0:
                        profit_growth = (income.iloc[0]['net_income'] - income.iloc[-1]['net_income']) / income.iloc[-1]['net_income'] * 100
                except:
                    pass

            # 确定质量标签
            quality_tag = "中"
            if score >= 80:
                quality_tag = "优"
            elif score >= 60:
                quality_tag = "良"
            elif score < 40:
                quality_tag = "差"

            analysis = FinancialAnalysis(
                ts_code=ts_code,
                name=latest_daily.get('name', ''),
                report_date=str(latest_daily.get('trade_date', '')),
                pe_ttm=latest_daily.get('pe_ttm'),
                pb=latest_daily.get('pb'),
                ps_ttm=latest_daily.get('ps_ttm'),
                peg=latest_daily.get('peg'),
                roe=latest_income.get('roe') if latest_income else None,
                roa=latest_income.get('roa') if latest_income else None,
                gross_margin=latest_income.get('grossprofit_margin') if latest_income else None,
                net_margin=latest_income.get('netprofit_margin') if latest_income else None,
                revenue_growth=revenue_growth,
                profit_growth=profit_growth,
                debt_ratio=latest_balance.get('debt_to_assets') if latest_balance else None,
                current_ratio=latest_balance.get('current_ratio') if latest_balance else None,
                financial_score=score,
                quality_tag=quality_tag
            )

            FinancialRepository.save_financial_analysis(analysis)

        except Exception as e:
            print(f"保存财务分析失败 {ts_code}: {e}")
