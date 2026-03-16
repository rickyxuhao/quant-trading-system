# 性能优化模块

## 功能概述

提供回测性能优化功能，包括并行回测、缓存机制和向量化计算。

## 模块结构

```
optimizations/
├── __init__.py           # 模块导出
├── parallel.py           # 并行回测
├── cache.py              # 缓存管理
└── vectorized.py         # 向量化回测
```

## 并行回测

支持多进程并行参数扫描，提高策略优化效率。

```python
from projects.quant_trading.backtest.optimizations import run_parallel_backtests
from projects.quant_trading.backtest.engine import BacktestConfig

# 定义参数网格
param_grid = [
    {"ma_short": 5, "ma_long": 20},
    {"ma_short": 10, "ma_long": 30},
    {"ma_short": 5, "ma_long": 60},
]

# 策略工厂函数
def strategy_factory(params):
    return MAStrategy(**params)

# 并行回测
config = BacktestConfig(
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    initial_cash=100000
)

results = run_parallel_backtests(
    param_grid=param_grid,
    config=config,
    strategy_factory=strategy_factory,
    n_workers=4
)

# 找出最佳参数
best = max(results, key=lambda r: r["results"]["metrics"].sharpe_ratio)
print(f"Best params: {best['params']}")
```

## 缓存管理

提供两级缓存机制：内存缓存 + 磁盘缓存。

```python
from projects.quant_trading.backtest.optimizations import CacheManager, cached

# 创建缓存管理器
cache = CacheManager(
    memory_size=1000,
    disk_path="./cache",
    ttl_seconds=3600
)

# 使用装饰器
@cached(ttl_seconds=7200)
def expensive_calculation(data):
    # 耗时计算
    return result

# 直接使用
value = cache.get("key")
if value is None:
    value = calculate()
    cache.set("key", value)
```

## 向量化回测

使用向量化计算进行快速回测，适合简单策略和参数扫描。

```python
from projects.quant_trading.backtest.optimizations import VectorizedBacktester

backtester = VectorizedBacktester(
    initial_cash=100000,
    commission_rate=0.00015,
    slippage_rate=0.0002
)

# 准备价格和信号数据
prices = pd.DataFrame(...)  # index=date, columns=ts_code
signals = pd.DataFrame(...)  # 1=买入, -1=卖出, 0=持有

# 执行回测
result = backtester.run(prices, signals)

print(f"Total return: {result.metrics.total_return:.2%}")
print(f"Sharpe ratio: {result.metrics.sharpe_ratio:.2f}")

# 优化仓位大小
best_size, best_result = backtester.optimize_position_size(
    prices, signals, size_range=np.linspace(0.1, 1.0, 10)
)
```

## 性能对比

| 优化方式 | 适用场景 | 预期加速 |
|:---|:---|:---|
| 并行回测 | 参数扫描 | 2-4x (取决于CPU核心数) |
| 缓存机制 | 重复查询 | 10-100x (缓存命中时) |
| 向量化回测 | 简单策略 | 10-50x |

## 注意事项

1. **并行回测**：每进程独立内存，不共享数据
2. **缓存管理**：注意TTL设置，避免数据过期
3. **向量化回测**：不支持复杂风控和滑点模型
