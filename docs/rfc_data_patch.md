# RFC: 数据缺口修复方案

**Requester**: data-engineer-001
**Architect**: architect-001
**Date**: 2026-03-22
**Status**: APPROVED

---

## 问题陈述

Phase 1 数据质量检查发现以下缺口：

| 因子 | 缺失率 | 原因 |
|------|--------|------|
| `rs_20d_market` | 99.5% NULL（仅首日有数据）| 计算公式未知，从未正确回填 |
| `rs_60d_market` | 100% NULL | 同上 |
| `entropy_20d` | 列不存在 | 从未写入 t_precomputed_factors |

## 决策方案

### 方案 A（选用）：最小化修复
1. **放弃 `rs_20d_market` / `rs_60d_market`**：用语义等价且已完整的因子替代
   - `market_alpha_20d`（缺失率 0.18%）→ 替代 `rs_20d_market`
   - `market_alpha_60d`（缺失率 0.99%）→ 替代 `rs_60d_market`
   - 定义：`market_alpha_Nd = return_Nd - AVG(return_Nd)` (等权市场均值)，语义等价

2. **新增并回填 `entropy_20d`**：添加列并从价格数据计算
   - 定义：Shannon entropy of daily trading amount over 20-day window
   - 数据来源：`tushare_biz.t_stock_dailymarketdata`（close × vol）
   - 范围：2024-01-02 ~ 2026-03-20，覆盖 5573 只股票

### 不选方案 B（完整回填 rs 列）
原因：rs_20d_market 计算公式不明，回填可能引入与 market_alpha 不一致的值，增加后续模型调试难度。

## 接口契约

### 新增 entropy_20d 列
```sql
ALTER TABLE interface.t_precomputed_factors
ADD COLUMN entropy_20d FLOAT DEFAULT NULL COMMENT '20日成交额分布Shannon熵，熵越小越集中（卖出信号）';
```

### 计算逻辑
```python
# 对每只股票，在 t-19 ~ t 窗口内：
# money_i = close_i * vol_i
# ratio_i = money_i / sum(money over 20 days)
# entropy_20d = -sum(ratio_i * log(ratio_i + eps))
# 语义：熵越小 → 成交集中某几日（高位） → 卖出信号
```

### 数据写入
- 更新 `t_precomputed_factors.entropy_20d` WHERE ts_code + trade_date 匹配
- 批量处理，每批 500 只股票，避免内存溢出
- 预估行数：5500 stocks × 212 dates ≈ 116 万行

## 影响文件

- `scripts/patch_entropy_factor.py`（新建，code-maintainer 实现）
- `t_precomputed_factors`（新增列 + 数据更新）
- 下游脚本无需修改（因子名不变）

## 后续因子列表调整

在 `scripts/factor_icir_analysis.py` 中：
- 从 FACTOR_GROUPS['momentum'] 移除 `rs_20d_market`、`rs_60d_market`
- 向 FACTOR_GROUPS['relative'] 补充 `market_alpha_20d`、`market_alpha_60d`（原已存在，确认不重复）
- 向 FACTOR_GROUPS['technical'] 补充 `entropy_20d`

## 验收标准

1. `entropy_20d` 列存在，缺失率 < 2%
2. `market_alpha_20d` 替代 `rs_20d_market` 在因子列表中生效
3. Phase 1-retry 验证通过（所有待测因子缺失率 < 5%）
