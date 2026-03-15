"""
AkShare新闻同步模块
作为Tushare新闻接口的备用方案
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    print("⚠️ akshare 未安装，将使用备用新闻源")

from projects.broker_gold_stock.data.models import NewsSentiment
from projects.broker_gold_stock.data.repository import NewsRepository


class AkShareNewsSync:
    """
    AkShare新闻同步器
    从东方财富获取财经新闻作为Tushare的备用
    """

    def __init__(self):
        self.enabled = HAS_AKSHARE

    def is_available(self) -> bool:
        """检查AkShare是否可用"""
        return self.enabled

    def fetch_stock_news(self, ts_code: str, name: str = "",
                         days: int = 3, limit: int = 10) -> List[NewsSentiment]:
        """
        获取个股相关新闻

        Args:
            ts_code: 股票代码
            name: 股票名称
            days: 最近几天
            limit: 数量限制

        Returns:
            新闻列表
        """
        if not self.enabled:
            return []

        news_list = []

        try:
            # 获取东方财富财经新闻
            df = ak.stock_news_em()

            if df.empty:
                return []

            # 过滤相关新闻
            code_base = ts_code.split('.')[0] if '.' in ts_code else ts_code
            keywords = [code_base, name] if name else [code_base]

            # 内容匹配
            for _, row in df.iterrows():
                title = str(row.get('title', ''))
                content = str(row.get('content', ''))

                # 检查相关性
                if self._is_relevant(title + content, keywords):
                    # 解析日期
                    news_date = str(row.get('datetime', ''))[:10].replace('-', '')
                    if not news_date:
                        news_date = datetime.now().strftime('%Y%m%d')

                    news = NewsSentiment(
                        ts_code=ts_code,
                        name=name,
                        news_date=news_date,
                        title=title[:500],
                        content=content[:2000] if content else None,
                        source='东方财富',
                        url=row.get('url', '')
                    )
                    news_list.append(news)

                    if len(news_list) >= limit:
                        break

        except Exception as e:
            print(f"获取AkShare新闻失败 {ts_code}: {e}")

        return news_list[:limit]

    def fetch_industry_news(self, industry: str, days: int = 3,
                           limit: int = 10) -> List[NewsSentiment]:
        """
        获取行业新闻

        Args:
            industry: 行业名称
            days: 最近几天
            limit: 数量限制

        Returns:
            新闻列表
        """
        if not self.enabled or not industry:
            return []

        try:
            # 获取财经要闻
            df = ak.stock_news_main_cx()

            if df.empty:
                return []

            news_list = []
            for _, row in df.head(limit * 2).iterrows():
                title = str(row.get('title', ''))
                content = str(row.get('content', ''))

                # 检查是否包含行业关键词
                if industry in title or industry in content:
                    news = NewsSentiment(
                        ts_code='INDUSTRY',
                        name=industry,
                        news_date=datetime.now().strftime('%Y%m%d'),
                        title=title[:500],
                        content=content[:2000] if content else None,
                        source='财经新闻',
                        url=''
                    )
                    news_list.append(news)

                    if len(news_list) >= limit:
                        break

            return news_list

        except Exception as e:
            print(f"获取行业新闻失败 {industry}: {e}")
            return []

    def _is_relevant(self, content: str, keywords: List[str]) -> bool:
        """检查新闻是否与关键词相关"""
        if not content:
            return False

        content = content.lower()

        for keyword in keywords:
            if keyword and keyword.lower() in content:
                return True

        return False

    def sync_and_analyze(self, ts_code: str, name: str = "",
                         days: int = 3) -> List[NewsSentiment]:
        """
        同步并分析新闻

        Args:
            ts_code: 股票代码
            name: 股票名称
            days: 最近几天

        Returns:
            分析后的新闻列表
        """
        from projects.broker_gold_stock.shared.services.news_service import NewsService

        # 获取新闻
        news_list = self.fetch_stock_news(ts_code, name, days)

        if not news_list:
            return []

        # 使用NewsService进行情感分析
        news_service = NewsService()
        analyzed_news = []

        for news in news_list:
            try:
                # 简单的规则分析
                analyzed = news_service._rule_based_sentiment(news)

                # 保存到数据库
                NewsRepository.save_news(analyzed)
                analyzed_news.append(analyzed)

            except Exception as e:
                print(f"分析新闻失败: {e}")
                analyzed_news.append(news)

        return analyzed_news


def get_akshare_news() -> AkShareNewsSync:
    """获取AkShare新闻同步器实例"""
    return AkShareNewsSync()
