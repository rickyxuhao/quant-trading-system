# 因子框架扩展指南

## 概述

本文档对比两种因子计算方式，并指导如何添加新因子。

| 框架 | 适用场景 | 性能 | 灵活性 |
|------|----------|------|--------|
| **SQLFactorEngine** (现有) | 固定因子集，追求极致性能 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **FactorRegistry** (新增) | 频繁添加新因子，实验阶段 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 方案一：现有 SQLFactorEngine（推荐用于生产）

### 添加新因子的步骤

以添加 `return_10d`（10日收益）为例：

#### 1. 修改 `sql_factor_engine.py`

找到 `_unified_factor_query()` 方法，在 `price_data` CTE 中添加：

```sql
LAG(close, 10) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_10d_ago,
```

在 `price_today` CTE 中添加：

```sql
(close / NULLIF(close_10d_ago, 0) - 1) as return_10d,
```

在最终的 SELECT 中添加输出：

```sql
p.return_10d,
```

#### 2. 修改 `precomputed_factors.py`

在 `PRECOMPUTED_FACTOR_SCHEMA` 中添加：

```python
"return_10d": "FLOAT",
```

#### 3. 更新数据库表

```sql
ALTER TABLE t_precomputed_factors ADD COLUMN return_10d FLOAT;
```

#### 4. 重新计算历史数据

```python
precomputer.batch_precompute(start_date, end_date, skip_existing=False)
```

**缺点**：每次修改需要改动核心代码，风险较高。

---

## 方案二：FactorRegistry（推荐用于研究/实验）

### 快速开始

```python
from projects.quant_trading.strategies.ml_prediction.factor_registry import (
    FactorRegistry, get_default_registry
)
from datetime import datetime

# 获取默认注册表（已包含常用因子）
registry = get_default_registry()

# 查看已有因子
print(registry.list_factors())
print(registry.list_factors(category="returns"))  # 按分类查看
```

### 添加新因子（无需修改核心代码）

#### 示例 1：SQL 因子（10日收益）

```python
# 注册新因子
registry.register_sql_factor(
    name="return_10d",
    sql_expr="(close / NULLIF(LAG(close, 10) OVER (PARTITION BY ts_code ORDER BY trade_date), 0) - 1)",
    description="10日收益率",
    category="returns"
)

# 立即使用
date = datetime(2024, 1, 15)
df = registry.compute_factors(date, stock_pool=['000001.SZ', '000002.SZ'])
print(df[['return_10d']])
```

#### 示例 2：Python 因子（动量差）

```python
# 注册 Python 计算因子
registry.register_python_factor(
    name="momentum_spread",
    compute_fn=lambda df: df['return_20d'] - df['return_5d'],
    dependencies=["return_20d", "return_5d"],
    description="20日减5日动量",
    category="momentum"
)

# 使用
df = registry.compute_factors(date, stock_pool)
print(df[['return_20d', 'return_5d', 'momentum_spread']])
```

#### 示例 3：批量注册相似因子

```python
# 一次性注册多个周期
for period in [5, 10, 20, 60, 120, 250]:
    registry.register_sql_factor(
        name=f"return_{period}d",
        sql_expr=f"(close / NULLIF(LAG(close, {period}) OVER w, 0) - 1)",
        description=f"{period}日收益率",
        category="returns"
    )
```

---

## 方案对比

| 维度 | SQLFactorEngine | FactorRegistry |
|------|-----------------|----------------|
| **添加因子** | 修改核心代码（3-4个文件） | 调用 `register_*` 方法 |
| **性能** | 单次查询 ~2秒/天 | 动态生成 SQL，性能接近 |
| **维护性** | 难（SQL 耦合） | 易（声明式定义） |
| **类型检查** | 无 | 有（FactorDefinition） |
| **适用阶段** | 生产环境 | 研究/实验/生产 |
| **依赖管理** | 手动 | 自动解析 |

---

## 混合使用策略（推荐）

对于生产系统，建议采用分层策略：

### 第一层：核心因子（SQLFactorEngine）

稳定、高频使用的基础因子：
- 估值因子：PE/PB/PS
- 基础收益：return_20d/60d
- 基础风险：volatility_20d/60d

### 第二层：实验因子（FactorRegistry）

快速迭代的实验性因子：
- 新发现的 Alpha 因子
- 不同参数的变体
- 组合因子

### 示例：混合使用

```python
# 1. 从核心引擎获取基础因子
from sql_factor_engine import SQLFactorEngine
engine = SQLFactorEngine()
base_factors = engine.calculate_factors_for_date(date, stock_pool)

# 2. 注册表添加实验因子
registry = FactorRegistry()
registry.register_python_factor(
    name="custom_alpha",
    compute_fn=lambda df: df['pe_ttm_zscore'] * 0.5 + df['return_20d_zscore'] * 0.5,
    dependencies=["pe_ttm_zscore", "return_20d_zscore"]
)

# 3. 计算实验因子并合并
custom_factors = registry.compute_factors(date, stock_pool, factor_names=['custom_alpha'])
all_factors = pd.concat([base_factors, custom_factors], axis=1)
```

---

## 未来改进方向

### 1. 配置文件驱动

支持 YAML/JSON 配置，完全无需改代码：

```yaml
# factors.yaml
factors:
  - name: return_10d
    type: sql
    expr: "(close / NULLIF(LAG(close, 10) OVER w, 0) - 1)"
    category: returns

  - name: momentum_score
    type: python
    expr: "df['return_20d'] - df['return_60d']"
    dependencies: [return_20d, return_60d]
```

### 2. 自动数据库迁移

注册因子时自动检查并添加表列：

```python
registry.register_sql_factor(..., auto_migrate=True)
```

### 3. 因子版本管理

支持因子迭代，保留历史版本：

```python
registry.register_sql_factor(
    name="volatility_20d",
    version="v2",
    sql_expr="...",
    changelog="修复了盘中数据问题"
)
```

### 4. 性能优化

- 惰性计算：只在需要时计算
- 缓存管理：自动缓存热门因子
- 增量更新：只计算缺失的日期

---

## 总结建议

| 场景 | 推荐方案 |
|------|----------|
| 生产系统，因子稳定 | SQLFactorEngine |
| 快速实验，频繁迭代 | FactorRegistry |
| 大规模生产+灵活实验 | 混合使用 |
| 团队协作 | FactorRegistry + 配置文件 |

当前框架**基本可用**，但如果计划频繁添加新因子或多人协作，建议**引入 FactorRegistry 或配置文件驱动**的改进。
