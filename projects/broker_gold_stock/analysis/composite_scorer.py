"""
综合评分器
整合多维度分析结果，生成综合评分
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from projects.broker_gold_stock.data.models import (
    StockAnalysis, TechnicalScore, FinancialScore, FactorScore,
    InvestmentAdvice, Recommendation
)
from projects.broker_gold_stock.data.repository import ConfigRepository


@dataclass
class ScoreWeights:
    """评分权重配置"""
    technical: float = 0.30
    financial: float = 0.30
    quant: float = 0.30
    sentiment: float = 0.10


class CompositeScorer:
    """
    综合评分器

    整合技术、财务、量化因子三个维度的评分，
    生成综合评分和投资建议
    """

    def __init__(self):
        self.weights = self._load_weights()

    def _load_weights(self) -> ScoreWeights:
        """从数据库加载权重配置"""
        try:
            technical = ConfigRepository.get_config('analysis.weight.technical', 0.30)
            financial = ConfigRepository.get_config('analysis.weight.financial', 0.30)
            quant = ConfigRepository.get_config('analysis.weight.quant', 0.30)
            sentiment = ConfigRepository.get_config('analysis.weight.sentiment', 0.10)

            return ScoreWeights(
                technical=float(technical),
                financial=float(financial),
                quant=float(quant),
                sentiment=float(sentiment)
            )
        except Exception as e:
            print(f"加载权重配置失败，使用默认值: {e}")
            return ScoreWeights()

    def calculate_composite_score(self, analysis: StockAnalysis) -> float:
        """
        计算综合评分 - 包含券商共识度因子

        Args:
            analysis: 股票分析结果

        Returns:
            综合评分(0-100)
        """
        scores = []
        weights = []

        # 技术评分
        if analysis.technical:
            scores.append(analysis.technical.total)
            weights.append(self.weights.technical)

        # 财务评分
        if analysis.financial:
            scores.append(analysis.financial.total)
            weights.append(self.weights.financial)

        # 量化因子评分
        if analysis.quant and analysis.quant.total:
            scores.append(analysis.quant.total)
            weights.append(self.weights.quant)

        if not scores:
            return 50.0

        # 加权平均
        total_weight = sum(weights)
        if total_weight == 0:
            return 50.0

        base_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

        # 应用券商共识度加分
        consensus_bonus = self._calculate_consensus_bonus(analysis.broker_count)
        analysis.consensus_score = consensus_bonus

        composite = base_score + consensus_bonus

        return round(min(100, max(0, composite)), 2)

    def _calculate_consensus_bonus(self, broker_count: int) -> float:
        """
        计算券商共识度加分

        被多家券商推荐的股票，说明市场共识度高，给予适当加分

        Args:
            broker_count: 推荐该股票的券商数量

        Returns:
            加分值(0-10)
        """
        if broker_count <= 1:
            return 0
        elif broker_count == 2:
            return 2  # 2家推荐 +2分
        elif broker_count == 3:
            return 4  # 3家推荐 +4分
        elif broker_count == 4:
            return 6  # 4家推荐 +6分
        elif broker_count == 5:
            return 8  # 5家推荐 +8分
        else:
            return 10  # 6家及以上推荐 +10分（封顶）

    def generate_advice(self, analysis: StockAnalysis) -> InvestmentAdvice:
        """
        生成投资建议

        Args:
            analysis: 股票分析结果

        Returns:
            InvestmentAdvice对象
        """
        score = self.calculate_composite_score(analysis)

        # 根据评分确定建议动作
        action, confidence = self._score_to_recommendation(score, analysis)

        # 生成理由
        reasoning = self._generate_reasoning(analysis, score)

        # 生成风险提示
        risk_factors = self._generate_risk_factors(analysis)

        # 仓位建议
        position = self._generate_position_advice(score, action)

        return InvestmentAdvice(
            ts_code=analysis.ts_code,
            name=analysis.name,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            risk_factors=risk_factors,
            position_suggestion=position
        )

    def _score_to_recommendation(self, score: float, analysis: StockAnalysis) -> tuple:
        """
        将评分转换为建议动作

        Returns:
            (Recommendation, confidence)
        """
        # 考虑异动情况
        has_critical_anomaly = any(
            a.severity.value in ['high', 'critical']
            for a in analysis.anomalies
        )

        if score >= 85:
            if has_critical_anomaly:
                return Recommendation.HOLD, 0.6
            return Recommendation.STRONG_BUY, 0.85
        elif score >= 70:
            if has_critical_anomaly:
                return Recommendation.HOLD, 0.5
            return Recommendation.BUY, 0.75
        elif score >= 55:
            return Recommendation.HOLD, 0.6
        elif score >= 40:
            return Recommendation.REDUCE, 0.55
        else:
            return Recommendation.AVOID, 0.70

    def _generate_reasoning(self, analysis: StockAnalysis, score: float) -> str:
        """生成推荐理由"""
        reasons = []

        # 技术面理由
        if analysis.technical:
            if analysis.technical.total >= 75:
                signals = [s['name'] for s in analysis.technical.signals[:2] if s.get('score', 0) > 0]
                if signals:
                    reasons.append(f"技术面表现强势: {', '.join(signals)}")
            elif analysis.technical.total <= 40:
                reasons.append("技术面走弱，注意风险")

        # 财务面理由
        if analysis.financial:
            if analysis.financial.total >= 75:
                reasons.append("财务指标优秀，基本面扎实")
            elif analysis.financial.total >= 60:
                reasons.append("财务状况良好")

        # 量化因子理由
        if analysis.quant:
            if analysis.quant.total and analysis.quant.total >= 75:
                reasons.append("量化因子评分领先")

        # 综合理由
        if score >= 80:
            reasons.insert(0, "综合评分优秀，多维度指标向好")
        elif score >= 60:
            reasons.insert(0, "综合评分良好")
        elif score < 50:
            reasons.insert(0, "综合评分偏低，建议谨慎")

        return "; ".join(reasons) if reasons else "综合评分中性，建议观望"

    def _generate_risk_factors(self, analysis: StockAnalysis) -> List[str]:
        """生成风险提示"""
        risks = []

        # 技术面风险
        if analysis.technical:
            negative_signals = [s['name'] for s in analysis.technical.signals if s.get('score', 0) < 0]
            if negative_signals:
                risks.append(f"技术面: {', '.join(negative_signals[:2])}")

        # 异动风险
        if analysis.anomalies:
            recent_anomalies = [a for a in analysis.anomalies if a.severity.value in ['high', 'critical']]
            if recent_anomalies:
                risks.append(f"近期有{len(recent_anomalies)}项异常波动")

        # 综合风险
        if analysis.technical and analysis.technical.total < 40:
            risks.append("技术走势偏弱")

        return risks if risks else ["暂无重大风险"]

    def _generate_position_advice(self, score: float, action: Recommendation) -> str:
        """生成仓位建议"""
        if action == Recommendation.STRONG_BUY:
            return "建议仓位: 8-10%"
        elif action == Recommendation.BUY:
            return "建议仓位: 5-8%"
        elif action == Recommendation.HOLD:
            return "建议仓位: 3-5%"
        elif action == Recommendation.REDUCE:
            return "建议减仓至: 1-3%"
        else:
            return "建议清仓观望"

    def rank_stocks(self, analyses: List[StockAnalysis], top_n: int = 20) -> List[Dict[str, Any]]:
        """
        对股票进行排名

        Args:
            analyses: 分析结果列表
            top_n: 返回前N名

        Returns:
            排名结果列表
        """
        ranked = []

        for analysis in analyses:
            score = self.calculate_composite_score(analysis)
            advice = self.generate_advice(analysis)

            ranked.append({
                'ts_code': analysis.ts_code,
                'name': analysis.name,
                'composite_score': score,
                'broker_count': analysis.broker_count,
                'consensus_score': analysis.consensus_score,
                'technical_score': analysis.technical.total if analysis.technical else None,
                'financial_score': analysis.financial.total if analysis.financial else None,
                'quant_score': analysis.quant.total if analysis.quant else None,
                'recommendation': advice.action.value,
                'confidence': advice.confidence,
                'reasoning': advice.reasoning,
                'anomalies': len(analysis.anomalies)
            })

        # 按综合评分排序
        ranked.sort(key=lambda x: x['composite_score'], reverse=True)

        return ranked[:top_n]


class MultiDimensionAnalyzer:
    """
    多维度分析器

    整合技术、财务、量化因子分析
    """

    def __init__(self):
        from projects.broker_gold_stock.analysis.technical_analyzer import TechnicalAnalyzer
        from projects.broker_gold_stock.analysis.financial_analyzer import FinancialAnalyzer
        from projects.broker_gold_stock.analysis.quant_factor_analyzer import QuantFactorAnalyzer
        from projects.broker_gold_stock.analysis.anomaly_detector import AnomalyDetector

        self.technical = TechnicalAnalyzer()
        self.financial = FinancialAnalyzer()
        self.quant = QuantFactorAnalyzer()
        self.anomaly = AnomalyDetector()
        self.scorer = CompositeScorer()

    def analyze_stock(self, ts_code: str, name: str = "", trade_date: str = None,
                       broker_count: int = 1, industry: str = "") -> StockAnalysis:
        """
        对单只股票进行多维度分析

        Args:
            ts_code: 股票代码
            name: 股票名称
            trade_date: 分析日期
            broker_count: 推荐该股票的券商数量
            industry: 所属行业

        Returns:
            StockAnalysis对象
        """
        if trade_date is None:
            from datetime import datetime
            trade_date = datetime.now().strftime('%Y%m%d')

        print(f"🔍 分析 {ts_code} ({name})...")

        # 数据溯源记录
        data_sources = {
            'technical': {},
            'financial': {},
            'quant': {},
            'analysis_date': trade_date
        }

        # 技术分析
        try:
            technical, tech_source = self.technical.analyze(ts_code)
            data_sources['technical'] = tech_source
            data_sources['technical']['score'] = technical.total if technical else 0
            print(f"   技术评分: {technical.total}")
        except Exception as e:
            print(f"   技术分析失败: {e}")
            technical = None

        # 财务分析
        try:
            financial, fin_source = self.financial.analyze(ts_code)
            data_sources['financial'] = fin_source
            data_sources['financial']['score'] = financial.total if financial else 0
            print(f"   财务评分: {financial.total}")
        except Exception as e:
            print(f"   财务分析失败: {e}")
            financial = None

        # 量化因子分析
        try:
            quant, quant_source = self.quant.analyze(ts_code, trade_date)
            data_sources['quant'] = quant_source
            data_sources['quant']['score'] = quant.total if quant else 0
            print(f"   量化评分: {quant.total}")
        except Exception as e:
            print(f"   量化分析失败: {e}")
            quant = None

        # 异动检测
        try:
            anomalies = self.anomaly.detect(ts_code, name)
            if anomalies:
                print(f"   检测到 {len(anomalies)} 项异动")
        except Exception as e:
            print(f"   异动检测失败: {e}")
            anomalies = []

        # 构建分析结果
        analysis = StockAnalysis(
            ts_code=ts_code,
            name=name,
            trade_date=trade_date,
            technical=technical,
            financial=financial,
            quant=quant,
            anomalies=anomalies,
            broker_count=broker_count,
            industry=industry,
            data_sources=data_sources
        )

        # 计算综合评分
        analysis.composite_score = self.scorer.calculate_composite_score(analysis)
        print(f"   综合评分: {analysis.composite_score} (含{analysis.consensus_score:.0f}分共识度加分)")

        return analysis

    def analyze_stocks(self, ts_codes: List[str], names: Dict[str, str] = None,
                       broker_counts: Dict[str, int] = None,
                       industries: Dict[str, str] = None) -> List[StockAnalysis]:
        """
        批量分析多只股票

        Args:
            ts_codes: 股票代码列表
            names: 代码到名称的映射
            broker_counts: 代码到券商推荐数量的映射
            industries: 代码到行业的映射

        Returns:
            分析结果列表
        """
        names = names or {}
        broker_counts = broker_counts or {}
        industries = industries or {}
        results = []

        for ts_code in ts_codes:
            try:
                analysis = self.analyze_stock(
                    ts_code,
                    names.get(ts_code, ""),
                    broker_count=broker_counts.get(ts_code, 1),
                    industry=industries.get(ts_code, "")
                )
                results.append(analysis)
            except Exception as e:
                print(f"❌ 分析 {ts_code} 失败: {e}")

        return results
