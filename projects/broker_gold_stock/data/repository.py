"""
数据访问层 - Repository 模式
提供对券商金股相关数据表的CRUD操作
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from core.storage.relational.connection import DatabaseManager
from projects.broker_gold_stock.data.models import (
    GoldStock, GoldStockPerformance, FinancialAnalysis,
    QuantFactorScore, StockAnomaly, NewsSentiment, MorningReport,
    StockStatus, AnomalySeverity
)


class GoldStockRepository:
    """券商金股数据访问"""

    DB_NAME = "interface"

    @classmethod
    def save_gold_stock(cls, stock: GoldStock) -> int:
        """保存或更新金股推荐记录"""
        sql = """
            INSERT INTO broker_gold_stock
            (month, broker_name, ts_code, name, industry, analyst, logic, target_price, previous_perf)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
            name = new.name,
            industry = new.industry,
            analyst = new.analyst,
            logic = new.logic,
            target_price = new.target_price,
            previous_perf = new.previous_perf
        """
        result = DatabaseManager.execute(cls.DB_NAME, sql, (
            stock.month, stock.broker_name, stock.ts_code, stock.name,
            stock.industry, stock.analyst, stock.logic, stock.target_price, stock.previous_perf
        ))
        return result

    @classmethod
    def save_many_gold_stocks(cls, stocks: List[GoldStock]) -> Dict[str, int]:
        """批量保存金股推荐"""
        if not stocks:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = ['month', 'broker_name', 'ts_code', 'name', 'industry',
                   'analyst', 'logic', 'target_price', 'previous_perf']
        rows = []
        for s in stocks:
            rows.append([
                s.month, s.broker_name, s.ts_code, s.name, s.industry,
                s.analyst, s.logic, s.target_price, s.previous_perf
            ])

        on_duplicate = """
            name = new.name, industry = new.industry, analyst = new.analyst,
            logic = new.logic, target_price = new.target_price, previous_perf = new.previous_perf
        """

        return DatabaseManager.insert_many(
            cls.DB_NAME, 'broker_gold_stock', columns, rows,
            on_duplicate=on_duplicate
        )

    @classmethod
    def get_gold_stocks_by_month(cls, month: str) -> List[GoldStock]:
        """获取指定月份的所有金股"""
        sql = """
            SELECT * FROM broker_gold_stock
            WHERE month = %s
            ORDER BY broker_name, ts_code
        """
        rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (month,))
        return [cls._row_to_gold_stock(r) for r in rows]

    @classmethod
    def get_gold_stocks_by_code(cls, ts_code: str, months: int = 3) -> List[GoldStock]:
        """获取指定股票近N个月的金股记录"""
        sql = """
            SELECT * FROM broker_gold_stock
            WHERE ts_code = %s
            AND month >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL %s MONTH), '%Y%m')
            ORDER BY month DESC
        """
        rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (ts_code, months))
        return [cls._row_to_gold_stock(r) for r in rows]

    @classmethod
    def get_all_brokers(cls, month: str) -> List[str]:
        """获取指定月份的所有券商名称"""
        sql = """
            SELECT DISTINCT broker_name FROM broker_gold_stock
            WHERE month = %s AND broker_name IS NOT NULL
            ORDER BY broker_name
        """
        rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (month,))
        return [r['broker_name'] for r in rows]

    @staticmethod
    def _row_to_gold_stock(row: Dict) -> GoldStock:
        """将数据库行转换为GoldStock对象"""
        return GoldStock(
            id=row.get('id'),
            month=row.get('month', ''),
            broker_name=row.get('broker_name', ''),
            ts_code=row.get('ts_code', ''),
            name=row.get('name', ''),
            industry=row.get('industry', ''),
            analyst=row.get('analyst', ''),
            logic=row.get('logic', ''),
            target_price=row.get('target_price'),
            previous_perf=row.get('previous_perf'),
            created_at=row.get('created_at')
        )


class PerformanceRepository:
    """金股表现数据访问"""

    DB_NAME = "interface"

    @classmethod
    def save_performance(cls, perf: GoldStockPerformance) -> int:
        """保存或更新表现数据"""
        sql = """
            INSERT INTO gold_stock_performance
            (month, ts_code, name, recommend_date, end_date, recommend_price, current_price,
             max_price, min_price, total_return, excess_return, max_drawdown,
             avg_volume, volatility, technical_score, technical_signals, ext_data, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
            name = new.name, current_price = new.current_price, max_price = new.max_price,
            min_price = new.min_price, total_return = new.total_return,
            excess_return = new.excess_return, max_drawdown = new.max_drawdown,
            avg_volume = new.avg_volume, volatility = new.volatility,
            technical_score = new.technical_score, technical_signals = new.technical_signals,
            ext_data = new.ext_data, status = new.status
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (
            perf.month, perf.ts_code, perf.name, perf.recommend_date, perf.end_date,
            perf.recommend_price, perf.current_price, perf.max_price, perf.min_price,
            perf.total_return, perf.excess_return, perf.max_drawdown,
            perf.avg_volume, perf.volatility, perf.technical_score,
            json.dumps(perf.technical_signals) if perf.technical_signals else None,
            json.dumps(perf.ext_data) if perf.ext_data else None,
            perf.status.value if perf.status else 'watching'
        ))

    @classmethod
    def get_performance_by_month(cls, month: str) -> List[GoldStockPerformance]:
        """获取指定月份的所有金股表现"""
        sql = "SELECT * FROM gold_stock_performance WHERE month = %s"
        rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (month,))
        return [cls._row_to_performance(r) for r in rows]

    @classmethod
    def get_performance_by_code(cls, ts_code: str, month: str) -> Optional[GoldStockPerformance]:
        """获取指定股票在指定月份的表现"""
        sql = "SELECT * FROM gold_stock_performance WHERE ts_code = %s AND month = %s"
        row = DatabaseManager.fetchone(cls.DB_NAME, sql, (ts_code, month))
        return cls._row_to_performance(row) if row else None

    @staticmethod
    def _row_to_performance(row: Dict) -> GoldStockPerformance:
        """将数据库行转换为GoldStockPerformance对象"""
        return GoldStockPerformance(
            id=row.get('id'),
            month=row.get('month', ''),
            ts_code=row.get('ts_code', ''),
            name=row.get('name', ''),
            recommend_date=row.get('recommend_date', ''),
            end_date=row.get('end_date'),
            recommend_price=row.get('recommend_price'),
            current_price=row.get('current_price'),
            max_price=row.get('max_price'),
            min_price=row.get('min_price'),
            total_return=row.get('total_return'),
            excess_return=row.get('excess_return'),
            max_drawdown=row.get('max_drawdown'),
            avg_volume=row.get('avg_volume'),
            volatility=row.get('volatility'),
            technical_score=row.get('technical_score'),
            technical_signals=json.loads(row['technical_signals']) if row.get('technical_signals') else None,
            ext_data=json.loads(row['ext_data']) if row.get('ext_data') else None,
            status=StockStatus(row.get('status', 'watching')),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )


class FinancialRepository:
    """财务分析数据访问"""

    DB_NAME = "interface"

    @classmethod
    def save_financial_analysis(cls, analysis: FinancialAnalysis) -> int:
        """保存财务分析结果"""
        sql = """
            INSERT INTO financial_analysis
            (ts_code, name, report_date, pe_ttm, pb, ps_ttm, peg, roe, roa,
             gross_margin, net_margin, revenue_growth, profit_growth,
             debt_ratio, current_ratio, financial_score, quality_tag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
            pe_ttm = new.pe_ttm, pb = new.pb, ps_ttm = new.ps_ttm, peg = new.peg,
            roe = new.roe, roa = new.roa, gross_margin = new.gross_margin,
            net_margin = new.net_margin, revenue_growth = new.revenue_growth,
            profit_growth = new.profit_growth, debt_ratio = new.debt_ratio,
            current_ratio = new.current_ratio, financial_score = new.financial_score,
            quality_tag = new.quality_tag
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (
            analysis.ts_code, analysis.name, analysis.report_date,
            analysis.pe_ttm, analysis.pb, analysis.ps_ttm, analysis.peg,
            analysis.roe, analysis.roa, analysis.gross_margin, analysis.net_margin,
            analysis.revenue_growth, analysis.profit_growth,
            analysis.debt_ratio, analysis.current_ratio,
            analysis.financial_score, analysis.quality_tag
        ))

    @classmethod
    def get_latest_analysis(cls, ts_code: str) -> Optional[FinancialAnalysis]:
        """获取指定股票的最新财务分析"""
        sql = """
            SELECT * FROM financial_analysis
            WHERE ts_code = %s
            ORDER BY report_date DESC
            LIMIT 1
        """
        row = DatabaseManager.fetchone(cls.DB_NAME, sql, (ts_code,))
        return cls._row_to_financial_analysis(row) if row else None

    @staticmethod
    def _row_to_financial_analysis(row: Dict) -> FinancialAnalysis:
        return FinancialAnalysis(
            id=row.get('id'),
            ts_code=row.get('ts_code', ''),
            name=row.get('name', ''),
            report_date=row.get('report_date', ''),
            pe_ttm=row.get('pe_ttm'),
            pb=row.get('pb'),
            ps_ttm=row.get('ps_ttm'),
            peg=row.get('peg'),
            roe=row.get('roe'),
            roa=row.get('roa'),
            gross_margin=row.get('gross_margin'),
            net_margin=row.get('net_margin'),
            revenue_growth=row.get('revenue_growth'),
            profit_growth=row.get('profit_growth'),
            debt_ratio=row.get('debt_ratio'),
            current_ratio=row.get('current_ratio'),
            financial_score=row.get('financial_score'),
            quality_tag=row.get('quality_tag'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )


class QuantFactorRepository:
    """量化因子数据访问"""

    DB_NAME = "interface"

    @classmethod
    def save_factor_score(cls, score: QuantFactorScore) -> int:
        """保存因子评分"""
        sql = """
            INSERT INTO quant_factor_score
            (ts_code, name, trade_date, value_factor, quality_factor, growth_factor,
             momentum_factor, volatility_factor, liquidity_factor, total_score,
             rank_in_industry, rank_in_market)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
            value_factor = new.value_factor, quality_factor = new.quality_factor,
            growth_factor = new.growth_factor, momentum_factor = new.momentum_factor,
            volatility_factor = new.volatility_factor, liquidity_factor = new.liquidity_factor,
            total_score = new.total_score, rank_in_industry = new.rank_in_industry,
            rank_in_market = new.rank_in_market
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (
            score.ts_code, score.name, score.trade_date,
            score.value_factor, score.quality_factor, score.growth_factor,
            score.momentum_factor, score.volatility_factor, score.liquidity_factor,
            score.total_score, score.rank_in_industry, score.rank_in_market
        ))

    @classmethod
    def get_factor_score(cls, ts_code: str, trade_date: str) -> Optional[QuantFactorScore]:
        """获取指定日期的因子评分"""
        sql = """
            SELECT * FROM quant_factor_score
            WHERE ts_code = %s AND trade_date = %s
        """
        row = DatabaseManager.fetchone(cls.DB_NAME, sql, (ts_code, trade_date))
        return cls._row_to_factor_score(row) if row else None

    @classmethod
    def get_latest_factor_score(cls, ts_code: str) -> Optional[QuantFactorScore]:
        """获取最新因子评分"""
        sql = """
            SELECT * FROM quant_factor_score
            WHERE ts_code = %s
            ORDER BY trade_date DESC
            LIMIT 1
        """
        row = DatabaseManager.fetchone(cls.DB_NAME, sql, (ts_code,))
        return cls._row_to_factor_score(row) if row else None

    @staticmethod
    def _row_to_factor_score(row: Dict) -> QuantFactorScore:
        return QuantFactorScore(
            id=row.get('id'),
            ts_code=row.get('ts_code', ''),
            name=row.get('name', ''),
            trade_date=row.get('trade_date', ''),
            value_factor=row.get('value_factor'),
            quality_factor=row.get('quality_factor'),
            growth_factor=row.get('growth_factor'),
            momentum_factor=row.get('momentum_factor'),
            volatility_factor=row.get('volatility_factor'),
            liquidity_factor=row.get('liquidity_factor'),
            total_score=row.get('total_score'),
            rank_in_industry=row.get('rank_in_industry'),
            rank_in_market=row.get('rank_in_market'),
            created_at=row.get('created_at')
        )


class AnomalyRepository:
    """异动检测数据访问"""

    DB_NAME = "interface"

    @classmethod
    def save_anomaly(cls, anomaly: StockAnomaly) -> int:
        """保存异动记录"""
        sql = """
            INSERT INTO stock_anomaly
            (ts_code, name, detect_date, anomaly_type, severity, trigger_price,
             price_change, volume_ratio, news_collected, news_analyzed,
             ai_analysis, ai_sentiment, recommendation, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (
            anomaly.ts_code, anomaly.name, anomaly.detect_date,
            anomaly.anomaly_type, anomaly.severity.value,
            anomaly.trigger_price, anomaly.price_change, anomaly.volume_ratio,
            1 if anomaly.news_collected else 0,
            1 if anomaly.news_analyzed else 0,
            anomaly.ai_analysis, anomaly.ai_sentiment,
            anomaly.recommendation, anomaly.confidence
        ))

    @classmethod
    def get_anomalies_by_date(cls, detect_date: str,
                              severity: Optional[str] = None) -> List[StockAnomaly]:
        """获取指定日期的异动记录"""
        if severity:
            sql = """
                SELECT * FROM stock_anomaly
                WHERE detect_date = %s AND severity = %s
                ORDER BY price_change DESC
            """
            rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (detect_date, severity))
        else:
            sql = """
                SELECT * FROM stock_anomaly
                WHERE detect_date = %s
                ORDER BY severity DESC, price_change DESC
            """
            rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (detect_date,))
        return [cls._row_to_anomaly(r) for r in rows]

    @classmethod
    def get_anomalies_by_code(cls, ts_code: str, days: int = 30) -> List[StockAnomaly]:
        """获取指定股票近N天的异动记录"""
        sql = """
            SELECT * FROM stock_anomaly
            WHERE ts_code = %s AND detect_date >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL %s DAY), '%Y%m%d')
            ORDER BY detect_date DESC
        """
        rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (ts_code, days))
        return [cls._row_to_anomaly(r) for r in rows]

    @classmethod
    def update_ai_analysis(cls, anomaly_id: int, analysis: str, sentiment: str) -> int:
        """更新AI分析结果"""
        sql = """
            UPDATE stock_anomaly
            SET ai_analysis = %s, ai_sentiment = %s, news_analyzed = 1
            WHERE id = %s
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (analysis, sentiment, anomaly_id))

    @staticmethod
    def _row_to_anomaly(row: Dict) -> StockAnomaly:
        return StockAnomaly(
            id=row.get('id'),
            ts_code=row.get('ts_code', ''),
            name=row.get('name', ''),
            detect_date=row.get('detect_date', ''),
            anomaly_type=row.get('anomaly_type', ''),
            severity=AnomalySeverity(row.get('severity', 'medium')),
            trigger_price=row.get('trigger_price'),
            price_change=row.get('price_change'),
            volume_ratio=row.get('volume_ratio'),
            news_collected=bool(row.get('news_collected')),
            news_analyzed=bool(row.get('news_analyzed')),
            ai_analysis=row.get('ai_analysis'),
            ai_sentiment=row.get('ai_sentiment'),
            recommendation=row.get('recommendation'),
            confidence=row.get('confidence'),
            created_at=row.get('created_at')
        )


class NewsRepository:
    """新闻舆情数据访问"""

    DB_NAME = "interface"

    @classmethod
    def save_news(cls, news: NewsSentiment) -> int:
        """保存新闻"""
        sql = """
            INSERT INTO news_sentiment
            (ts_code, name, news_date, title, content, source, url,
             sentiment_score, sentiment_label, ai_summary, key_points, impact_assessment, relevance_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (
            news.ts_code, news.name, news.news_date, news.title, news.content,
            news.source, news.url, news.sentiment_score, news.sentiment_label,
            news.ai_summary,
            json.dumps(news.key_points) if news.key_points else None,
            news.impact_assessment, news.relevance_score
        ))

    @classmethod
    def get_news_by_code_and_date(cls, ts_code: str, news_date: str) -> List[NewsSentiment]:
        """获取指定股票某日的新闻"""
        sql = """
            SELECT * FROM news_sentiment
            WHERE ts_code = %s AND news_date = %s
            ORDER BY relevance_score DESC
        """
        rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (ts_code, news_date))
        return [cls._row_to_news(r) for r in rows]

    @classmethod
    def get_recent_news(cls, ts_code: str, days: int = 7) -> List[NewsSentiment]:
        """获取指定股票近N天的新闻"""
        sql = """
            SELECT * FROM news_sentiment
            WHERE ts_code = %s AND news_date >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL %s DAY), '%Y%m%d')
            ORDER BY news_date DESC, relevance_score DESC
        """
        rows = DatabaseManager.fetchall(cls.DB_NAME, sql, (ts_code, days))
        return [cls._row_to_news(r) for r in rows]

    @staticmethod
    def _row_to_news(row: Dict) -> NewsSentiment:
        return NewsSentiment(
            id=row.get('id'),
            ts_code=row.get('ts_code', ''),
            name=row.get('name', ''),
            news_date=row.get('news_date', ''),
            title=row.get('title', ''),
            content=row.get('content'),
            source=row.get('source'),
            url=row.get('url'),
            sentiment_score=row.get('sentiment_score'),
            sentiment_label=row.get('sentiment_label'),
            ai_summary=row.get('ai_summary'),
            key_points=json.loads(row['key_points']) if row.get('key_points') else None,
            impact_assessment=row.get('impact_assessment'),
            relevance_score=row.get('relevance_score'),
            created_at=row.get('created_at')
        )


class MorningReportRepository:
    """晨间报告数据访问"""

    DB_NAME = "interface"

    @classmethod
    def save_report(cls, report: MorningReport) -> int:
        """保存晨间报告"""
        sql = """
            INSERT INTO morning_report
            (report_date, gold_stock_count, anomaly_count, buy_signals, sell_signals,
             summary, highlight_stocks, market_outlook, strategy_signals,
             markdown_path, pdf_path, sent_at, send_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
            gold_stock_count = new.gold_stock_count, anomaly_count = new.anomaly_count,
            buy_signals = new.buy_signals, sell_signals = new.sell_signals,
            summary = new.summary, highlight_stocks = new.highlight_stocks,
            market_outlook = new.market_outlook, strategy_signals = new.strategy_signals,
            markdown_path = new.markdown_path, pdf_path = new.pdf_path,
            sent_at = new.sent_at, send_status = new.send_status
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (
            report.report_date, report.gold_stock_count, report.anomaly_count,
            report.buy_signals, report.sell_signals, report.summary,
            json.dumps(report.highlight_stocks) if report.highlight_stocks else None,
            report.market_outlook,
            json.dumps(report.strategy_signals) if report.strategy_signals else None,
            report.markdown_path, report.pdf_path, report.sent_at, report.send_status
        ))

    @classmethod
    def get_report_by_date(cls, report_date: str) -> Optional[MorningReport]:
        """获取指定日期的报告"""
        sql = "SELECT * FROM morning_report WHERE report_date = %s"
        row = DatabaseManager.fetchone(cls.DB_NAME, sql, (report_date,))
        return cls._row_to_report(row) if row else None

    @classmethod
    def get_latest_report(cls) -> Optional[MorningReport]:
        """获取最新报告"""
        sql = "SELECT * FROM morning_report ORDER BY report_date DESC LIMIT 1"
        row = DatabaseManager.fetchone(cls.DB_NAME, sql)
        return cls._row_to_report(row) if row else None

    @staticmethod
    def _row_to_report(row: Dict) -> MorningReport:
        return MorningReport(
            id=row.get('id'),
            report_date=row.get('report_date', ''),
            gold_stock_count=row.get('gold_stock_count', 0),
            anomaly_count=row.get('anomaly_count', 0),
            buy_signals=row.get('buy_signals', 0),
            sell_signals=row.get('sell_signals', 0),
            summary=row.get('summary'),
            highlight_stocks=json.loads(row['highlight_stocks']) if row.get('highlight_stocks') else None,
            market_outlook=row.get('market_outlook'),
            strategy_signals=json.loads(row['strategy_signals']) if row.get('strategy_signals') else None,
            markdown_path=row.get('markdown_path'),
            pdf_path=row.get('pdf_path'),
            sent_at=row.get('sent_at'),
            send_status=row.get('send_status'),
            created_at=row.get('created_at')
        )


class ConfigRepository:
    """系统配置数据访问"""

    DB_NAME = "interface"

    @classmethod
    def get_config(cls, key: str, default: Any = None) -> Any:
        """获取配置值"""
        sql = "SELECT config_value, config_type FROM broker_gold_stock_config WHERE config_key = %s"
        row = DatabaseManager.fetchone(cls.DB_NAME, sql, (key,))
        if not row:
            return default

        value, value_type = row['config_value'], row['config_type']

        if value_type == 'int':
            return int(value)
        elif value_type == 'float':
            return float(value)
        elif value_type == 'json':
            return json.loads(value)
        else:
            return value

    @classmethod
    def set_config(cls, key: str, value: Any, value_type: str = 'string', description: str = '') -> int:
        """设置配置值"""
        if value_type == 'json':
            value = json.dumps(value)
        else:
            value = str(value)

        sql = """
            INSERT INTO broker_gold_stock_config (config_key, config_value, config_type, description)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
            config_value = new.config_value, config_type = new.config_type, description = new.description
        """
        return DatabaseManager.execute(cls.DB_NAME, sql, (key, value, value_type, description))
