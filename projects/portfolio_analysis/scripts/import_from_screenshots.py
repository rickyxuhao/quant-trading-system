#!/usr/bin/env python3
"""
从截图识别的持仓数据导入数据库
"""

import sys
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from projects.portfolio_analysis.database.models import Position, AssetType, SIPPlan, FundInfo, SIPCycle
from projects.portfolio_analysis.database.repository import PositionRepository, SIPRepository, FundRepository


def import_stock_positions():
    """导入股票/ETF持仓"""
    print("=" * 60)
    print("导入股票/ETF持仓")
    print("=" * 60)

    # 从截图识别的股票持仓数据
    stocks = [
        # (代码, 名称, 数量, 成本价, 当前价, 市值, 类型)
        ("000708.SZ", "中信特钢", 600, 17.418, 17.690, 10614.00, AssetType.STOCK),
        ("002195.SZ", "岩山科技", 1400, 10.364, 10.340, 14476.00, AssetType.STOCK),
        ("002364.SZ", "中恒电气", 400, 38.154, 34.600, 13840.00, AssetType.STOCK),
        ("159870.SZ", "化工ETF嘉实", 5700, 1.046, 1.267, 7221.90, AssetType.FUND_ETF),
        ("159353.SZ", "A500ETF嘉实", 14200, 1.297, 1.250, 17750.00, AssetType.FUND_ETF),
        ("512890.SH", "红利低波ETF", 36400, 1.063, 1.123, 40877.20, AssetType.FUND_ETF),
        ("159741.SZ", "恒生科技ETF嘉实", 14000, 0.773, 0.637, 8918.00, AssetType.FUND_ETF),
        ("159880.SZ", "有色ETF银华", 10000, 1.133, 1.140, 11400.00, AssetType.FUND_ETF),
        ("300750.SZ", "宁德时代", 100, 394.231, 393.690, 39369.00, AssetType.STOCK),
        ("300970.SZ", "华绿生物", 300, 25.577, 26.250, 7875.00, AssetType.STOCK),
        ("513520.SH", "日经ETF", 21700, 1.917, 1.943, 42163.10, AssetType.FUND_ETF),
        ("588000.SH", "科创50ETF", 3500, 1.576, 1.461, 5113.50, AssetType.FUND_ETF),
    ]

    imported = 0

    for code, name, volume, cost_price, current_price, market_value, asset_type in stocks:
        position = Position(
            code=code,
            name=name,
            asset_type=asset_type,
            volume=Decimal(str(volume)),
            cost_price=Decimal(str(cost_price)),
            current_price=Decimal(str(current_price)),
            market_value=Decimal(str(market_value)),
            entry_date=date(2025, 1, 1),  # 假设入场日期
        )

        try:
            PositionRepository.save_position(position)
            print(f"✅ {code} {name}: {volume}股 @ {cost_price}")
            imported += 1
        except Exception as e:
            if "Duplicate" in str(e):
                print(f"🔄 {code} {name}: 已存在，跳过")
                imported += 1
            else:
                print(f"❌ {code} {name}: {e}")

    print(f"\n股票/ETF导入完成: {imported}/{len(stocks)} 只")
    return imported


def import_fund_positions():
    """导入场外基金持仓"""
    print("\n" + "=" * 60)
    print("导入场外基金持仓")
    print("=" * 60)

    # 从截图识别的基金数据
    funds = [
        # (代码, 名称, 份额/金额, 成本净值, 当前净值, 市值, 定投状态)
        ("001122", "鹏华弘利灵活配置混合A", Decimal("30348.41"), None, None, Decimal("30348.41"), False),
        ("008764", "天弘越南市场股票(QDII)C", Decimal("27724.03"), None, None, Decimal("27724.03"), True),
        ("016665", "天弘全球高端制造混合(QDII)C", Decimal("48540.32"), None, None, Decimal("48540.32"), True),
        ("013345", "嘉实中证稀有金属主题ETF联接A", Decimal("26088.91"), None, None, Decimal("26088.91"), False),
        ("013172", "华夏恒生科技ETF联接(QDII)A", Decimal("8879.63"), None, None, Decimal("8879.63"), False),
        ("019918", "招商中证2000指数增强A", Decimal("20860.93"), None, None, Decimal("20860.93"), False),
        ("000961", "天弘沪深300ETF联接C", Decimal("2579.35"), None, None, Decimal("2579.35"), False),
        ("017855", "汇添富中证1000指数增强A", Decimal("10192.82"), None, None, Decimal("10192.82"), False),
        ("021855", "汇添富中证A500指数增强A", Decimal("10083.11"), None, None, Decimal("10083.11"), False),
    ]

    imported = 0

    for code, name, shares, cost_nav, nav, market_value, is_sip in funds:
        position = Position(
            code=code,
            name=name,
            asset_type=AssetType.FUND_OE,
            volume=shares,  # 对于场外基金，volume存储的是份额
            cost_price=cost_nav,
            current_price=nav,
            market_value=market_value,
            entry_date=date(2025, 1, 1),
        )

        try:
            PositionRepository.save_position(position)
            status = "定投中" if is_sip else ""
            print(f"✅ {code} {name}: ¥{market_value} {status}")
            imported += 1
        except Exception as e:
            if "Duplicate" in str(e):
                print(f"🔄 {code} {name}: 已存在，跳过")
                imported += 1
            else:
                print(f"❌ {code} {name}: {e}")

    print(f"\n基金导入完成: {imported}/{len(funds)} 只")
    return imported


def import_sip_plans():
    """导入定投计划"""
    print("\n" + "=" * 60)
    print("导入定投计划")
    print("=" * 60)

    # 从截图识别的定投数据
    sip_plans = [
        {
            "code": "016665",
            "name": "天弘全球高端制造混合(QDII)C",
            "asset_type": AssetType.FUND_OE,
            "cycle": "daily",  # 每日定投
            "cycle_day": None,
            "fixed_amount": Decimal("800.00"),
            "start_date": date(2025, 10, 1),  # 估算：146期前
            "is_active": True,
            "total_invested": Decimal("105400.00"),
            "total_shares": None,
            "notes": "每日定投800元，已投146期",
        },
        {
            "code": "008764",
            "name": "天弘越南市场股票(QDII)C",
            "asset_type": AssetType.FUND_OE,
            "cycle": "daily",  # 每日定投
            "cycle_day": None,
            "fixed_amount": Decimal("1000.00"),
            "start_date": date(2026, 2, 10),  # 估算：28期前
            "is_active": True,
            "total_invested": Decimal("28000.00"),
            "total_shares": None,
            "notes": "每日定投1000元，已投28期",
        },
    ]

    repo = SIPRepository()
    imported = 0

    for plan_data in sip_plans:
        plan = SIPPlan(
            code=plan_data["code"],
            name=plan_data["name"],
            asset_type=plan_data["asset_type"],
            cycle=SIPCycle.DAILY,
            cycle_day=plan_data["cycle_day"],
            fixed_amount=plan_data["fixed_amount"],
            start_date=plan_data["start_date"],
            is_active=plan_data["is_active"],
            total_invested=plan_data["total_invested"],
            total_shares=plan_data["total_shares"],
            notes=plan_data["notes"],
        )

        try:
            plan_id = repo.create_plan(plan)
            print(f"✅ {plan.code} {plan.name}:")
            print(f"   每期: ¥{plan.fixed_amount} | 累计投入: ¥{plan.total_invested} | 状态: {'进行中' if plan.is_active else '暂停'}")
            imported += 1
        except Exception as e:
            print(f"❌ {plan.code}: {e}")

    print(f"\n定投计划导入完成: {imported}/{len(sip_plans)} 个")
    return imported


def import_fund_info():
    """导入基金基本信息"""
    print("\n" + "=" * 60)
    print("导入基金基本信息")
    print("=" * 60)

    funds_info = [
        ("001122", "鹏华弘利灵活配置混合A", "混合型", "鹏华基金"),
        ("008764", "天弘越南市场股票(QDII)C", "QDII", "天弘基金"),
        ("016665", "天弘全球高端制造混合(QDII)C", "QDII", "天弘基金"),
        ("013345", "嘉实中证稀有金属主题ETF联接A", "指数型", "嘉实基金"),
        ("013172", "华夏恒生科技ETF联接(QDII)A", "QDII", "华夏基金"),
        ("019918", "招商中证2000指数增强A", "指数型", "招商基金"),
        ("000961", "天弘沪深300ETF联接C", "指数型", "天弘基金"),
        ("017855", "汇添富中证1000指数增强A", "指数型", "汇添富基金"),
        ("021855", "汇添富中证A500指数增强A", "指数型", "汇添富基金"),
    ]

    imported = 0

    for code, name, fund_type, company in funds_info:
        fund = FundInfo(
            code=code,
            name=name,
            fund_type=fund_type,
            company=company,
        )

        try:
            FundRepository.save_fund_info(fund)
            print(f"✅ {code} {name}")
            imported += 1
        except Exception as e:
            if "Duplicate" in str(e):
                print(f"🔄 {code}: 已存在")
                imported += 1
            else:
                print(f"❌ {code}: {e}")

    print(f"\n基金信息导入完成: {imported}/{len(funds_info)} 只")
    return imported


def calculate_portfolio_summary():
    """计算并显示组合汇总"""
    print("\n" + "=" * 60)
    print("持仓汇总")
    print("=" * 60)

    repo = PositionRepository()
    positions = repo.get_all_positions()

    total_market_value = 0
    stock_value = 0
    fund_value = 0
    etf_value = 0

    for pos in positions:
        value = float(pos.market_value) if pos.market_value else 0
        total_market_value += value

        if pos.asset_type == AssetType.STOCK:
            stock_value += value
        elif pos.asset_type == AssetType.FUND_OE:
            fund_value += value
        elif pos.asset_type == AssetType.FUND_ETF:
            etf_value += value

    print(f"\n总资产: ¥{total_market_value:,.2f}")
    print(f"  - 股票: ¥{stock_value:,.2f} ({stock_value/total_market_value*100:.1f}%)")
    print(f"  - ETF:  ¥{etf_value:,.2f} ({etf_value/total_market_value*100:.1f}%)")
    print(f"  - 基金: ¥{fund_value:,.2f} ({fund_value/total_market_value*100:.1f}%)")

    # 显示定投汇总
    sip_repo = SIPRepository()
    active_plans = sip_repo.get_active_plans()

    print(f"\n定投计划: {len(active_plans)} 个进行中")
    total_sip = sum(float(p.total_invested) for p in active_plans if p.total_invested)
    print(f"定投累计投入: ¥{total_sip:,.2f}")


def main():
    """主函数"""
    print("=" * 60)
    print("持仓数据导入 - 从截图识别")
    print("=" * 60)
    print(f"导入时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        # 1. 导入基金信息
        import_fund_info()

        # 2. 导入股票/ETF持仓
        import_stock_positions()

        # 3. 导入场外基金持仓
        import_fund_positions()

        # 4. 导入定投计划
        import_sip_plans()

        # 5. 显示汇总
        calculate_portfolio_summary()

        print("\n" + "=" * 60)
        print("✅ 数据导入完成！")
        print("=" * 60)
        print("\n现在可以刷新 Streamlit 仪表盘查看数据：")
        print("  streamlit run projects/portfolio_analysis/visualization/streamlit_app.py")

    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
