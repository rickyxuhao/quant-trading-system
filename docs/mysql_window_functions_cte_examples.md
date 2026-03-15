# MySQL 窗口函数与 CTE 查询优化示例

**文档目的**: 展示 MySQL 8.0+ 窗口函数和 CTE 在金融时间序列数据分析中的应用

**适用版本**: MySQL 8.0+

---

## 一、窗口函数 (Window Functions)

### 1.1 移动平均线计算

#### 简单移动平均 (SMA)
```sql
-- 计算 5日、10日、20日移动平均线
SELECT
    ts_code,
    trade_date,
    close,
    AVG(close) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS sma_5,
    AVG(close) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
    ) AS sma_10,
    AVG(close) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS sma_20
FROM tushare_biz.t_stock_dailymarketdata
WHERE ts_code = '600519.SH'
  AND trade_date >= '20240101'
ORDER BY trade_date;
```

#### 指数移动平均 (EMA)
```sql
-- 使用递归 CTE 计算 EMA (更复杂的实现)
WITH RECURSIVE price_data AS (
    SELECT
        ts_code,
        trade_date,
        close,
        ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date) AS rn
    FROM tushare_biz.t_stock_dailymarketdata
    WHERE ts_code = '600519.SH'
      AND trade_date >= '20240101'
),
ema_calc AS (
    -- 初始值: 第一个收盘价
    SELECT
        ts_code,
        trade_date,
        close,
        rn,
        close AS ema_12
    FROM price_data
    WHERE rn = 1

    UNION ALL

    -- 递归计算: EMA = α * Price + (1-α) * EMA_prev
    -- α = 2 / (N + 1), N=12 时 α = 0.1538
    SELECT
        p.ts_code,
        p.trade_date,
        p.close,
        p.rn,
        ROUND(0.1538 * p.close + 0.8462 * e.ema_12, 4) AS ema_12
    FROM price_data p
    JOIN ema_calc e ON p.ts_code = e.ts_code AND p.rn = e.rn + 1
)
SELECT ts_code, trade_date, close, ema_12
FROM ema_calc
ORDER BY trade_date;
```

### 1.2 排名与分位

#### 每日涨跌幅排名
```sql
-- 计算每日涨跌幅排名 (行业/全市场)
SELECT
    trade_date,
    ts_code,
    name,
    industry,
    pct_change,
    -- 全市场排名
    RANK() OVER (PARTITION BY trade_date ORDER BY pct_change DESC) AS rank_all,
    -- 行业内排名
    RANK() OVER (PARTITION BY trade_date, industry ORDER BY pct_change DESC) AS rank_industry,
    -- 全市场分位数 (0-1)
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY pct_change) AS percentile,
    -- 前N%标记 (涨停/5%+/下跌)
    CASE
        WHEN pct_change >= 9.9 THEN '涨停'
        WHEN pct_change >= 5 THEN '大涨'
        WHEN pct_change <= -9.9 THEN '跌停'
        WHEN pct_change <= -5 THEN '大跌'
        ELSE '正常'
    END AS change_category
FROM tushare_biz.t_stock_dailymarketdata
WHERE trade_date = '20250313'
ORDER BY pct_change DESC
LIMIT 50;
```

#### 滚动窗口排名
```sql
-- 近20日波动率排名
SELECT
    ts_code,
    trade_date,
    high,
    low,
    close,
    -- 近20日平均振幅
    AVG((high - low) / low * 100) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS avg_amplitude_20d,
    -- 波动率排名 (窗口内)
    RANK() OVER (
        ORDER BY AVG((high - low) / low * 100) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) DESC
    ) AS volatility_rank
FROM tushare_biz.t_stock_dailymarketdata
WHERE trade_date >= '20250201'
ORDER BY trade_date DESC, volatility_rank
LIMIT 100;
```

### 1.3 累计计算

#### 累计收益率
```sql
-- 计算累计收益率 (从基准日开始)
WITH base_prices AS (
    SELECT
        ts_code,
        close AS base_close,
        MIN(trade_date) OVER (PARTITION BY ts_code) AS base_date
    FROM tushare_biz.t_stock_dailymarketdata
    WHERE trade_date >= '20240101'
    GROUP BY ts_code
)
SELECT
    d.ts_code,
    d.trade_date,
    d.close,
    b.base_close,
    -- 累计收益率
    ROUND((d.close - b.base_close) / b.base_close * 100, 4) AS total_return_pct,
    -- 累计对数收益率 (用于多期复合)
    SUM(LOG(d.close / LAG(d.close, 1, d.close) OVER (PARTITION BY d.ts_code ORDER BY d.trade_date)))
        OVER (PARTITION BY d.ts_code ORDER BY d.trade_date) AS log_return_cum
FROM tushare_biz.t_stock_dailymarketdata d
JOIN base_prices b ON d.ts_code = b.ts_code
WHERE d.trade_date >= '20240101'
ORDER BY d.ts_code, d.trade_date;
```

#### 成交量累计与均量
```sql
-- 计算不同周期的累计成交量和均量
SELECT
    ts_code,
    trade_date,
    volume,
    amount,
    -- 5日累计成交量
    SUM(volume) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS volume_sum_5d,
    -- 5日均量
    AVG(volume) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS volume_avg_5d,
    -- 量能比 (当日/5日均量)
    volume / AVG(volume) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS volume_ratio,
    -- 20日累计成交额
    SUM(amount) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS amount_sum_20d
FROM tushare_biz.t_stock_dailymarketdata
WHERE ts_code = '000001.SZ'
  AND trade_date >= '20240101'
ORDER BY trade_date;
```

### 1.4 行间比较 (LAG/LEAD)

#### 计算涨跌停状态变化
```sql
-- 识别涨跌停板的打开与封板
WITH daily_changes AS (
    SELECT
        ts_code,
        trade_date,
        close,
        pct_change,
        ROUND((close - pre_close) / pre_close * 100, 2) AS calculated_change,
        -- 判断涨跌停
        CASE
            WHEN pct_change >= 9.9 THEN '涨停'
            WHEN pct_change <= -9.9 THEN '跌停'
            ELSE '正常'
        END AS limit_status,
        -- 前一日状态
        LAG(pct_change) OVER (PARTITION BY ts_code ORDER BY trade_date) AS prev_pct_change,
        -- 后一日状态
        LEAD(pct_change) OVER (PARTITION BY ts_code ORDER BY trade_date) AS next_pct_change
    FROM tushare_biz.t_stock_dailymarketdata
    WHERE ts_code LIKE '000001%'
      AND trade_date >= '20240101'
)
SELECT
    ts_code,
    trade_date,
    close,
    pct_change,
    limit_status,
    -- 连续涨停天数计算
    CASE
        WHEN pct_change >= 9.9 THEN
            ROW_NUMBER() OVER (
                PARTITION BY ts_code,
                -- 分组: 连续涨停的段
                CASE WHEN pct_change >= 9.9 THEN 0 ELSE 1 END
                ORDER BY trade_date
            )
        ELSE 0
    END AS consecutive_limits
FROM daily_changes
ORDER BY trade_date DESC, pct_change DESC;
```

#### 跳空缺口检测
```sql
-- 检测向上/向下跳空缺口
SELECT
    ts_code,
    trade_date,
    open,
    high,
    low,
    close,
    -- 前一日最高
    LAG(high) OVER (PARTITION BY ts_code ORDER BY trade_date) AS prev_high,
    -- 前一日最低
    LAG(low) OVER (PARTITION BY ts_code ORDER BY trade_date) AS prev_low,
    -- 判断跳空类型
    CASE
        WHEN low > LAG(high) OVER (PARTITION BY ts_code ORDER BY trade_date) THEN '向上跳空'
        WHEN high < LAG(low) OVER (PARTITION BY ts_code ORDER BY trade_date) THEN '向下跳空'
        ELSE '无跳空'
    END AS gap_type,
    -- 跳空幅度
    CASE
        WHEN low > LAG(high) OVER (PARTITION BY ts_code ORDER BY trade_date)
            THEN ROUND((low - LAG(high) OVER (PARTITION BY ts_code ORDER BY trade_date)) / LAG(high) OVER (PARTITION BY ts_code ORDER BY trade_date) * 100, 2)
        WHEN high < LAG(low) OVER (PARTITION BY ts_code ORDER BY trade_date)
            THEN ROUND((high - LAG(low) OVER (PARTITION BY ts_code ORDER BY trade_date)) / LAG(low) OVER (PARTITION BY ts_code ORDER BY trade_date) * 100, 2)
        ELSE 0
    END AS gap_pct
FROM tushare_biz.t_stock_dailymarketdata
WHERE ts_code = '000001.SZ'
  AND trade_date >= '20240101'
ORDER BY trade_date;
```

### 1.5 分组聚合 (PARTITION BY)

#### 行业相对强弱
```sql
-- 计算个股相对于行业的强弱
WITH industry_avg AS (
    SELECT
        trade_date,
        industry,
        AVG(pct_change) AS industry_avg_change,
        AVG(volume_ratio) AS industry_avg_volume
    FROM tushare_biz.t_stock_dailymarketdata
    WHERE trade_date >= '20250101'
    GROUP BY trade_date, industry
)
SELECT
    d.ts_code,
    d.name,
    d.trade_date,
    d.industry,
    d.pct_change,
    i.industry_avg_change,
    -- 相对行业强弱
    ROUND(d.pct_change - i.industry_avg_change, 2) AS relative_strength,
    -- 行业内分位数
    NTILE(4) OVER (
        PARTITION BY d.trade_date, d.industry
        ORDER BY d.pct_change
    ) AS quartile,
    -- 是否跑赢行业
    CASE WHEN d.pct_change > i.industry_avg_change THEN 1 ELSE 0 END AS beat_industry
FROM tushare_biz.t_stock_dailymarketdata d
JOIN industry_avg i
    ON d.trade_date = i.trade_date AND d.industry = i.industry
WHERE d.trade_date = '20250313'
ORDER BY d.industry, relative_strength DESC;
```

---

## 二、公用表表达式 (CTE)

### 2.1 递归 CTE

#### 获取连续交易日期序列
```sql
-- 生成连续的交易日序列 (填充停牌日期)
WITH RECURSIVE trading_days AS (
    -- 基础: 第一个交易日
    SELECT MIN(cal_date) AS trade_date
    FROM tushare_biz.t_stock_tradedate
    WHERE is_open = 1 AND cal_date >= '20240101'

    UNION ALL

    -- 递归: 下一个交易日
    SELECT (
        SELECT MIN(cal_date)
        FROM tushare_biz.t_stock_tradedate
        WHERE is_open = 1 AND cal_date > trading_days.trade_date
    )
    FROM trading_days
    WHERE trade_date < '20241231'
),
-- 股票数据填充
stock_data AS (
    SELECT ts_code, trade_date, close
    FROM tushare_biz.t_stock_dailymarketdata
    WHERE ts_code = '600519.SH'
      AND trade_date >= '20240101'
)
SELECT
    t.trade_date,
    s.close,
    -- 前向填充 (使用最近的收盘价)
    COALESCE(s.close, (
        SELECT close FROM stock_data
        WHERE trade_date <= t.trade_date AND close IS NOT NULL
        ORDER BY trade_date DESC LIMIT 1
    )) AS filled_close,
    CASE WHEN s.close IS NULL THEN '停牌' ELSE '交易' END AS status
FROM trading_days t
LEFT JOIN stock_data s ON t.trade_date = s.trade_date
ORDER BY t.trade_date;
```

#### 层级数据遍历 (概念板块)
```sql
-- 假设有概念板块层级表
WITH RECURSIVE concept_hierarchy AS (
    -- 基础: 顶层概念
    SELECT
        concept_code,
        concept_name,
        parent_code,
        1 AS level,
        CAST(concept_name AS CHAR(255)) AS path
    FROM concept_categories
    WHERE parent_code IS NULL

    UNION ALL

    -- 递归: 子概念
    SELECT
        c.concept_code,
        c.concept_name,
        c.parent_code,
        ch.level + 1,
        CONCAT(ch.path, ' > ', c.concept_name)
    FROM concept_categories c
    JOIN concept_hierarchy ch ON c.parent_code = ch.concept_code
)
SELECT * FROM concept_hierarchy
ORDER BY path;
```

### 2.2 非递归 CTE

#### 多步数据处理流程
```sql
-- 计算多因子得分
WITH
-- 步骤1: 基础数据
price_data AS (
    SELECT
        ts_code,
        trade_date,
        close,
        volume,
        amount,
        pct_change
    FROM tushare_biz.t_stock_dailymarketdata
    WHERE trade_date >= '20250101'
),

-- 步骤2: 计算技术指标
technical_indicators AS (
    SELECT
        ts_code,
        trade_date,
        close,
        volume,
        -- 20日波动率
        STDDEV(pct_change) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) AS volatility_20d,
        -- 成交量变化率
        volume / AVG(volume) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) - 1 AS volume_change_pct
    FROM price_data
),

-- 步骤3: 计算排名得分
ranked_scores AS (
    SELECT
        ts_code,
        trade_date,
        close,
        volatility_20d,
        volume_change_pct,
        -- 低波动率得分 (越低越好)
        PERCENT_RANK() OVER (ORDER BY volatility_20d ASC) AS low_vol_score,
        -- 高成交量得分 (越高越好)
        PERCENT_RANK() OVER (ORDER BY volume_change_pct DESC) AS high_vol_score
    FROM technical_indicators
    WHERE trade_date = '20250313'
),

-- 步骤4: 综合评分
final_score AS (
    SELECT
        ts_code,
        trade_date,
        close,
        volatility_20d,
        volume_change_pct,
        -- 综合因子得分 (等权)
        ROUND((low_vol_score + high_vol_score) / 2 * 100, 2) AS composite_score,
        -- 评级
        CASE
            WHEN (low_vol_score + high_vol_score) / 2 >= 0.8 THEN 'A'
            WHEN (low_vol_score + high_vol_score) / 2 >= 0.6 THEN 'B'
            WHEN (low_vol_score + high_vol_score) / 2 >= 0.4 THEN 'C'
            ELSE 'D'
        END AS grade
    FROM ranked_scores
)

SELECT * FROM final_score
ORDER BY composite_score DESC
LIMIT 50;
```

#### 多表关联分析
```sql
-- 综合分析: 行情 + 基本面 + 资金流向
WITH
-- 最新行情
latest_price AS (
    SELECT ts_code, trade_date, close, pct_change, volume, amount
    FROM tushare_biz.t_stock_dailymarketdata
    WHERE trade_date = '20250313'
),

-- 基本面指标
fundamentals AS (
    SELECT
        ts_code,
        eps,
        bvps,
        total_mv,
        pe_ttm,
        pb_mrq
    FROM tushare_biz.t_stock_daily_basic
    WHERE trade_date = '20250313'
),

-- 资金流向
money_flow AS (
    SELECT
        ts_code,
        buy_elg_amount,
        sell_elg_amount,
        net_mf_amount
    FROM tushare_biz.t_stock_moneyflow
    WHERE trade_date = '20250313'
)

SELECT
    p.ts_code,
    p.trade_date,
    p.close,
    p.pct_change,
    f.eps,
    f.pe_ttm,
    f.pb_mrq,
    f.total_mv / 10000 AS market_cap_yi, -- 亿元
    m.net_mf_amount / 10000 AS net_inflow_yi, -- 亿元
    -- 综合评分
    CASE
        WHEN f.pe_ttm > 0 AND f.pe_ttm < 30 AND m.net_mf_amount > 0 THEN '价值+资金关注'
        WHEN f.pe_ttm > 50 AND m.net_mf_amount < 0 THEN '高估+资金流出'
        ELSE '中性'
    END AS recommendation
FROM latest_price p
LEFT JOIN fundamentals f ON p.ts_code = f.ts_code
LEFT JOIN money_flow m ON p.ts_code = m.ts_code
WHERE f.total_mv > 100000000000  -- 市值>100亿
ORDER BY m.net_mf_amount DESC
LIMIT 30;
```

### 2.3 CTE 与窗口函数结合

#### 计算历史分位点
```sql
-- 计算当前 PE 在历史中的分位
WITH historical_pe AS (
    SELECT
        ts_code,
        trade_date,
        pe_ttm,
        PERCENT_RANK() OVER (
            PARTITION BY ts_code
            ORDER BY pe_ttm
        ) AS pe_historical_percentile
    FROM tushare_biz.t_stock_daily_basic
    WHERE trade_date >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR)
),
current_pe AS (
    SELECT ts_code, pe_ttm, pe_historical_percentile
    FROM historical_pe
    WHERE trade_date = '20250313'
)
SELECT
    c.ts_code,
    c.pe_ttm,
    ROUND(c.pe_historical_percentile * 100, 2) AS pe_percentile_rank,
    CASE
        WHEN c.pe_historical_percentile < 0.1 THEN '极度低估'
        WHEN c.pe_historical_percentile < 0.3 THEN '低估'
        WHEN c.pe_historical_percentile > 0.9 THEN '极度高估'
        WHEN c.pe_historical_percentile > 0.7 THEN '高估'
        ELSE '合理'
    END AS valuation_status
FROM current_pe c
ORDER BY c.pe_historical_percentile
LIMIT 50;
```

---

## 三、查询优化技巧

### 3.1 索引优化建议

```sql
-- 窗口函数查询的索引建议

-- 1. 支持 PARTITION BY + ORDER BY 的复合索引
ALTER TABLE t_stock_dailymarketdata
ADD INDEX idx_symbol_date (ts_code, trade_date);

-- 2. 支持 WHERE + ORDER BY 的索引
ALTER TABLE t_stock_dailymarketdata
ADD INDEX idx_date_symbol (trade_date, ts_code);

-- 3. 覆盖索引 (包含常用字段)
ALTER TABLE t_stock_dailymarketdata
ADD INDEX idx_covering (ts_code, trade_date, close, volume, pct_change);
```

### 3.2 分区表优化

```sql
-- 按日期范围分区 (适合时间序列数据)
ALTER TABLE t_stock_dailymarketdata
PARTITION BY RANGE (YEAR(trade_date)) (
    PARTITION p2020 VALUES LESS THAN (2021),
    PARTITION p2021 VALUES LESS THAN (2022),
    PARTITION p2022 VALUES LESS THAN (2023),
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION pfuture VALUES LESS THAN MAXVALUE
);

-- 分区裁剪示例: 只扫描 2024 年分区
SELECT * FROM t_stock_dailymarketdata
WHERE trade_date >= '20240101' AND trade_date < '20250101';
```

### 3.3 性能对比

| 查询类型 | 传统子查询 | 窗口函数 | 性能提升 |
|:---|:---|:---|:---|
| 移动平均 | JOIN + 子查询 | AVG() OVER | 5-10x |
| 排名计算 | 变量自增 | RANK() | 10-50x |
| 累计求和 | 递归/变量 | SUM() OVER | 10-20x |
| 行间比较 | 自连接 | LAG/LEAD | 5-15x |

### 3.4 执行计划分析

```sql
-- 使用 EXPLAIN ANALYZE 查看执行计划
EXPLAIN ANALYZE
SELECT
    ts_code,
    trade_date,
    close,
    AVG(close) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    )
FROM tushare_biz.t_stock_dailymarketdata
WHERE ts_code = '600519.SH'
  AND trade_date >= '20240101';

-- 预期输出:
-- -> Window aggregate: avg(close) OVER (PARTITION BY ts_code ... )
--    -> Index range scan on t_stock_dailymarketdata using idx_symbol_date
```

---

## 四、实用函数汇总

### 4.1 窗口函数速查表

| 函数 | 用途 | 示例 |
|:---|:---|:---|
| `ROW_NUMBER()` | 行号 (唯一) | 生成序号 |
| `RANK()` | 排名 (跳号) | 涨跌幅排名 |
| `DENSE_RANK()` | 密集排名 (不跳号) | 评级分组 |
| `NTILE(n)` | 分桶 | 四分位分组 |
| `LEAD(n)` | 向后取n行 | 次日收盘价 |
| `LAG(n)` | 向前取n行 | 前日收盘价 |
| `FIRST_VALUE()` | 窗口内第一个 | 区间最高价 |
| `LAST_VALUE()` | 窗口内最后一个 | 区间最低价 |
| `NTH_VALUE()` | 窗口内第n个 | 第三高值 |
| `SUM/AVG/COUNT()` | 聚合 | 移动平均 |
| `MIN/MAX()` | 极值 | 区间高低点 |
| `STDDEV()` | 标准差 | 波动率 |

### 4.2 窗口定义

```sql
-- 行窗口
ROWS BETWEEN 4 PRECEDING AND CURRENT ROW  -- 前5行(含当前)
ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW  -- 从开始到当前
ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING  -- 前1后1

-- 范围窗口 (基于值)
RANGE BETWEEN INTERVAL 7 DAY PRECEDING AND CURRENT ROW  -- 前7天
```

---

## 五、参考资源

1. **MySQL 官方文档**: https://dev.mysql.com/doc/refman/8.0/en/window-functions.html
2. **窗口函数性能优化**: https://dev.mysql.com/blog-archive/mysql-8-0-window-functions-how-to-take-advantage-of-sql-involution/
3. **金融时间序列分析模式**: 参见项目 `docs/sync_guide.md`

---

*文档创建时间: 2026-03-15*
*适用数据库: MySQL 8.0+*
