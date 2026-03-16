# Streamlit可视化Dashboard

量化交易系统的交互式可视化分析平台，提供策略绩效分析、交易明细展示、模型诊断和参数调优功能。

## 功能特性

### 1. 策略绩效页面 (Performance)
- 累计收益曲线（支持对数刻度）
- 回撤曲线（自动标注最大回撤区间）
- 月度收益热力图
- 详细绩效指标展示（收益、风险、风险调整收益、交易统计）
- 滚动指标分析（滚动波动率、滚动夏普比率）
- 收益率分布分析

### 2. 交易明细页面 (Trades)
- 交易统计概览（胜率、盈亏比、总盈亏）
- 个股盈亏分布分析
- 盈亏分布直方图
- 连续盈亏分析
- 持仓周期分析
- 完整交易明细表格

### 3. 模型诊断页面 (Model Diagnosis)
- 预测准确率趋势
- 特征重要性分析
- 特征稳定性时序
- IC（信息系数）滚动分析
- IR（信息比率）分析
- 分位数收益单调性检验
- 多空组合表现
- 预测vs实际收益散点图

### 4. 参数调优页面 (Optimization)
- 交互式参数调整（滑块控件）
- 多参数组合对比
- 雷达图多维度对比
- 参数敏感性分析
- 参数-指标相关性热图
- 对比结果导出（CSV）

## 项目结构

```
visualization/
├── __init__.py                 # 包初始化
├── app.py                      # Streamlit主应用入口
├── config.py                   # 可视化配置
├── state_manager.py            # Session state管理
├── backtest_config.py          # 回测配置模块
├── components/                 # 可复用组件
│   ├── __init__.py
│   ├── metric_cards.py         # 指标卡片组件
│   ├── charts.py               # Plotly图表封装
│   └── tables.py               # 数据表格组件
├── pages/                      # 多页面模块
│   ├── __init__.py
│   ├── performance.py          # 策略绩效页
│   ├── trades.py               # 交易明细页
│   ├── model_diagnosis.py      # 模型分析页
│   └── optimization.py         # 参数调优页
└── utils/                      # 工具函数
    ├── __init__.py
    ├── data_loader.py          # 数据加载
    └── formatters.py           # 格式化工具
```

## 快速开始

### 1. 安装依赖

确保已安装streamlit和plotly：

```bash
# 使用poetry
poetry add streamlit plotly

# 或使用pip
pip install streamlit plotly
```

### 2. 启动Dashboard

```bash
# 从项目根目录
poetry run streamlit run projects/quant_trading/visualization/app.py

# 或指定端口
poetry run streamlit run projects/quant_trading/visualization/app.py --server.port 8502
```

### 3. 访问Dashboard

打开浏览器访问：http://localhost:8501

## 使用说明

### 侧边栏配置

1. **策略选择**: 选择要分析的交易策略
2. **时间范围**: 设置回测的开始和结束日期
3. **资金配置**: 设置初始资金（万元）
4. **基准对比**: 选择对比基准（沪深300/中证500/上证指数）
5. **运行回测**: 点击按钮执行回测

### 页面导航

- **策略绩效**: 查看策略的整体表现和关键指标
- **交易明细**: 分析每笔交易的盈亏情况
- **模型诊断**: 分析机器学习模型的预测性能（仅ML策略）
- **参数调优**: 调整参数并对比不同组合的效果

## 与回测引擎集成

当前实现使用模拟数据进行演示。要连接实际回测引擎，需要修改`app.py`中的`run_backtest()`函数：

```python
def run_backtest():
    """执行回测"""
    # 获取配置
    start_date = StateManager.get('start_date')
    end_date = StateManager.get('end_date')
    strategy = StateManager.get('selected_strategy')

    # 创建回测配置
    from projects.quant_trading.backtest.engine import BacktestConfig, BacktestEngine

    config = BacktestConfig(
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.min.time()),
        initial_capital=StateManager.get('initial_capital'),
        benchmark=viz_config.default_benchmark
    )

    # 创建策略实例
    strategy_instance = create_strategy(strategy)

    # 运行回测
    engine = BacktestEngine(config, strategy_instance)
    results = engine.run()

    # 保存结果
    StateManager.set('backtest_results', results)
```

## 配置说明

### 修改默认配置

编辑`config.py`中的`VizConfig`类：

```python
@dataclass
class VizConfig:
    page_title: str = "自定义标题"
    default_initial_capital: float = 500_000.0  # 默认50万
    default_benchmark: str = "000905.SH"  # 中证500
```

### 添加新策略

在`config.py`的`__post_init__`方法中添加：

```python
self.available_strategies.append({
    "id": "new_strategy",
    "name": "新策略",
    "type": "technical"
})
```

## 性能优化

1. **数据缓存**: 使用`@st.cache_data`装饰器缓存回测结果
2. **懒加载**: 页面按需加载，避免一次性加载所有数据
3. **图表优化**: 限制同时显示的图表数量

## 扩展开发

### 添加新页面

1. 在`pages/`目录下创建新文件，如`new_page.py`
2. 实现`render_new_page()`函数
3. 在`app.py`的`main()`函数中添加页面路由

### 添加新图表

在`components/charts.py`中添加新的图表函数：

```python
def create_custom_chart(data: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    # 自定义图表逻辑
    return fig
```

## 注意事项

1. 当前版本使用模拟数据，生产环境需连接实际回测引擎
2. 大量数据可能导致页面响应变慢，建议限制回测时间范围
3. 参数调优页面的对比结果保存在session中，刷新页面会丢失

## 后续开发计划

### Phase 4.2: 高级功能
- [ ] 多策略对比
- [ ] 实时信号监控
- [ ] 组合优化器
- [ ] 报告导出（PDF/Excel）

### Phase 4.3: 实时交易集成
- [ ] 实盘信号展示
- [ ] 持仓同步
- [ ] 风险预警实时推送

## License

MIT License
