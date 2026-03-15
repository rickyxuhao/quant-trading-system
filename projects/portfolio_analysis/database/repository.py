"""
数据访问层 (Repository)

提供持仓、交易、快照等数据的CRUD操作。

Example:
    >>> positions = PositionRepository.get_all_positions()
    >>> txn_id = PositionRepository.add_transaction(transaction)
    >>> PositionRepository.record_snapshot(snapshot)
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Tuple, Any
import logging

from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker, Session

from projects.portfolio_analysis.database.models import (
    Position, Transaction, PortfolioSnapshot, PositionHistory,
    FundInfo, FundNetValue, SIPPlan, SIPTransaction,
    AssetType, TradeType, get_engine
)
from core.storage.relational.connection import DatabaseManager

logger = logging.getLogger(__name__)


class PositionRepository:
    """持仓数据访问类

    提供持仓相关的数据库操作方法。
    使用DatabaseManager进行原始SQL操作，同时支持SQLAlchemy ORM。
    """

    DB_NAME = "interface"

    @classmethod
    def get_session(cls) -> Session:
        """获取SQLAlchemy会话"""
        engine = get_engine()
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()

    # ========== Position Methods ==========

    @classmethod
    def get_all_positions(cls) -> List[Position]:
        """获取所有当前持仓

        Returns:
            当前持仓列表
        """
        session = cls.get_session()
        try:
            positions = session.query(Position).filter(Position.volume > 0).all()
            return positions
        finally:
            session.close()

    @classmethod
    def get_position_by_code(cls, code: str) -> Optional[Position]:
        """根据股票代码获取持仓

        Args:
            code: 股票代码

        Returns:
            持仓对象，不存在返回None
        """
        session = cls.get_session()
        try:
            return session.query(Position).filter(Position.code == code).first()
        finally:
            session.close()

    @classmethod
    def save_position(cls, position: Position) -> int:
        """保存或更新持仓

        Args:
            position: 持仓对象

        Returns:
            持仓ID
        """
        session = cls.get_session()
        try:
            session.merge(position)
            session.commit()
            return position.id
        except Exception as e:
            session.rollback()
            logger.error(f"保存持仓失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def delete_position(cls, code: str) -> bool:
        """删除持仓

        Args:
            code: 股票代码

        Returns:
            是否成功删除
        """
        session = cls.get_session()
        try:
            result = session.query(Position).filter(Position.code == code).delete()
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            logger.error(f"删除持仓失败: {e}")
            return False
        finally:
            session.close()

    @classmethod
    def update_position_from_transaction(cls, txn: Transaction) -> Position:
        """根据交易更新持仓

        Args:
            txn: 交易记录

        Returns:
            更新后的持仓对象
        """
        session = cls.get_session()
        try:
            position = session.query(Position).filter(Position.code == txn.code).first()

            if txn.trade_type == TradeType.BUY:
                if position is None:
                    # 新建持仓
                    position = Position(
                        code=txn.code,
                        name=txn.name,
                        asset_type=txn.asset_type,
                        volume=txn.volume,
                        cost_price=txn.price,
                        entry_date=txn.trade_date
                    )
                    session.add(position)
                else:
                    # 更新持仓成本
                    old_cost = float(position.cost_price) * float(position.volume)
                    new_cost = float(txn.price) * float(txn.volume) + float(txn.fee or 0)
                    total_volume = float(position.volume) + float(txn.volume)

                    position.volume = total_volume
                    position.cost_price = Decimal(str((old_cost + new_cost) / total_volume))
                    position.name = txn.name  # 更新名称
            else:  # sell
                if position is not None:
                    if float(position.volume) <= float(txn.volume):
                        # 清仓
                        session.delete(position)
                        position = None
                    else:
                        # 减仓（成本价不变）
                        position.volume = float(position.volume) - float(txn.volume)

            session.commit()
            return position
        except Exception as e:
            session.rollback()
            logger.error(f"更新持仓失败: {e}")
            raise
        finally:
            session.close()

    # ========== Transaction Methods ==========

    @classmethod
    def add_transaction(cls, txn: Transaction) -> int:
        """添加交易记录

        Args:
            txn: 交易对象

        Returns:
            交易ID
        """
        session = cls.get_session()
        try:
            session.add(txn)
            session.commit()

            # 同时更新持仓
            cls.update_position_from_transaction(txn)

            return txn.id
        except Exception as e:
            session.rollback()
            logger.error(f"添加交易失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_transactions(
        cls,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        code: Optional[str] = None,
        trade_type: Optional[str] = None
    ) -> List[Transaction]:
        """查询交易记录

        Args:
            start_date: 开始日期
            end_date: 结束日期
            code: 股票代码
            trade_type: 交易类型 (buy/sell)

        Returns:
            交易记录列表
        """
        session = cls.get_session()
        try:
            query = session.query(Transaction)

            if start_date:
                query = query.filter(Transaction.trade_date >= start_date)
            if end_date:
                query = query.filter(Transaction.trade_date <= end_date)
            if code:
                query = query.filter(Transaction.code == code)
            if trade_type:
                query = query.filter(Transaction.trade_type == trade_type)

            return query.order_by(Transaction.trade_date.desc()).all()
        finally:
            session.close()

    @classmethod
    def get_transaction_by_id(cls, txn_id: int) -> Optional[Transaction]:
        """根据ID获取交易记录

        Args:
            txn_id: 交易ID

        Returns:
            交易对象
        """
        session = cls.get_session()
        try:
            return session.query(Transaction).filter(Transaction.id == txn_id).first()
        finally:
            session.close()

    @classmethod
    def delete_transaction(cls, txn_id: int) -> bool:
        """删除交易记录（注意：不会回滚持仓变化）

        Args:
            txn_id: 交易ID

        Returns:
            是否成功删除
        """
        session = cls.get_session()
        try:
            result = session.query(Transaction).filter(Transaction.id == txn_id).delete()
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            logger.error(f"删除交易失败: {e}")
            return False
        finally:
            session.close()

    # ========== PortfolioSnapshot Methods ==========

    @classmethod
    def record_snapshot(cls, snapshot: PortfolioSnapshot) -> int:
        """记录每日净值快照

        Args:
            snapshot: 快照对象

        Returns:
            快照ID
        """
        session = cls.get_session()
        try:
            # 检查是否已存在该日期的记录
            existing = session.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.date == snapshot.date
            ).first()

            if existing:
                # 更新现有记录
                existing.total_asset = snapshot.total_asset
                existing.cash = snapshot.cash
                existing.market_value = snapshot.market_value
                existing.net_value = snapshot.net_value
                existing.daily_return = snapshot.daily_return
                existing.cumulative_return = snapshot.cumulative_return
                existing.benchmark_return = snapshot.benchmark_return
                existing.notes = snapshot.notes
                session.merge(existing)
                snapshot_id = existing.id
            else:
                session.add(snapshot)
                session.flush()
                snapshot_id = snapshot.id

            session.commit()
            return snapshot_id
        except Exception as e:
            session.rollback()
            logger.error(f"记录快照失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_snapshots(
        cls,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[PortfolioSnapshot]:
        """获取净值快照列表

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            快照列表
        """
        session = cls.get_session()
        try:
            query = session.query(PortfolioSnapshot)

            if start_date:
                query = query.filter(PortfolioSnapshot.date >= start_date)
            if end_date:
                query = query.filter(PortfolioSnapshot.date <= end_date)

            return query.order_by(PortfolioSnapshot.date.asc()).all()
        finally:
            session.close()

    @classmethod
    def get_latest_snapshot(cls) -> Optional[PortfolioSnapshot]:
        """获取最新快照

        Returns:
            最新的快照对象
        """
        session = cls.get_session()
        try:
            return session.query(PortfolioSnapshot).order_by(
                PortfolioSnapshot.date.desc()
            ).first()
        finally:
            session.close()

    @classmethod
    def get_snapshot_by_date(cls, target_date: date) -> Optional[PortfolioSnapshot]:
        """获取指定日期的快照

        Args:
            target_date: 目标日期

        Returns:
            快照对象
        """
        session = cls.get_session()
        try:
            return session.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.date == target_date
            ).first()
        finally:
            session.close()

    # ========== PositionHistory Methods ==========

    @classmethod
    def record_position_history(cls, history: PositionHistory) -> int:
        """记录历史持仓

        Args:
            history: 历史持仓对象

        Returns:
            记录ID
        """
        session = cls.get_session()
        try:
            session.merge(history)
            session.commit()
            return history.id
        except Exception as e:
            session.rollback()
            logger.error(f"记录历史持仓失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_position_history(
        cls,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        code: Optional[str] = None
    ) -> List[PositionHistory]:
        """获取历史持仓记录

        Args:
            start_date: 开始日期
            end_date: 结束日期
            code: 股票代码

        Returns:
            历史持仓列表
        """
        session = cls.get_session()
        try:
            query = session.query(PositionHistory)

            if start_date:
                query = query.filter(PositionHistory.date >= start_date)
            if end_date:
                query = query.filter(PositionHistory.date <= end_date)
            if code:
                query = query.filter(PositionHistory.code == code)

            return query.order_by(PositionHistory.date.desc()).all()
        finally:
            session.close()

    @classmethod
    def get_position_history_by_date(cls, target_date: date) -> List[PositionHistory]:
        """获取指定日期的所有持仓记录

        Args:
            target_date: 目标日期

        Returns:
            持仓列表
        """
        session = cls.get_session()
        try:
            return session.query(PositionHistory).filter(
                PositionHistory.date == target_date
            ).all()
        finally:
            session.close()

    # ========== Aggregated Queries ==========

    @classmethod
    def get_total_position_value(cls) -> float:
        """获取当前总持仓市值（需要外部传入价格）

        Returns:
            基于成本价的总持仓价值
        """
        session = cls.get_session()
        try:
            result = session.query(
                func.sum(Position.volume * Position.cost_price)
            ).filter(Position.volume > 0).scalar()

            return float(result) if result else 0.0
        finally:
            session.close()

    @classmethod
    def get_position_count(cls) -> int:
        """获取持仓数量

        Returns:
            当前持仓股票数量
        """
        session = cls.get_session()
        try:
            return session.query(Position).filter(Position.volume > 0).count()
        finally:
            session.close()

    @classmethod
    def get_sector_distribution(cls) -> Dict[str, float]:
        """获取行业分布

        Returns:
            行业->持仓金额的字典（基于成本价）
        """
        session = cls.get_session()
        try:
            results = session.query(
                Position.sector,
                func.sum(Position.volume * Position.cost_price).label('amount')
            ).filter(Position.volume > 0).group_by(Position.sector).all()

            return {r.sector or '未知': float(r.amount) for r in results}
        finally:
            session.close()

    # ========== Raw SQL Methods (for complex queries) ==========

    @classmethod
    def execute_raw(cls, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行原始SQL查询

        Args:
            sql: SQL语句
            params: 参数

        Returns:
            查询结果列表
        """
        return DatabaseManager.fetchall(cls.DB_NAME, sql, params)

    @classmethod
    def init_tables(cls):
        """初始化所有表"""
        from projects.portfolio_analysis.database.models import init_database
        init_database()


class FundRepository:
    """基金数据访问类"""

    @classmethod
    def get_session(cls) -> Session:
        """获取SQLAlchemy会话"""
        engine = get_engine()
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()

    @classmethod
    def save_fund_info(cls, fund: FundInfo) -> int:
        """保存基金信息"""
        session = cls.get_session()
        try:
            session.merge(fund)
            session.commit()
            return fund.id
        except Exception as e:
            session.rollback()
            logger.error(f"保存基金信息失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_fund_info(cls, code: str) -> Optional[FundInfo]:
        """获取基金信息"""
        session = cls.get_session()
        try:
            return session.query(FundInfo).filter(FundInfo.code == code).first()
        finally:
            session.close()

    @classmethod
    def save_nav(cls, nav: FundNetValue) -> int:
        """保存基金净值"""
        session = cls.get_session()
        try:
            session.merge(nav)
            session.commit()
            return nav.id
        except Exception as e:
            session.rollback()
            logger.error(f"保存基金净值失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_nav(cls, code: str, date: datetime.date) -> Optional[FundNetValue]:
        """获取指定日期的基金净值"""
        session = cls.get_session()
        try:
            return session.query(FundNetValue).filter(
                FundNetValue.code == code,
                FundNetValue.date == date
            ).first()
        finally:
            session.close()


class SIPRepository:
    """定投计划数据访问类"""

    @classmethod
    def get_session(cls) -> Session:
        """获取SQLAlchemy会话"""
        engine = get_engine()
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()

    @classmethod
    def create_plan(cls, plan: SIPPlan) -> int:
        """创建定投计划"""
        session = cls.get_session()
        try:
            session.add(plan)
            session.commit()
            return plan.id
        except Exception as e:
            session.rollback()
            logger.error(f"创建定投计划失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_active_plans(cls) -> List[SIPPlan]:
        """获取所有活动的定投计划"""
        session = cls.get_session()
        try:
            return session.query(SIPPlan).filter(SIPPlan.is_active == True).all()
        finally:
            session.close()

    @classmethod
    def add_transaction(cls, txn: SIPTransaction) -> int:
        """添加定投记录"""
        session = cls.get_session()
        try:
            session.add(txn)

            # 更新计划累计数据
            plan = session.query(SIPPlan).filter(SIPPlan.id == txn.plan_id).first()
            if plan:
                plan.total_invested = float(plan.total_invested or 0) + float(txn.amount)
                plan.total_shares = float(plan.total_shares or 0) + float(txn.shares)

            session.commit()
            return txn.id
        except Exception as e:
            session.rollback()
            logger.error(f"添加定投记录失败: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_plan_transactions(cls, plan_id: int) -> List[SIPTransaction]:
        """获取定投计划的所有交易记录"""
        session = cls.get_session()
        try:
            return session.query(SIPTransaction).filter(
                SIPTransaction.plan_id == plan_id
            ).order_by(SIPTransaction.execute_date.desc()).all()
        finally:
            session.close()


if __name__ == "__main__":
    # 测试Repository
    logging.basicConfig(level=logging.INFO)

    try:
        # 初始化表
        PositionRepository.init_tables()

        # 测试添加持仓
        pos = Position(
            code="000001.SZ",
            name="平安银行",
            volume=1000,
            cost_price=Decimal("10.50"),
            sector="银行"
        )
        pos_id = PositionRepository.save_position(pos)
        print(f"✅ 保存持仓成功，ID: {pos_id}")

        # 测试查询
        positions = PositionRepository.get_all_positions()
        print(f"✅ 查询到 {len(positions)} 条持仓")

        # 测试交易
        txn = Transaction(
            trade_date=date(2024, 1, 15),
            code="000001.SZ",
            name="平安银行",
            trade_type=TradeType.BUY,
            volume=500,
            price=Decimal("10.60"),
            amount=Decimal("5300.00"),
            fee=Decimal("5.00")
        )
        txn_id = PositionRepository.add_transaction(txn)
        print(f"✅ 添加交易成功，ID: {txn_id}")

        # 检查持仓是否更新
        updated_pos = PositionRepository.get_position_by_code("000001.SZ")
        if updated_pos:
            print(f"✅ 持仓已更新: volume={updated_pos.volume}, cost={updated_pos.cost_price}")

        # 清理测试数据
        PositionRepository.delete_position("000001.SZ")
        print("✅ 测试数据已清理")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
