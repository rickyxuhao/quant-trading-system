"""
Tushare 申万行业成分股同步任务
接口: index_member_all
数据范围: 全量（当前最新成分）
策略: 全量同步（成分股每日更新）
方式: 流式处理，先获取所有行业代码，再逐个获取成分股
"""
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client
from core.data_sync.tasks.rate_limiter import RateLimiter
from core.storage.relational.connection import DatabaseManager


class TushareSwMemberTask(BaseTushareTask):
    """Tushare 申万行业成分股同步任务"""

    def __init__(self, name: str = "sw_member", check_after_sync: bool = True,
                 batch_size: int = 1000, max_requests_per_minute: int = 500):
        super().__init__(
            name=name,
            table_name="t_sw_member",
            db_name="tushare_biz",
            sync_type="full",
            check_after_sync=check_after_sync,
            batch_size=batch_size
        )
        self.tushare = get_tushare_client()
        self.rate_limiter = RateLimiter(max_requests_per_minute)

    def fetch_data(self) -> pd.DataFrame:
        """
        从 Tushare 获取申万行业成分股数据
        """
        print("📥 从 Tushare 获取申万行业成分股数据...")

        # 获取所有一级行业代码
        industries = self._get_industry_codes()

        if not industries:
            print("⚠️ 无行业代码可用")
            return pd.DataFrame()

        print(f"   需要获取 {len(industries)} 个一级行业的成分股")

        all_members = []
        total_requests = 0

        for i, (code, name) in enumerate(industries, 1):
            print(f"   [{i}/{len(industries)}] 获取 {name}({code}) 成分股...", end=" ")

            try:
                self.rate_limiter.wait_if_needed()

                # 获取行业成分股
                df = self.tushare.pro.query(
                    'index_member_all',
                    index_code=code,
                    limit=5000
                )

                total_requests += 1

                if not df.empty:
                    all_members.append(df)
                    print(f"✓ {len(df)} 只")
                else:
                    print("无数据")

            except Exception as e:
                print(f"✗ 失败: {e}")
                continue

        if not all_members:
            return pd.DataFrame()

        # 合并所有成分股
        combined = pd.concat(all_members, ignore_index=True)
        combined['trade_date'] = datetime.now().strftime('%Y%m%d')
        combined['is_new'] = 1

        print(f"\n   总计获取 {len(combined)} 条成分股记录")
        print(f"   总请求次数: {total_requests}")

        return combined

    def _get_industry_codes(self) -> List[tuple]:
        """获取所有申万一级行业代码"""
        # 从分类表获取
        results = DatabaseManager.fetchall(
            self.db_name,
            "SELECT ts_code, name FROM t_sw_classify WHERE level = 1 ORDER BY ts_code"
        )

        if results:
            return [(r['ts_code'], r['name']) for r in results]

        # 如果分类表为空，使用预定义的一级行业代码
        return [
            ('801010', '农林牧渔'), ('801020', '采掘'), ('801030', '化工'),
            ('801040', '钢铁'), ('801050', '有色金属'), ('801080', '电子'),
            ('801110', '家用电器'), ('801120', '食品饮料'), ('801130', '纺织服装'),
            ('801140', '轻工制造'), ('801150', '医药生物'), ('801160', '公用事业'),
            ('801170', '交通运输'), ('801180', '房地产'), ('801200', '商业贸易'),
            ('801210', '休闲服务'), ('801230', '综合'), ('801710', '建筑材料'),
            ('801720', '建筑装饰'), ('801730', '电气设备'), ('801740', '国防军工'),
            ('801750', '计算机'), ('801760', '传媒'), ('801770', '通信'),
            ('801780', '银行'), ('801790', '非银金融'), ('801880', '汽车'),
            ('801890', '机械设备'),
        ]

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        同步数据到 MySQL
        """
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        # 将旧数据标记为 is_new=0
        print("   标记旧数据...")
        DatabaseManager.execute(
            self.db_name,
            f"UPDATE {self.table_name} SET is_new = 0 WHERE is_new = 1"
        )

        columns = ['index_code', 'index_name', 'con_code', 'con_name', 'trade_date',
                   'level', 'in_date', 'out_date', 'is_new']

        # Tushare API 返回的列名映射
        # l1_code/l1_name -> 一级行业, ts_code/name -> 股票代码/名称
        df = df.rename(columns={
            'l1_code': 'index_code',
            'l1_name': 'index_name',
            'ts_code': 'con_code',
            'name': 'con_name',
        })

        # 删除 index_code 为空的行
        df = df.dropna(subset=['index_code', 'con_code'])

        # 转换 is_new (Y -> 1, N -> 0)
        df['is_new'] = df['is_new'].apply(lambda x: 1 if x == 'Y' else 0)

        # 插入新数据
        result = self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['index_code', 'con_code', 'trade_date'],
            update_columns=['index_name', 'con_name', 'level', 'in_date', 'out_date', 'is_new']
        )

        print(f"   同步完成: {result['affected']} 条")
        return result
