"""
AI分析服务 - 共享服务层
提供统一的新闻分析和投资顾问功能
"""
import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict

try:
    import anthropic
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from projects.broker_gold_stock.data.models import (
    StockAnalysis, NewsSentiment, InvestmentAdvice, DailyStrategy
)


class AIService:
    """AI分析服务 - 使用Claude API进行智能分析"""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化Anthropic客户端"""
        if not HAS_ANTHROPIC:
            print("⚠️ anthropic 包未安装，AI功能将使用模拟模式")
            return

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠️ ANTHROPIC_API_KEY 未设置，AI功能将使用模拟模式")
            return

        try:
            self.client = Anthropic(api_key=api_key)
            print("✅ AI服务初始化成功")
        except Exception as e:
            print(f"❌ AI客户端初始化失败: {e}")

    def is_available(self) -> bool:
        """检查AI服务是否可用"""
        return self.client is not None

    async def analyze_news(self, news: NewsSentiment, stock_context: Dict = None) -> Dict[str, Any]:
        """
        分析新闻内容

        Args:
            news: 新闻对象
            stock_context: 股票上下文信息

        Returns:
            AI分析结果
        """
        if not self.is_available():
            return self._mock_news_analysis(news)

        prompt = self._build_news_analysis_prompt(news, stock_context)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # 解析响应
            result = self._parse_news_response(response.content[0].text)
            return result

        except Exception as e:
            print(f"AI新闻分析失败: {e}")
            return self._mock_news_analysis(news)

    async def analyze_opportunity(self, analysis: StockAnalysis) -> InvestmentAdvice:
        """
        分析买入机会

        Args:
            analysis: 股票分析结果

        Returns:
            InvestmentAdvice对象
        """
        if not self.is_available():
            return self._mock_opportunity_analysis(analysis)

        prompt = self._build_opportunity_prompt(analysis)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            result = self._parse_opportunity_response(response.content[0].text)

            return InvestmentAdvice(
                ts_code=analysis.ts_code,
                name=analysis.name,
                action=result.get('action', 'hold'),
                confidence=result.get('confidence', 0.5),
                reasoning=result.get('reasoning', ''),
                risk_factors=result.get('risk_factors', []),
                target_price=result.get('target_price'),
                stop_loss_price=result.get('stop_loss_price'),
                position_suggestion=result.get('position_suggestion')
            )

        except Exception as e:
            print(f"AI机会分析失败: {e}")
            return self._mock_opportunity_analysis(analysis)

    async def generate_daily_strategy(self, analyses: List[StockAnalysis], market_context: Dict = None) -> DailyStrategy:
        """
        生成每日投资策略

        Args:
            analyses: 分析结果列表
            market_context: 市场上下文

        Returns:
            DailyStrategy对象
        """
        if not self.is_available():
            return self._mock_strategy_generation(analyses)

        prompt = self._build_strategy_prompt(analyses, market_context)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.4,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            result = self._parse_strategy_response(response.content[0].text)

            return DailyStrategy(
                date=result.get('date', ''),
                market_outlook=result.get('market_outlook', ''),
                overall_position=result.get('overall_position', ''),
                style_bias=result.get('style_bias', ''),
                risk_level=result.get('risk_level', ''),
                focus_stocks=result.get('focus_stocks', []),
                dip_buying=result.get('dip_buying', []),
                profit_taking=result.get('profit_taking', []),
                avoid_stocks=result.get('avoid_stocks', []),
                summary=result.get('summary', '')
            )

        except Exception as e:
            print(f"AI策略生成失败: {e}")
            return self._mock_strategy_generation(analyses)

    def _build_news_analysis_prompt(self, news: NewsSentiment, context: Dict = None) -> str:
        """构建新闻分析提示词"""
        context_str = ""
        if context:
            context_str = f"""
股票信息:
- 股票代码: {context.get('ts_code', '')}
- 股票名称: {context.get('name', '')}
- 所属行业: {context.get('industry', '')}
- 当前价格: {context.get('price', 'N/A')}
"""

        prompt = f"""请分析以下股票新闻，判断其对股价的影响:

新闻标题: {news.title}
新闻内容: {news.content[:1000] if news.content else '无详细内容'}
新闻来源: {news.source or '未知'}
{context_str}

请以JSON格式返回分析结果:
{{
    "sentiment": "positive/negative/neutral",
    "sentiment_score": 0.5,  // -1到1之间
    "summary": "新闻摘要，50字以内",
    "key_points": ["要点1", "要点2", "要点3"],
    "impact_assessment": "重大利好/利好/中性/利空/重大利空",
    "relevance_score": 0.8  // 0到1之间，新闻与股票的相关度
}}
"""
        return prompt

    def _build_opportunity_prompt(self, analysis: StockAnalysis) -> str:
        """构建投资机会分析提示词"""

        technical_str = ""
        if analysis.technical:
            technical_str = f"""
技术面评分: {analysis.technical.total}/100
- 趋势评分: {analysis.technical.trend_score}
- 动量评分: {analysis.technical.momentum_score}
- 关键信号: {', '.join([s['name'] for s in analysis.technical.signals[:3]])}
"""

        financial_str = ""
        if analysis.financial:
            financial_str = f"""
财务面评分: {analysis.financial.total}/100
- 估值评分: {analysis.financial.valuation_score}
- 盈利能力: {analysis.financial.profitability_score}
- 成长性: {analysis.financial.growth_score}
"""

        quant_str = ""
        if analysis.quant:
            quant_str = f"""
量化因子评分: {analysis.quant.total}/100
- 估值因子: {analysis.quant.value}
- 动量因子: {analysis.quant.momentum}
- 质量因子: {analysis.quant.quality}
"""

        anomaly_str = ""
        if analysis.anomalies:
            anomaly_str = f"""
近期异动:
{chr(10).join([f"- {a.anomaly_type}: {a.severity.value}" for a in analysis.anomalies[:3]])}
"""

        prompt = f"""请分析以下股票的投资机会:

股票代码: {analysis.ts_code}
股票名称: {analysis.name}
综合评分: {analysis.composite_score}/100

{technical_str}
{financial_str}
{quant_str}
{anomaly_str}

请以JSON格式返回投资建议:
{{
    "action": "strong_buy/buy/hold/reduce/avoid",
    "confidence": 0.75,  // 0到1之间
    "reasoning": "详细的分析理由，100字以内",
    "risk_factors": ["风险1", "风险2"],
    "target_price": 15.50,  // 目标价，可选
    "stop_loss_price": 12.00,  // 止损价，可选
    "position_suggestion": "建议仓位: 5-8%"
}}
"""
        return prompt

    def _build_strategy_prompt(self, analyses: List[StockAnalysis], context: Dict = None) -> str:
        """构建策略生成提示词"""

        # 获取评分最高的几只股票
        top_stocks = sorted(analyses, key=lambda x: x.composite_score, reverse=True)[:10]

        stocks_str = "\n".join([
            f"{s.ts_code} ({s.name}): 综合评分{s.composite_score}, "
            f"技术{s.technical.total if s.technical else 'N/A'}, "
            f"财务{s.financial.total if s.financial else 'N/A'}"
            for s in top_stocks
        ])

        market_str = ""
        if context:
            market_str = f"""
市场概况:
- 沪深300走势: {context.get('hs300_trend', 'N/A')}
- 成交量: {context.get('volume', 'N/A')}
- 北向资金: {context.get('northbound', 'N/A')}
"""

        prompt = f"""请基于以下分析结果，生成今日投资策略:

重点关注的金股及评分:
{stocks_str}

{market_str}

请以JSON格式返回策略:
{{
    "date": "20260310",
    "market_outlook": "市场展望，50字以内",
    "overall_position": "建议仓位: 70%",
    "style_bias": "成长/价值/均衡",
    "risk_level": "高/中/低",
    "focus_stocks": ["代码1", "代码2"],  // 开盘关注
    "dip_buying": ["代码3"],  // 逢低布局
    "profit_taking": ["代码4"],  // 止盈考虑
    "avoid_stocks": ["代码5"],  // 规避
    "summary": "策略总结，100字以内"
}}
"""
        return prompt

    def _parse_news_response(self, text: str) -> Dict[str, Any]:
        """解析新闻分析响应"""
        try:
            # 尝试提取JSON
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end + 1]
                return json.loads(json_str)
        except:
            pass

        return {
            "sentiment": "neutral",
            "sentiment_score": 0,
            "summary": text[:100],
            "key_points": [],
            "impact_assessment": "中性",
            "relevance_score": 0.5
        }

    def _parse_opportunity_response(self, text: str) -> Dict[str, Any]:
        """解析机会分析响应"""
        try:
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end + 1]
                return json.loads(json_str)
        except:
            pass

        return {
            "action": "hold",
            "confidence": 0.5,
            "reasoning": text[:200],
            "risk_factors": [],
            "target_price": None,
            "stop_loss_price": None,
            "position_suggestion": "观望"
        }

    def _parse_strategy_response(self, text: str) -> Dict[str, Any]:
        """解析策略响应"""
        try:
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end + 1]
                return json.loads(json_str)
        except:
            pass

        from datetime import datetime
        return {
            "date": datetime.now().strftime('%Y%m%d'),
            "market_outlook": "市场震荡",
            "overall_position": "建议仓位: 50%",
            "style_bias": "均衡",
            "risk_level": "中",
            "focus_stocks": [],
            "dip_buying": [],
            "profit_taking": [],
            "avoid_stocks": [],
            "summary": text[:200]
        }

    def _mock_news_analysis(self, news: NewsSentiment) -> Dict[str, Any]:
        """模拟新闻分析（当AI不可用时）"""
        return {
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "summary": news.title[:50] + "...",
            "key_points": ["AI服务暂不可用"],
            "impact_assessment": "中性",
            "relevance_score": 0.5
        }

    def _mock_opportunity_analysis(self, analysis: StockAnalysis) -> InvestmentAdvice:
        """模拟机会分析（当AI不可用时）"""
        from projects.broker_gold_stock.analysis.composite_scorer import CompositeScorer

        scorer = CompositeScorer()
        return scorer.generate_advice(analysis)

    def _mock_strategy_generation(self, analyses: List[StockAnalysis]) -> DailyStrategy:
        """模拟策略生成（当AI不可用时）"""
        from datetime import datetime

        # 根据评分生成简单策略
        top_buy = [a.ts_code for a in analyses if a.composite_score >= 75][:3]
        top_sell = [a.ts_code for a in analyses if a.composite_score < 50][:3]

        return DailyStrategy(
            date=datetime.now().strftime('%Y%m%d'),
            market_outlook="市场震荡整理，建议谨慎操作",
            overall_position="建议仓位: 60%",
            style_bias="均衡配置",
            risk_level="中等",
            focus_stocks=top_buy,
            dip_buying=top_buy[:2] if len(top_buy) >= 2 else top_buy,
            profit_taking=top_sell,
            avoid_stocks=top_sell,
            summary="基于量化评分生成的策略，建议关注高分金股，规避低分股票。AI服务当前不可用，使用简化分析。"
        )


# 单例模式
_ai_service = None

def get_ai_service() -> AIService:
    """获取AI服务单例"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
