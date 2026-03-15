"""
SQLAlchemy 数据模型

定义持仓分析系统所需的数据表结构：
- Position: 当前持仓表
- Transaction: 交易记录表
- PortfolioSnapshot: 每日净值快照
- PositionHistory: 历史持仓记录

Example:
    >>> from projects.portfolio_analysis.database.models import Position
    >>> position = Position(code="000001.SZ", name="平安银行", volume=1000, cost_price=10.5)
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, Enum, Text, Boolean,
    ForeignKey, UniqueConstraint, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class AssetType(PyEnum):
    """资产类型枚举"""
    STOCK = "stock"
    FUND_ETF = "etf"
    FUND_LOF = "lof"
    FUND_OE = "fund_oe"
    BOND = "bond"
    CASH = "cash"


class TradeType(PyEnum):
    """交易类型枚举"""
    BUY = "buy"
    SELL = "sell"


class SIPCycle(PyEnum):
    """定投周期枚举"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class Position(Base):
    """当前持仓表

    记录当前持有的资产信息，包括股票和基金。

    Attributes:
        id: 主键ID
        code: 资产代码
        name: 资产名称
        asset_type: 资产类型
        volume: 持股数量/份额
        cost_price: 加权成本价
        current_price: 当前价格
        market_value: 市值
        sector: 所属行业
        fund_type: 基金类型
        entry_date: 首次买入日期
        updated_at: 更新时间
    """

    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True, comment='资产代码')
    name = Column(String(50), comment='资产名称')
    asset_type = Column(Enum(AssetType), default=AssetType.STOCK, comment='资产类型')

    # 通用持仓字段
    volume = Column(Numeric(12, 4), default=0, comment='持仓数量/份额')
    cost_price = Column(Numeric(12, 4), comment='加权成本价')
    current_price = Column(Numeric(12, 4), comment='当前价格/净值')
    market_value = Column(Numeric(15, 2), comment='市值')

    # 股票特有字段
    sector = Column(String(50), comment='所属行业')

    # 基金特有字段
    fund_type = Column(String(20), comment='基金类型：股票型、债券型、混合型等')
    fund_company = Column(String(50), comment='基金公司')
    nav = Column(Numeric(10, 4), comment='最新净值')

    entry_date = Column(Date, comment='首次买入日期')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now,
                       comment='更新时间')

    __table_args__ = (
        UniqueConstraint('code', name='uk_code'),
        {'comment': '当前持仓表', 'mysql_engine': 'InnoDB'}
    )

    def __repr__(self) -> str:
        return f"Position(code='{self.code}', name='{self.name}', volume={self.volume})"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'asset_type': self.asset_type.value if self.asset_type else 'stock',
            'volume': float(self.volume) if self.volume else 0.0,
            'cost_price': float(self.cost_price) if self.cost_price else 0.0,
            'current_price': float(self.current_price) if self.current_price else 0.0,
            'market_value': float(self.market_value) if self.market_value else 0.0,
            'sector': self.sector,
            'fund_type': self.fund_type,
            'fund_company': self.fund_company,
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def calculate_pnl(self, current_price: float = None) -> dict:
        """计算盈亏

        Args:
            current_price: 当前价格，如果不提供则使用 self.current_price

        Returns:
            包含盈亏信息的字典
        """
        price = current_price if current_price is not None else float(self.current_price or 0)

        if not self.volume or self.cost_price is None or price <= 0:
            return {
                'pnl': 0.0,
                'pnl_pct': 0.0,
                'cost': 0.0,
                'market_value': 0.0,
            }

        vol = float(self.volume)
        cost_price = float(self.cost_price)

        cost = cost_price * vol
        market_value = price * vol
        pnl = market_value - cost
        pnl_pct = (price / cost_price - 1) if cost_price > 0 else 0

        return {
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'cost': cost,
            'market_value': market_value,
        }


class Transaction(Base):
    """交易记录表

    记录每笔买入/卖出交易详情。

    Attributes:
        id: 主键ID
        trade_date: 交易日期
        code: 资产代码
        name: 资产名称
        asset_type: 资产类型
        trade_type: 交易类型（buy/sell）
        volume: 交易数量/份额
        price: 成交价格
        amount: 成交金额
        fee: 手续费
        strategy: 策略名称（用于回测追踪）
        created_at: 记录创建时间
    """

    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True, comment='交易日期')
    code = Column(String(20), nullable=False, comment='资产代码')
    name = Column(String(50), comment='资产名称')
    asset_type = Column(Enum(AssetType), default=AssetType.STOCK, comment='资产类型')
    trade_type = Column(Enum(TradeType), nullable=False, comment='交易类型')
    volume = Column(Numeric(12, 4), nullable=False, comment='交易数量/份额')
    price = Column(Numeric(12, 4), nullable=False, comment='成交价格')
    amount = Column(Numeric(15, 2), comment='成交金额')

    # 费用明细
    commission = Column(Numeric(10, 2), default=0, comment='佣金')
    stamp_tax = Column(Numeric(10, 2), default=0, comment='印花税')
    transfer_fee = Column(Numeric(10, 2), default=0, comment='过户费')
    other_fee = Column(Numeric(10, 2), default=0, comment='其他费用')
    fee = Column(Numeric(10, 2), default=0, comment='总手续费')

    strategy = Column(String(50), comment='策略名称')
    notes = Column(Text, comment='备注')
    created_at = Column(DateTime, default=datetime.now, comment='记录创建时间')

    __table_args__ = (
        Index('idx_code_date', 'code', 'trade_date'),
        {'comment': '交易记录表', 'mysql_engine': 'InnoDB'}
    )

    def __repr__(self) -> str:
        return (f"Transaction(code='{self.code}', type='{self.trade_type}', "
                f"volume={self.volume}, price={self.price})")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'code': self.code,
            'name': self.name,
            'asset_type': self.asset_type.value if self.asset_type else 'stock',
            'trade_type': self.trade_type.value if self.trade_type else None,
            'volume': float(self.volume) if self.volume else 0.0,
            'price': float(self.price) if self.price else 0.0,
            'amount': float(self.amount) if self.amount else 0.0,
            'fee': float(self.fee) if self.fee else 0.0,
            'commission': float(self.commission) if self.commission else 0.0,
            'stamp_tax': float(self.stamp_tax) if self.stamp_tax else 0.0,
            'transfer_fee': float(self.transfer_fee) if self.transfer_fee else 0.0,
            'strategy': self.strategy,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def net_amount(self) -> float:
        """计算净成交金额"""
        amt = float(self.amount) if self.amount else 0.0
        fee = float(self.fee) if self.fee else 0.0

        if self.trade_type == TradeType.BUY:
            return -(amt + fee)
        else:
            return amt - fee


class PortfolioSnapshot(Base):
    """每日净值快照

    每日收盘后记录账户总资产、净值、收益率等信息。

    Attributes:
        id: 主键ID
        date: 日期
        total_asset: 总资产
        cash: 现金余额
        market_value: 股票市值
        net_value: 单位净值
        daily_return: 日收益率
        cumulative_return: 累计收益率
        benchmark_return: 基准日收益率
        notes: 备注
    """

    __tablename__ = 'portfolio_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True, comment='日期')
    total_asset = Column(Numeric(15, 2), comment='总资产')
    cash = Column(Numeric(15, 2), comment='现金余额')
    market_value = Column(Numeric(15, 2), comment='股票市值')
    net_value = Column(Numeric(12, 6), comment='单位净值')
    daily_return = Column(Numeric(10, 6), comment='日收益率')
    cumulative_return = Column(Numeric(10, 6), comment='累计收益率')
    benchmark_return = Column(Numeric(10, 6), comment='基准日收益率')
    notes = Column(Text, comment='备注')

    __table_args__ = (
        {'comment': '每日净值快照', 'mysql_engine': 'InnoDB'}
    )

    def __repr__(self) -> str:
        return (f"PortfolioSnapshot(date='{self.date}', "
                f"total={self.total_asset}, nav={self.net_value})")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'total_asset': float(self.total_asset) if self.total_asset else 0.0,
            'cash': float(self.cash) if self.cash else 0.0,
            'market_value': float(self.market_value) if self.market_value else 0.0,
            'net_value': float(self.net_value) if self.net_value else 1.0,
            'daily_return': float(self.daily_return) if self.daily_return else 0.0,
            'cumulative_return': float(self.cumulative_return) if self.cumulative_return else 0.0,
            'benchmark_return': float(self.benchmark_return) if self.benchmark_return else None,
            'notes': self.notes,
        }

    def get_position_ratio(self) -> float:
        """获取仓位比例"""
        if not self.total_asset or self.total_asset == 0:
            return 0.0
        mv = self.market_value or 0
        return float(mv) / float(self.total_asset)


class PositionHistory(Base):
    """历史持仓记录

    每日收盘后记录持仓详情，用于分析持仓变化。

    Attributes:
        id: 主键ID
        date: 日期
        code: 股票代码
        name: 股票名称
        volume: 持股数量
        cost_price: 成本价
        close_price: 当日收盘价
        market_value: 市值
        pnl: 累计盈亏
        pnl_pct: 盈亏比例
        weight: 权重
    """

    __tablename__ = 'position_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True, comment='日期')
    code = Column(String(20), nullable=False, comment='股票代码')
    name = Column(String(50), comment='股票名称')
    volume = Column(Integer, comment='持股数量')
    cost_price = Column(Numeric(12, 4), comment='成本价')
    close_price = Column(Numeric(12, 4), comment='当日收盘价')
    market_value = Column(Numeric(15, 2), comment='市值')
    pnl = Column(Numeric(15, 2), comment='累计盈亏')
    pnl_pct = Column(Numeric(10, 6), comment='盈亏比例')
    weight = Column(Numeric(8, 6), comment='权重')

    __table_args__ = (
        UniqueConstraint('date', 'code', name='uk_date_code'),
        Index('idx_date', 'date'),
        {'comment': '历史持仓记录', 'mysql_engine': 'InnoDB'}
    )

    def __repr__(self) -> str:
        return f"PositionHistory(date='{self.date}', code='{self.code}', volume={self.volume})"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'code': self.code,
            'name': self.name,
            'volume': self.volume,
            'cost_price': float(self.cost_price) if self.cost_price else 0.0,
            'close_price': float(self.close_price) if self.close_price else 0.0,
            'market_value': float(self.market_value) if self.market_value else 0.0,
            'pnl': float(self.pnl) if self.pnl else 0.0,
            'pnl_pct': float(self.pnl_pct) if self.pnl_pct else 0.0,
            'weight': float(self.weight) if self.weight else 0.0,
        }


class FundInfo(Base):
    """基金基本信息表"""

    __tablename__ = 'fund_info'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, comment='基金代码')
    name = Column(String(100), comment='基金名称')
    fund_type = Column(String(20), comment='基金类型：股票型/债券型/混合型/指数型')
    company = Column(String(50), comment='基金公司')
    setup_date = Column(Date, comment='成立日期')

    # 费率信息
    management_fee = Column(Numeric(6, 4), comment='管理费率')
    custodian_fee = Column(Numeric(6, 4), comment='托管费率')
    purchase_fee = Column(Numeric(6, 4), comment='申购费率')
    redemption_fee = Column(Numeric(6, 4), comment='赎回费率')

    # 赎回费率结构（JSON格式存储）
    redemption_fee_structure = Column(Text, comment='赎回费率结构JSON')

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    __table_args__ = (
        {'comment': '基金基本信息表', 'mysql_engine': 'InnoDB'}
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'fund_type': self.fund_type,
            'company': self.company,
            'setup_date': self.setup_date.isoformat() if self.setup_date else None,
            'management_fee': float(self.management_fee) if self.management_fee else 0,
            'custodian_fee': float(self.custodian_fee) if self.custodian_fee else 0,
            'purchase_fee': float(self.purchase_fee) if self.purchase_fee else 0,
            'redemption_fee': float(self.redemption_fee) if self.redemption_fee else 0,
        }


class FundNetValue(Base):
    """基金净值表（场外基金每日只有一个净值）"""

    __tablename__ = 'fund_net_values'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True, comment='基金代码')
    name = Column(String(50), comment='基金名称')
    date = Column(Date, nullable=False, comment='净值日期')

    nav = Column(Numeric(10, 4), comment='单位净值')
    accumulated_nav = Column(Numeric(10, 4), comment='累计净值')
    daily_return = Column(Numeric(8, 4), comment='日涨跌幅')

    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    __table_args__ = (
        UniqueConstraint('code', 'date', name='uk_fund_date'),
        {'comment': '基金净值表', 'mysql_engine': 'InnoDB'}
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'code': self.code,
            'date': self.date.isoformat() if self.date else None,
            'nav': float(self.nav) if self.nav else 0,
            'accumulated_nav': float(self.accumulated_nav) if self.accumulated_nav else 0,
            'daily_return': float(self.daily_return) if self.daily_return else 0,
        }


class SIPPlan(Base):
    """定投计划表"""

    __tablename__ = 'sip_plans'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, comment='基金代码')
    name = Column(String(50), comment='基金名称')
    asset_type = Column(Enum(AssetType), default=AssetType.FUND_OE, comment='资产类型')

    # 定投设置
    cycle = Column(Enum(SIPCycle), nullable=False, comment='定投周期')
    cycle_day = Column(Integer, comment='定投日（周几/每月几号）')
    fixed_amount = Column(Numeric(12, 2), comment='每期金额')

    # 时间范围
    start_date = Column(Date, comment='开始日期')
    end_date = Column(Date, nullable=True, comment='结束日期（可选）')
    is_active = Column(Boolean, default=True, comment='是否进行中')

    # 统计
    total_invested = Column(Numeric(15, 2), default=0, comment='累计投入')
    total_shares = Column(Numeric(12, 4), default=0, comment='累计份额')

    notes = Column(Text, comment='备注')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关系
    transactions = relationship("SIPTransaction", back_populates="plan",
                               order_by="SIPTransaction.execute_date", cascade="all, delete-orphan")

    __table_args__ = (
        {'comment': '定投计划表', 'mysql_engine': 'InnoDB'}
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'cycle': self.cycle.value if self.cycle else None,
            'cycle_day': self.cycle_day,
            'fixed_amount': float(self.fixed_amount) if self.fixed_amount else 0,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active,
            'total_invested': float(self.total_invested) if self.total_invested else 0,
            'total_shares': float(self.total_shares) if self.total_shares else 0,
        }


class SIPTransaction(Base):
    """定投执行记录"""

    __tablename__ = 'sip_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey('sip_plans.id'), nullable=False, comment='计划ID')

    # 执行信息
    execute_date = Column(Date, nullable=False, comment='执行日期')
    nav = Column(Numeric(10, 4), comment='当日净值')
    shares = Column(Numeric(12, 4), comment='获得份额')
    amount = Column(Numeric(12, 2), comment='投入金额')
    fee = Column(Numeric(10, 2), default=0, comment='申购费')

    # 状态
    is_auto = Column(Boolean, default=True, comment='是否自动执行')
    status = Column(String(20), default='success', comment='执行状态')

    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    # 关系
    plan = relationship("SIPPlan", back_populates="transactions")

    __table_args__ = (
        Index('idx_plan_date', 'plan_id', 'execute_date'),
        {'comment': '定投执行记录表', 'mysql_engine': 'InnoDB'}
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'execute_date': self.execute_date.isoformat() if self.execute_date else None,
            'nav': float(self.nav) if self.nav else 0,
            'shares': float(self.shares) if self.shares else 0,
            'amount': float(self.amount) if self.amount else 0,
            'fee': float(self.fee) if self.fee else 0,
        }


# 数据库连接相关函数
def get_engine(db_url: Optional[str] = None):
    """获取SQLAlchemy引擎

    Args:
        db_url: 数据库连接URL，如果不提供则从环境变量构建

    Returns:
        SQLAlchemy引擎实例
    """
    if db_url is None:
        import os
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '3306')
        user = os.getenv('DB_USER', 'root')
        password = os.getenv('DB_PASSWORD', '')
        database = os.getenv('DB_NAME_INTERFACE', 'interface')

        db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

    return create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)


def init_database(engine=None):
    """初始化数据库，创建所有表

    Args:
        engine: SQLAlchemy引擎，如果不提供则自动创建
    """
    if engine is None:
        engine = get_engine()

    Base.metadata.create_all(engine)
    print("✅ 数据库表已创建")


def drop_all_tables(engine=None):
    """删除所有表（危险操作！）

    Args:
        engine: SQLAlchemy引擎，如果不提供则自动创建
    """
    if engine is None:
        engine = get_engine()

    Base.metadata.drop_all(engine)
    print("✅ 数据库表已删除")


def get_session(engine=None):
    """获取数据库会话

    Args:
        engine: SQLAlchemy引擎

    Returns:
        Session类
    """
    if engine is None:
        engine = get_engine()

    Session = sessionmaker(bind=engine)
    return Session


if __name__ == "__main__":
    # 测试模型定义
    print("测试模型定义...")

    # 创建Position实例
    pos = Position(
        code="000001.SZ",
        name="平安银行",
        volume=Decimal("1000"),
        cost_price=Decimal("10.50"),
        sector="银行",
        entry_date=date(2024, 1, 1)
    )
    print(f"Position: {pos}")
    print(f"Position dict: {pos.to_dict()}")
    print(f"Position PnL @ 11.0: {pos.calculate_pnl(11.0)}")

    # 创建Transaction实例
    txn = Transaction(
        trade_date=date(2024, 1, 15),
        code="000001.SZ",
        name="平安银行",
        trade_type=TradeType.BUY,
        volume=Decimal("1000"),
        price=Decimal("10.50"),
        amount=Decimal("10500.00"),
        fee=Decimal("5.00"),
        strategy="测试策略"
    )
    print(f"Transaction: {txn}")
    print(f"Transaction net_amount: {txn.net_amount}")

    # 创建PortfolioSnapshot实例
    snapshot = PortfolioSnapshot(
        date=date(2024, 1, 15),
        total_asset=Decimal("200000.00"),
        cash=Decimal("50000.00"),
        market_value=Decimal("150000.00"),
        net_value=Decimal("1.0000"),
        daily_return=Decimal("0.0010"),
        cumulative_return=Decimal("0.0010"),
    )
    print(f"PortfolioSnapshot: {snapshot}")
    print(f"Position ratio: {snapshot.get_position_ratio():.2%}")

    # 创建FundInfo实例
    fund = FundInfo(
        code="110022",
        name="易方达消费行业",
        fund_type="股票型",
        company="易方达基金",
        purchase_fee=Decimal("0.0015"),
        redemption_fee=Decimal("0.0050"),
    )
    print(f"FundInfo: {fund}")
    print(f"FundInfo dict: {fund.to_dict()}")

    # 创建SIPPlan实例
    sip = SIPPlan(
        code="110022",
        name="易方达消费行业",
        cycle=SIPCycle.MONTHLY,
        cycle_day=1,
        fixed_amount=Decimal("1000.00"),
        start_date=date(2024, 1, 1),
    )
    print(f"SIPPlan: {sip}")
    print(f"SIPPlan dict: {sip.to_dict()}")

    # 测试数据库初始化
    try:
        init_database()
    except Exception as e:
        print(f"数据库初始化失败（可能是环境未配置）: {e}")
