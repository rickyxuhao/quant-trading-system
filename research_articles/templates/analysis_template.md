# 论文分析报告: {title}

## 1. 论文元数据

| 项目 | 内容 |
|------|------|
| **标题** | {title} |
| **作者** | {authors} |
| **发表期刊/会议** | {venue} |
| **年份** | {year} |
| **核心贡献** | {contribution} |

---

## 2. 方法论框架

### 2.1 信号生成逻辑

#### 入场条件
{entry_signals}

#### 出场条件
{exit_signals}

#### 止损/止盈设置
{risk_signals}

---

### 2.2 特征变量列表

| 变量名 | 类型 | 描述 | 计算公式 | 数据来源 |
|--------|------|------|----------|----------|
{features_table}

---

### 2.3 模型架构

**模型类型**: {model_type}

**模型描述**: {model_description}

#### 层结构
{layer_structure}

#### 超参数配置
{hyperparameters}

#### 优化器与损失函数
- 优化器: {optimizer}
- 损失函数: {loss_function}

---

### 2.4 训练流程

**数据划分**:
- 训练集: {train_period}
- 验证集: {val_period}
- 测试集: {test_period}

**训练配置**:
{training_config}

---

### 2.5 回测设计

| 配置项 | 设置值 |
|--------|--------|
| 时间范围 | {backtest_range} |
| 再平衡频率 | {rebalance_freq} |
| 交易成本 | {transaction_cost} |
| 滑点 | {slippage} |
| 初始资金 | {initial_capital} |

---

## 3. 关键假设与局限性

### 3.1 明确声明的假设
{explicit_assumptions}

### 3.2 隐含假设
{implicit_assumptions}

### 3.3 方法论弱点
{methodology_weaknesses}

---

## 4. 中国市场适配性评估

### 4.1 T+1制度影响
{t_plus_one_impact}

### 4.2 涨跌停限制
{price_limit_impact}

### 4.3 数据可得性差异
{data_availability}

### 4.4 交易成本差异
{cost_comparison}

---

## 5. 改进建议

| 序号 | 建议标题 | 问题描述 | 改进方案 | 预期效果 | 复杂度 | 优先级 |
|------|----------|----------|----------|----------|--------|--------|
{improvements_table}

---

## 6. 框架应用建议

### 6.1 建议实现路径

```
阶段1: {stage1_task}
├── 预计工期: {stage1_duration}
├── 关键产出: {stage1_output}
└── 验收标准: {stage1_criteria}

阶段2: {stage2_task}
├── 预计工期: {stage2_duration}
├── 关键产出: {stage2_output}
└── 验收标准: {stage2_criteria}

阶段3: {stage3_task}
├── 预计工期: {stage3_duration}
├── 关键产出: {stage3_output}
└── 验收标准: {stage3_criteria}
```

### 6.2 需要的数据支持

| 数据类型 | 具体字段 | 频率 | 来源 | 优先级 |
|----------|----------|------|------|--------|
{data_requirements}

### 6.3 优先级评估

**立即实施**: {immediate_actions}

**中期规划**: {medium_term}

**长期考虑**: {long_term}

---

## 7. 关键发现摘录

{key_findings}

---

## 8. 原文局限性与未来研究方向

{limitations}

---

*报告生成时间: {generation_time}*
*解析工具版本: {parser_version}*
