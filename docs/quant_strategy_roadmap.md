# 量化策略路线图：ML预测与组合构建

> 创建时间: 2026-03-17
> 最后更新: 2026-03-17

## 项目目标

构建基于机器学习的A股量化交易系统，实现从信号生成到组合优化的完整工作流，输出日频交易信号。

---

## 当前能力盘点

### 已有基础设施

| 模块 | 状态 | 文件位置 |
|------|------|----------|
| ML模型 | ✅ 可用 | `projects/quant_trading/strategies/ml_prediction/` |
| 技术指标 | ✅ 40+指标 | `feature_engineering.py` (TA-Lib集成) |
| 仓位管理 | ✅ 多种算法 | `position_sizing.py` |
| 回测引擎 | ✅ 事件驱动 | `engine.py` |
| 数据接入 | ✅ Tushare | `core/data_access/tushare/` |

### 当前局限

- 仅支持**单股票回测**，无法构建多股票组合
- 缺少**横截面**选股能力（行业中性化、Z-score标准化）
- 缺少**基本面因子**（PE、PB、ROE等）
- 缺少**资金流向因子**

---

## 用户确认需求

| 需求项 | 用户选择 | 说明 |
|--------|----------|------|
| 预测目标 | 未来收益率（回归） | 而非涨跌分类 |
| 股票池 | 动态筛选 | 沪深300 / 特定行业 / 剔除ST全市场 |
| 选股数量 | 前30-50名 | 基于预测得分排序 |
| 调仓频率 | 对比测试 | 日频 vs 周频，回测决定 |
| 资金分配 | 优化器决定 | 由组合优化器计算权重，非等分 |
| 风险控制 | 规则+BARRA | 板块限制+回撤控制+波动率目标+多因子风险模型 |
| 集成策略 | 分市场环境 | 牛市/熊市/高波动使用不同模型 |
| 特征扩展 | 全面扩展 | 基本面+资金流+另类数据+论文因子挖掘 |
| 数据周期 | 2010年至今 | 训练:2010-2022, 测试:2023-2024 |

---

## 因子挖掘框架设计

### 框架架构

```
Factor Mining Framework
├── Data Sources (数据源)
│   ├── Market Data (价格、成交量)
│   ├── Fundamental Data (财务数据)
│   ├── Money Flow (资金流向)
│   └── Alternative Data (另类数据)
│
├── Factor Repository (因子库)
│   ├── Classical Factors (经典因子)
│   │   ├── Value (PE, PB, PS, PCF)
│   │   ├── Quality (ROE, ROA, 毛利率)
│   │   ├── Growth (营收增速, 利润增速)
│   │   ├── Momentum (20日/60日动量)
│   │   └── Volatility (波动率, 最大回撤)
│   │
│   ├── Technical Factors (技术因子)
│   │   ├── Trend (均线排列, MACD)
│   │   ├── Reversal (RSI极端值, 量价背离)
│   │   ├── Volume (放量突破, 缩量回调)
│   │   └── Pattern (K线形态)
│   │
│   ├── Microstructure Factors (微观结构)
│   │   ├── Order Flow (大单净流入比率)
│   │   ├── Northbound (北向资金流向)
│   │   ├── Liquidity (Amihud非流动性)
│   │   └── Turnover (换手率变化)
│   │
│   └── Custom Factors (自定义因子)
│       └── 学术研究导入区
│
├── Factor Research Pipeline (研究流程)
│   1. 单因子IC测试
│   2. 因子相关性分析
│   3. 因子正交化
│   4. 多因子组合
│   5. 回测验证
│
└── Academic Integration (学术研究)
    ├── Paper Parser (论文解析器)
    │   - 输入: PDF/论文文本
    │   - 输出: 可计算因子公式
    ├── Factor Implementation (因子实现)
    │   - 根据论文描述编写因子代码
    ├── Reproduction Test (复现测试)
    │   - 与论文结果对比验证
    └── Performance Tracker (表现跟踪)
        - 记录因子衰减情况
```

### 学术研究因子导入流程

1. **发现**: 阅读JFE、RFS、JFQA等顶级期刊
2. **解析**: 提取因子公式、参数、回测设置
3. **实现**: 用Python编写因子计算逻辑
4. **验证**: 复现论文中的单因子表现
5. **本地化**: 调整适配A股市场
6. **集成**: 加入因子库，参与IC测试

**推荐阅读资源**:
- 期刊: Journal of Financial Economics, Review of Financial Studies
- 中文: 《经济研究》《管理世界》《金融研究》
- 网站: SSRN, AQR Research Papers

---

## 实施路线图

### Phase 1: 横截面特征工程 (2周)

**目标**: 构建全行业可比的标准化因子

**新增文件**:
- `projects/quant_trading/strategies/ml_prediction/cross_sectional_features.py`
- `projects/quant_trading/strategies/ml_prediction/universe_selector.py`

**实现功能**:
```python
# 横截面标准化
- 行业中性化: factor_zscore - industry_mean
- 市值中性化: 剔除市值影响的残差
- 分位数转换: 0-1标准化

# 新增因子类别
估值因子: pe_ttm_zscore, pb_zscore, ps_ttm_zscore, pcf_zscore
质量因子: roe_zscore, roa_zscore, gross_margin_zscore
成长因子: revenue_yoy_zscore, profit_yoy_zscore
资金流因子: large_order_net_ratio, northbound_flow_5d, money_flow_trend
相对强弱因子: rs_20d_sector, rs_60d_market, volatility_percentile
```

### Phase 2: 因子挖掘框架 (2周)

**目标**: 建立因子研究、测试、集成工作流

**新增文件**:
- `projects/quant_trading/research/__init__.py`
- `projects/quant_trading/research/factor_repository.py`
- `projects/quant_trading/research/factor_analyzer.py`
- `projects/quant_trading/research/paper_importer.py`

**功能模块**:
- `FactorRepository`: 因子注册、版本管理、元数据
- `FactorAnalyzer`: 单因子IC测试、分层回测、衰减分析
- `PaperImporter`: 论文因子解析模板

### Phase 3: 市场环境识别 + 多模型 (2周)

**目标**: 识别牛/熊/高波动环境，使用对应模型

**新增文件**:
- `projects/quant_trading/strategies/ml_prediction/market_regime_detector.py`
- `projects/quant_trading/strategies/ml_prediction/regime_specific_model.py`

**环境定义**:
```python
REGIME_DEFINITIONS = {
    'bull_trend': 波动率<15% AND 趋势>0 AND 均线多头排列,
    'bear_trend': 波动率<20% AND 趋势<0 AND 均线空头排列,
    'high_vol': 波动率>25%,
    'normal': 其他情况
}
```

### Phase 4: 风险感知组合优化 (3周)

**目标**: 将预测转化为可执行的交易组合

**新增文件**:
- `projects/quant_trading/backtest/risk_model.py` (BARRA风格)
- `projects/quant_trading/backtest/portfolio_optimizer.py`
- `projects/quant_trading/backtest/risk_constraints.py`

**组合优化模型**:
```
目标: 最大化 预期收益 - 风险惩罚
约束:
  - 单股权重: 0% ≤ w_i ≤ max_position (如 10%)
  - 行业权重: ∑w_i(行业j) ≤ 20%
  - 目标波动率: σ_portfolio = 15%
  - 现金比例: 保留5-10%
  - 换手率惩罚: 考虑交易成本
```

**资金分配逻辑**:
```
1. 预测收益率 → 原始得分
2. 风险调整得分 = 原始得分 / 个股波动率
3. 组合优化求解 → 目标权重
4. 权重 × 总资金 = 每只目标市值
5. 考虑100股整数倍调整
```

### Phase 5: 验证框架 (1周)

**目标**: 科学评估策略表现

**新增文件**:
- `projects/quant_trading/evaluation/ic_analysis.py`
- `projects/quant_trading/evaluation/bootstrap_validator.py`
- `projects/quant_trading/evaluation/turnover_analyzer.py`

**评估指标**:
| 指标 | 说明 | 目标值 |
|------|------|--------|
| IC (信息系数) | 预测与实际的相关系数 | > 0.03 |
| ICIR | IC的稳定性 (IC/Std) | > 0.5 |
| 分位数收益 | Q5(前20%) - Q1(后20%) | > 1%/月 |
| 夏普比率 | 风险调整后收益 | > 1.0 |
| 最大回撤 | 最大资金回落 | < 20% |
| 换手率 | 月均换手率 | < 100% |

---

## 数据使用计划

| 数据范围 | 用途 | 说明 |
|----------|------|------|
| 2010-2018 | 额外训练数据 | 提供更长的历史样本 |
| 2019-2022 | 主要训练数据 | 包含完整牛熊周期 |
| 2023-2024 | 测试数据 | 纯样本外测试 |

**数据检查清单**:
- [ ] 确认2010年以来日线数据完整性
- [ ] 确认财务报表数据覆盖度
- [ ] 确认资金流向数据起始时间
- [ ] 处理退市股票、ST股票过滤

---

## 文件结构规划

```
projects/quant_trading/
├── strategies/ml_prediction/
│   ├── cross_sectional_features.py      # 新增: 横截面特征
│   ├── universe_selector.py             # 新增: 股票池筛选
│   ├── market_regime_detector.py        # 新增: 市场环境识别
│   ├── regime_specific_model.py         # 新增: 分环境模型
│   └── factor_ensemble.py               # 新增: 因子集成
│
├── backtest/
│   ├── risk_model.py                    # 新增: BARRA风险模型
│   ├── portfolio_optimizer.py           # 新增: 组合优化器
│   ├── risk_constraints.py              # 新增: 风险约束
│   └── multi_stock_engine.py            # 新增: 多股票回测引擎
│
├── research/                            # 新增目录
│   ├── __init__.py
│   ├── factor_repository.py             # 因子库
│   ├── factor_analyzer.py               # 因子分析
│   ├── paper_importer.py                # 论文导入
│   └── factor_templates.py              # 因子模板
│
├── evaluation/                          # 新增目录
│   ├── __init__.py
│   ├── ic_analysis.py                   # IC分析
│   ├── bootstrap_validator.py           # Bootstrap验证
│   └── turnover_analyzer.py             # 换手率分析
│
└── run_cross_sectional_backtest.py      # 新增: 主运行脚本
```

---

## 下一步行动

1. **确认本计划** - 用户审核并确认路线图
2. **数据审计** - 检查2010年以来数据完整性
3. **Phase 1启动** - 开始横截面特征工程

---

## 附录: BARRA风险模型简介

BARRA模型将个股收益分解为:
```
R_i = ∑(X_ik × F_k) + ε_i

其中:
- X_ik: 股票i在因子k上的暴露
- F_k: 因子k的收益
- ε_i: 个股特异性收益
```

**因子分类**:
- 国家因子: 市场整体收益 (CSI 300)
- 行业因子: 28个申万一级行业
- 风格因子: 市值、价值、动量、波动、质量、成长

**风险分解**:
```
总风险² = 系统性风险² + 特异性风险²
       = ∑∑(w_i × X_ik × Cov(F) × X_jk × w_j) + ∑(w_i² × Var(ε_i))
```

**应用**:
- 计算组合风险贡献
- 行业/风格中性化
- 最优化风险预算
