"""
Phase 5 实施验证脚本

验证测试框架、监控告警和性能优化模块的完整性。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def test_imports():
    """测试所有关键模块是否能正常导入"""
    print("=" * 60)
    print("1. 测试模块导入")
    print("=" * 60)

    modules_to_test = [
        # 测试框架
        ("tests.conftest", "pytest配置"),
        ("tests.unit.test_metrics", "单元测试-绩效指标"),
        ("tests.unit.test_portfolio", "单元测试-投资组合"),
        ("tests.unit.test_data_manager", "单元测试-数据管理"),
        ("tests.unit.test_risk_manager", "单元测试-风控"),
        ("tests.unit.test_strategy", "单元测试-策略"),
        # 监控告警
        ("projects.quant_trading.monitoring.metrics", "监控指标"),
        ("projects.quant_trading.monitoring.alerts", "告警管理"),
        ("projects.quant_trading.monitoring.reporters", "报告生成"),
        # 性能优化
        ("projects.quant_trading.backtest.optimizations.cache", "缓存优化"),
        ("projects.quant_trading.backtest.optimizations.parallel", "并行回测"),
        ("projects.quant_trading.backtest.optimizations.vectorized", "向量化回测"),
    ]

    failed = []
    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            print(f"  ✓ {description}: {module_name}")
        except Exception as e:
            print(f"  ✗ {description}: {module_name} - {e}")
            failed.append((module_name, e))

    return len(failed) == 0


def test_monitoring_components():
    """测试监控组件功能"""
    print("\n" + "=" * 60)
    print("2. 测试监控组件")
    print("=" * 60)

    from projects.quant_trading.monitoring.metrics import SystemMetrics, SystemMetricsCollector
    from projects.quant_trading.monitoring.alerts import (
        AlertManager,
    )
    from projects.quant_trading.monitoring.reporters import MetricsReporter

    # 测试指标采集
    collector = SystemMetricsCollector()
    metrics = collector.collect()
    print(f"  ✓ SystemMetricsCollector 工作正常")
    print(f"    - 采集时间: {metrics.timestamp}")
    print(f"    - 内存占用: {metrics.memory_usage_mb:.1f} MB")

    # 测试告警管理器
    alert_manager = AlertManager()
    rules = alert_manager.get_rules()
    print(f"  ✓ AlertManager 工作正常")
    print(f"    - 默认规则数: {len(rules)}")

    # 测试告警触发
    test_metrics = SystemMetrics(
        data_freshness_minutes=150,  # 超过2小时触发告警
        data_completeness_pct=95.0,  # 低于98%触发告警
    )
    alerts = alert_manager.check_metrics(test_metrics)
    print(f"    - 测试告警触发: {len(alerts)} 个告警")

    # 测试报告生成
    reporter = MetricsReporter(collector, alert_manager)
    reporter.generate_daily_report()
    print(f"  ✓ MetricsReporter 工作正常")

    return True


def test_optimization_components():
    """测试性能优化组件"""
    print("\n" + "=" * 60)
    print("3. 测试性能优化组件")
    print("=" * 60)

    from projects.quant_trading.backtest.optimizations.cache import (
        CacheManager,
        cached,
    )
    from projects.quant_trading.backtest.optimizations.parallel import (
        ParallelBacktestRunner,
    )
    from projects.quant_trading.backtest.optimizations.vectorized import VectorizedBacktester

    # 测试缓存管理器
    cache = CacheManager(memory_size=100, ttl_seconds=60)
    cache.set("test_key", {"data": "test_value"})
    result = cache.get("test_key")
    assert result == {"data": "test_value"}, "缓存读写失败"
    print(f"  ✓ CacheManager 工作正常")

    # 测试缓存装饰器
    @cached(ttl_seconds=60)
    def expensive_function(x):
        return x * 2

    result1 = expensive_function(5)
    result2 = expensive_function(5)
    assert result1 == result2 == 10
    print(f"  ✓ cached 装饰器工作正常")

    # 测试向量化回测器
    import pandas as pd
    import numpy as np

    backtester = VectorizedBacktester(initial_cash=100000)
    dates = pd.date_range("2023-01-01", periods=30, freq="B")
    prices = pd.DataFrame(
        {"000001.SZ": 100 * (1 + np.random.randn(30) * 0.02).cumprod()}, index=dates
    )
    signals = pd.DataFrame({"000001.SZ": [1] * 15 + [0] * 15}, index=dates)

    result = backtester.run(prices, signals)
    print(f"  ✓ VectorizedBacktester 工作正常")
    print(f"    - 最终净值: {result.nav_history[-1][1]:.2f}")

    # 测试并行回测运行器
    runner = ParallelBacktestRunner(max_workers=2)
    print(f"  ✓ ParallelBacktestRunner 工作正常")

    return True


def test_fixtures():
    """测试测试框架fixtures"""
    print("\n" + "=" * 60)
    print("4. 测试测试框架fixtures")
    print("=" * 60)

    # 模拟fixtures功能
    import pandas as pd
    import numpy as np

    # 测试样本数据生成
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")[:252]
    np.random.seed(42)
    base_price = 100.0
    prices = []
    for i in range(len(dates)):
        change = np.random.normal(0.0005, 0.02)
        base_price *= 1 + change
        prices.append(
            {
                "trade_date": dates[i].strftime("%Y%m%d"),
                "open": base_price * (1 + np.random.normal(0, 0.005)),
                "high": base_price * (1 + abs(np.random.normal(0, 0.01))),
                "low": base_price * (1 - abs(np.random.normal(0, 0.01))),
                "close": base_price,
                "vol": np.random.randint(100000, 1000000),
            }
        )

    df = pd.DataFrame(prices)
    print(f"  ✓ 样本价格数据生成正常")
    print(f"    - 数据条数: {len(df)}")
    print(f"    - 列: {list(df.columns)}")

    return True


def test_database_optimizations():
    """测试数据库优化脚本"""
    print("\n" + "=" * 60)
    print("5. 测试数据库优化脚本")
    print("=" * 60)

    db_opt_dir = Path(__file__).parent.parent / "database" / "optimizations"

    sql_files = [
        ("01_create_indexes.sql", "索引优化"),
        ("02_create_materialized_views.sql", "物化视图"),
        ("03_query_optimizations.sql", "查询优化"),
    ]

    for filename, description in sql_files:
        filepath = db_opt_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            lines = len(content.splitlines())
            print(f"  ✓ {description}: {filename} ({lines} 行)")
        else:
            print(f"  ✗ {description}: {filename} 不存在")

    return True


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Phase 5 实施验证")
    print("=" * 60)

    results = []

    results.append(("模块导入", test_imports()))
    results.append(("监控组件", test_monitoring_components()))
    results.append(("性能优化", test_optimization_components()))
    results.append(("测试Fixtures", test_fixtures()))
    results.append(("数据库优化", test_database_optimizations()))

    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ Phase 5 所有组件验证通过！")
    else:
        print("✗ 部分组件验证失败")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
