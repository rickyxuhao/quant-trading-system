"""
新闻服务 - 获取和分析股票新闻
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import re

from core.data_access.tushare.client import TushareClient
from projects.broker_gold_stock.data.models import NewsSentiment
from projects.broker_gold_stock.data.repository import NewsRepository
from projects.broker_gold_stock.shared.services.ai_service import get_ai_service


class NewsService:
    """新闻服务 - 获取股票新闻并进行情感分析"""

    def __init__(self):
        self.ts_client = TushareClient()

    def fetch_stock_news(self, ts_code: str, name: str = "",
                         start_date: str = None, end_date: str = None,
                         limit: int = 10) -> List[NewsSentiment]:
        """
        获取股票新闻 - Tushare优先，AkShare作为备用

        Args:
            ts_code: 股票代码
            name: 股票名称
            start_date: 开始日期
            end_date: 结束日期
            limit: 数量限制

        Returns:
            新闻列表
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

        # 1. 尝试使用Tushare获取新闻
        news_list = self._fetch_from_tushare(ts_code, name, start_date, end_date, limit)

        # 2. 如果Tushare没有获取到足够新闻，尝试AkShare
        if len(news_list) < limit // 2:
            print(f"   Tushare新闻不足({len(news_list)}条)，尝试AkShare...")
            akshare_news = self._fetch_from_akshare(ts_code, name, start_date, end_date, limit - len(news_list))
            news_list.extend(akshare_news)

        return news_list[:limit]

    def _fetch_from_tushare(self, ts_code: str, name: str,
                           start_date: str, end_date: str, limit: int) -> List[NewsSentiment]:
        """从Tushare获取新闻"""
        news_list = []

        try:
            # 使用major_news接口获取重要新闻
            df = self.ts_client.query(
                'major_news',
                start_date=start_date,
                end_date=end_date,
                src='sina'  # 新浪新闻
            )

            if not df.empty:
                # 过滤与股票相关的新闻
                for _, row in df.head(limit * 3).iterrows():  # 获取更多，过滤后保留limit
                    content = str(row.get('content', ''))
                    title = str(row.get('title', ''))

                    # 检查是否相关
                    if self._is_relevant(title + content, ts_code, name):
                        news = NewsSentiment(
                            ts_code=ts_code,
                            name=name,
                            news_date=str(row.get('datetime', end_date))[:8],
                            title=title[:500],
                            content=content[:2000] if content else None,
                            source=row.get('src', 'unknown'),
                            url=row.get('url', '')
                        )
                        news_list.append(news)

                        if len(news_list) >= limit:
                            break

        except Exception as e:
            print(f"Tushare新闻获取失败 {ts_code}: {e}")

        return news_list

    def _fetch_from_akshare(self, ts_code: str, name: str,
                           start_date: str, end_date: str, limit: int) -> List[NewsSentiment]:
        """从AkShare获取新闻作为备用"""
        try:
            from projects.broker_gold_stock.data.sync.akshare_news_sync import get_akshare_news

            akshare_sync = get_akshare_news()
            if akshare_sync.is_available():
                days = (datetime.strptime(end_date, '%Y%m%d') -
                       datetime.strptime(start_date, '%Y%m%d')).days
                return akshare_sync.fetch_stock_news(ts_code, name, days, limit)
        except Exception as e:
            print(f"AkShare新闻获取失败 {ts_code}: {e}")

        return []

    def analyze_sentiment(self, news: NewsSentiment,
                          stock_context: Dict = None) -> NewsSentiment:
        """
        使用AI分析新闻情感

        Args:
            news: 新闻对象
            stock_context: 股票上下文

        Returns:
            带有AI分析的新闻对象
        """
        try:
            ai_service = get_ai_service()
            result = ai_service.analyze_news(news, stock_context)

            news.sentiment_score = result.get('sentiment_score', 0)
            news.sentiment_label = result.get('sentiment', 'neutral')
            news.ai_summary = result.get('summary', '')
            news.key_points = result.get('key_points', [])
            news.impact_assessment = result.get('impact_assessment', '中性')
            news.relevance_score = result.get('relevance_score', 0.5)

        except Exception as e:
            print(f"AI新闻分析失败: {e}")
            # 使用简单规则分析
            news = self._rule_based_sentiment(news)

        return news

    def get_and_analyze_news(self, ts_code: str, name: str = "",
                             days: int = 3) -> List[NewsSentiment]:
        """
        获取并分析股票新闻

        Args:
            ts_code: 股票代码
            name: 股票名称
            days: 最近几天

        Returns:
            分析后的新闻列表
        """
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取新闻
        news_list = self.fetch_stock_news(ts_code, name, start_date, end_date)

        if not news_list:
            return []

        # 分析每条新闻
        analyzed_news = []
        for news in news_list:
            try:
                analyzed = self.analyze_sentiment(news, {
                    'ts_code': ts_code,
                    'name': name
                })
                analyzed_news.append(analyzed)

                # 保存到数据库
                NewsRepository.save_news(analyzed)

            except Exception as e:
                print(f"分析新闻失败: {e}")
                analyzed_news.append(news)

        return analyzed_news

    def _is_relevant(self, content: str, ts_code: str, name: str) -> bool:
        """检查新闻是否与股票相关"""
        if not content:
            return False

        content = content.lower()

        # 股票代码匹配 (去掉后缀)
        code_base = ts_code.split('.')[0] if '.' in ts_code else ts_code

        # 检查是否包含股票名称或代码
        keywords = [code_base, name] if name else [code_base]

        for keyword in keywords:
            if keyword and keyword in content:
                return True

        return False

    def _rule_based_sentiment(self, news: NewsSentiment) -> NewsSentiment:
        """基于规则的简单情感分析"""
        content = (news.title + ' ' + (news.content or '')).lower()

        # 正面词汇
        positive_words = ['利好', '增长', '盈利', '上涨', '突破', '扩张',
                          '增持', '买入', '推荐', '优秀', '超预期', '分红']

        # 负面词汇
        negative_words = ['利空', '亏损', '下跌', '跌破', '减持', '卖出',
                          '回避', '风险', '暴雷', '罚款', '调查', '召回']

        pos_count = sum(1 for w in positive_words if w in content)
        neg_count = sum(1 for w in negative_words if w in content)

        total = pos_count + neg_count
        if total == 0:
            news.sentiment_score = 0
            news.sentiment_label = 'neutral'
            news.impact_assessment = '中性'
        else:
            score = (pos_count - neg_count) / max(total, 3)
            news.sentiment_score = round(max(-1, min(1, score)), 2)

            if score > 0.3:
                news.sentiment_label = 'positive'
                news.impact_assessment = '利好'
            elif score < -0.3:
                news.sentiment_label = 'negative'
                news.impact_assessment = '利空'
            else:
                news.sentiment_label = 'neutral'
                news.impact_assessment = '中性'

        news.ai_summary = news.title[:100]
        news.key_points = []
        news.relevance_score = 0.8

        return news

    def get_recent_sentiment_summary(self, ts_code: str, days: int = 7) -> Dict[str, Any]:
        """
        获取近期舆情摘要

        Args:
            ts_code: 股票代码
            days: 最近几天

        Returns:
            舆情摘要
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 从数据库查询
        news_list = NewsRepository.get_recent_news(ts_code, days)

        if not news_list:
            return {
                'avg_sentiment': 0,
                'sentiment_label': 'neutral',
                'news_count': 0,
                'summary': '近期无相关新闻'
            }

        # 计算平均情感得分
        scores = [n.sentiment_score for n in news_list if n.sentiment_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0

        # 统计正面/负面数量
        positive = sum(1 for n in news_list if n.sentiment_label == 'positive')
        negative = sum(1 for n in news_list if n.sentiment_label == 'negative')
        neutral = len(news_list) - positive - negative

        if avg_score > 0.2:
            label = 'positive'
        elif avg_score < -0.2:
            label = 'negative'
        else:
            label = 'neutral'

        return {
            'avg_sentiment': round(avg_score, 2),
            'sentiment_label': label,
            'news_count': len(news_list),
            'positive_count': positive,
            'negative_count': negative,
            'neutral_count': neutral,
            'summary': f"近{days}天共{len(news_list)}条新闻，正面{positive}条，负面{negative}条"
        }
