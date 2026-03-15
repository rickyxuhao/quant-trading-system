# 券商金股监控分析系统

## 项目概述

券商金股监控分析系统是一个集数据同步、多维分析、异动检测、AI分析和报告生成于一体的股票投资分析平台。

## 核心功能

### 1. 金股数据管理
- 从Tushare同步券商每月金股推荐数据
- 自动去重和更新
- 支持历史数据回溯

### 2. 多维度分析引擎
- **技术分析**：趋势、支撑压力、动量指标、成交量
- **财务分析**：估值、盈利能力、成长性、财务健康度
- **量化因子**：价值、质量、成长、动量、波动率、流动性

### 3. 异动检测
- 价格异动检测（涨跌超5%）
- 成交量异动检测（量比超2倍）
- 涨跌停检测
- 技术突破检测

### 4. AI分析服务
- 新闻情感分析
- 买入机会分析
- 每日投资策略生成

### 5. 晨间报告
- 每日自动生成投资报告
- Markdown格式输出
- 重点金股推荐
- 异动提醒
- 风险提示

## 项目结构

```
broker_gold_stock/
├── __init__.py              # 包初始化
├── cli.py                   # 命令行工具
├── config/                  # 配置文件
│   └── gold_stock.yaml     # 主配置
├── database/                # 数据库
│   └── schema.sql          # 表结构
├── data/                    # 数据层
│   ├── models.py           # 数据模型
│   ├── repository.py       # 数据访问层
│   └── sync/               # 数据同步
│       └── gold_stock_sync.py
├── analysis/                # 分析层
│   ├── technical_analyzer.py    # 技术分析
│   ├── financial_analyzer.py    # 财务分析
│   ├── quant_factor_analyzer.py # 量化因子
│   ├── anomaly_detector.py      # 异动检测
│   └── composite_scorer.py      # 综合评分
├── shared/                  # 共享服务层
│   └── services/
│       ├── ai_service.py   # AI服务
│       └── news_service.py # 新闻服务
├── report/                  # 报告层
│   ├── templates/          # 报告模板
│   └── morning_report.py   # 晨间报告生成器
└── scheduler/               # 调度层
    └── morning_task.py     # 晨间任务调度
```

## 快速开始

### 1. 安装依赖

```bash
# 确保已安装项目依赖
pip install -r requirements.txt

# AI功能需要额外安装
pip install anthropic

# 定时任务需要
pip install apscheduler
```

### 2. 配置环境变量

在 `.env` 文件中添加：

```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME_TUSHARE=tushare_biz
DB_NAME_INTERFACE=interface

# Tushare Token
TUSHARE_TOKEN=your_tushare_token

# AI服务 (可选)
ANTHROPIC_API_KEY=your_anthropic_key
```

### 3. 初始化数据库

```bash
cd projects/broker_gold_stock
python cli.py init
```

### 4. 同步金股数据

```bash
# 同步当前月份（默认）
python cli.py sync

# 同步指定月份
python cli.py sync 202603

# 同步最近3个月
python cli.py sync --months 3
```

**注意**：系统会自动去重，同一只股票被多家券商推荐只保留一条记录进行分析。

### 5. 分析股票

```bash
# 分析单只股票
python cli.py analyze 000001.SZ

# 分析本月所有金股
python cli.py analyze
```

### 6. 生成报告

```bash
# 生成今日报告
python cli.py report

# 生成指定日期报告
python cli.py report 20260310
```

### 7. 启动定时任务

```bash
# 每天早上8点自动生成报告
python cli.py schedule
```

## 数据库表结构

### 核心表

| 表名 | 说明 |
|------|------|
| `broker_gold_stock` | 券商金股推荐数据 |
| `gold_stock_performance` | 金股表现追踪 |
| `financial_analysis` | 财务指标分析 |
| `quant_factor_score` | 量化因子评分 |
| `stock_anomaly` | 异动检测记录 |
| `news_sentiment` | 新闻舆情数据 |
| `morning_report` | 晨间报告记录 |

### 数据处理逻辑

**去重机制**：
- 同一只股票可能被多家券商同时推荐（如中际旭创被4家券商推荐）
- 系统会自动去重，**同月内只分析一次**
- 报告会显示：`本月共有 108 只独特金股（来自 122 条券商推荐）`

**时间范围**：
- 默认只同步和分析**当前月份**的金股
- 可手动指定月份：`python cli.py sync 202603`

## 评分体系

### 综合评分计算

```
综合评分 = 技术评分 × 30% + 财务评分 × 30% + 量化因子 × 30% + 情绪 × 10%
```

### 评分等级

| 综合评分 | 建议 |
|----------|------|
| ≥85 | 强烈推荐买入 ⭐⭐⭐⭐⭐ |
| 75-84 | 推荐买入 ⭐⭐⭐⭐ |
| 60-74 | 持有/关注 ⭐⭐⭐ |
| 50-59 | 观望 ⭐⭐ |
| <50 | 规避 ⭐ |

## 扩展性设计

系统预留了以下扩展接口：

1. **量化策略分析** (v2.0)
   - 策略回测引擎
   - 信号生成系统
   - 绩效归因分析

2. **舆情风控监控** (v3.0)
   - 持仓同步
   - 舆情实时监控
   - 风险预警系统

3. **事件总线**
   - 模块间松耦合通信
   - 支持插件化扩展

## 配置说明

配置文件路径: `config/gold_stock.yaml`

主要配置项：

```yaml
analysis:
  weights:
    technical: 0.30    # 技术分析权重
    financial: 0.30    # 财务分析权重
    quant: 0.30        # 量化因子权重

anomaly:
  price_change_threshold: 5.0    # 价格异动阈值
  volume_ratio_threshold: 2.0    # 量比阈值

report:
  generate_time: "08:00"         # 报告生成时间
  top_stocks_limit: 20           # 展示数量
```

## 使用示例

### Python API

```python
from projects.broker_gold_stock.data.sync.gold_stock_sync import sync_gold_stock_data
from projects.broker_gold_stock.analysis.composite_scorer import MultiDimensionAnalyzer
from projects.broker_gold_stock.report.morning_report import MorningReportGenerator

# 同步数据
sync_gold_stock_data(month='202603')

# 分析股票
analyzer = MultiDimensionAnalyzer()
analysis = analyzer.analyze_stock('000001.SZ', '平安银行')

print(f"综合评分: {analysis.composite_score}")
print(f"技术评分: {analysis.technical.total}")
print(f"财务评分: {analysis.financial.total}")

# 生成报告
import asyncio
generator = MorningReportGenerator()
asyncio.run(generator.generate())
```

## 注意事项

1. **Tushare权限**: 确保账号有 `broker_recommend` 接口权限
2. **数据更新**: 金股数据通常在每月初更新
3. **报告时间**: 建议早上8点后生成报告（等待日线数据更新）
4. **AI功能**: 需要配置 `ANTHROPIC_API_KEY` 才能使用AI分析

## 问题排查

### 数据库连接失败
- 检查 `.env` 文件中的数据库配置
- 确保MySQL服务已启动

### Tushare API错误
- 检查 `TUSHARE_TOKEN` 是否配置正确
- 确认有相应接口的访问权限

### 缺少依赖
```bash
pip install anthropic apscheduler pandas numpy
```

## 更新日志

### v1.0.0 (2026-03-10)
- 初始版本发布
- 实现金股数据同步
- 多维度分析引擎
- 异动检测功能
- AI分析服务
- 晨间报告生成

## License

MIT License
