-- ========================================================
-- 券商金股监控分析系统 - 数据库表结构
-- 数据库: interface
-- ========================================================

-- --------------------------------------------------------
-- 1. 券商金股推荐表 broker_gold_stock
-- 存储每月券商推荐的金股数据
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS broker_gold_stock (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    month VARCHAR(6) NOT NULL COMMENT '月份 YYYYMM',
    broker_name VARCHAR(100) COMMENT '券商名称',
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS股票代码',
    name VARCHAR(100) COMMENT '股票名称',
    industry VARCHAR(100) COMMENT '所属行业',
    analyst VARCHAR(100) COMMENT '分析师',
    logic TEXT COMMENT '推荐逻辑',
    target_price DECIMAL(16,4) COMMENT '目标价',
    previous_perf DECIMAL(10,4) COMMENT '上月涨跌幅%',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_month_broker_stock (month, broker_name, ts_code),
    INDEX idx_month (month),
    INDEX idx_ts_code (ts_code),
    INDEX idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='券商月度金股推荐';


-- --------------------------------------------------------
-- 2. 金股表现追踪表 gold_stock_performance
-- 追踪金股从推荐日到当前的表现
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold_stock_performance (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    month VARCHAR(6) NOT NULL COMMENT '推荐月份',
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '股票名称',
    recommend_date VARCHAR(8) COMMENT '推荐日期',
    end_date VARCHAR(8) COMMENT '统计截止日期',

    -- 价格表现
    recommend_price DECIMAL(16,4) COMMENT '推荐日收盘价',
    current_price DECIMAL(16,4) COMMENT '当前价格',
    max_price DECIMAL(16,4) COMMENT '月内最高价',
    min_price DECIMAL(16,4) COMMENT '月内最低价',

    -- 收益统计
    total_return DECIMAL(10,4) COMMENT '累计收益率%',
    excess_return DECIMAL(10,4) COMMENT '超额收益%(相对沪深300)',
    max_drawdown DECIMAL(10,4) COMMENT '最大回撤%',

    -- 市场数据
    avg_volume DECIMAL(20,4) COMMENT '日均成交额(万元)',
    volatility DECIMAL(10,4) COMMENT '波动率',

    -- 技术信号
    technical_score INT COMMENT '技术评分(0-100)',
    technical_signals JSON COMMENT '技术信号详情',

    -- 扩展字段
    ext_data JSON COMMENT '扩展数据字段(预留)',

    status ENUM('holding', 'closed', 'watching') DEFAULT 'watching' COMMENT '状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_month_code (month, ts_code),
    INDEX idx_status (status),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='金股表现追踪';


-- --------------------------------------------------------
-- 3. 财务指标分析表 financial_analysis
-- 存储股票的财务分析结果
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS financial_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '股票名称',
    report_date VARCHAR(8) COMMENT '报告期',

    -- 估值指标
    pe_ttm DECIMAL(16,4) COMMENT 'PE TTM',
    pb DECIMAL(16,4) COMMENT 'PB',
    ps_ttm DECIMAL(16,4) COMMENT 'PS TTM',
    peg DECIMAL(16,4) COMMENT 'PEG',

    -- 盈利能力
    roe DECIMAL(10,4) COMMENT 'ROE%',
    roa DECIMAL(10,4) COMMENT 'ROA%',
    gross_margin DECIMAL(10,4) COMMENT '毛利率%',
    net_margin DECIMAL(10,4) COMMENT '净利率%',

    -- 成长性
    revenue_growth DECIMAL(10,4) COMMENT '营收增长率%',
    profit_growth DECIMAL(10,4) COMMENT '净利润增长率%',

    -- 财务健康
    debt_ratio DECIMAL(10,4) COMMENT '资产负债率%',
    current_ratio DECIMAL(10,4) COMMENT '流动比率',

    -- 综合评分
    financial_score INT COMMENT '财务评分(0-100)',
    quality_tag VARCHAR(50) COMMENT '质量标签(优/良/中/差)',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_code_date (ts_code, report_date),
    INDEX idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务指标分析';


-- --------------------------------------------------------
-- 4. 量化因子评分表 quant_factor_score
-- 存储多因子模型评分结果
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS quant_factor_score (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '股票名称',
    trade_date VARCHAR(8) COMMENT '交易日',

    -- 估值因子
    value_factor DECIMAL(10,4) COMMENT '估值因子得分',

    -- 质量因子
    quality_factor DECIMAL(10,4) COMMENT '质量因子得分',

    -- 成长因子
    growth_factor DECIMAL(10,4) COMMENT '成长因子得分',

    -- 动量因子
    momentum_factor DECIMAL(10,4) COMMENT '动量因子得分',

    -- 波动率因子
    volatility_factor DECIMAL(10,4) COMMENT '波动率因子得分',

    -- 流动性因子
    liquidity_factor DECIMAL(10,4) COMMENT '流动性因子得分',

    -- 综合评分
    total_score DECIMAL(10,4) COMMENT '综合因子得分',
    rank_in_industry INT COMMENT '行业内排名',
    rank_in_market INT COMMENT '全市场排名',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_code_date (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_total_score (total_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='量化因子评分';


-- --------------------------------------------------------
-- 5. 异动检测记录表 stock_anomaly
-- 记录股票异动检测事件
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_anomaly (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '股票名称',
    detect_date VARCHAR(8) COMMENT '检测日期',

    -- 异动类型: price_spike, volume_surge, limit_up, limit_down,
    --          technical_breakout, news_driven
    anomaly_type VARCHAR(50) COMMENT '异动类型',
    severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium' COMMENT '严重程度',

    -- 异动数据
    trigger_price DECIMAL(16,4) COMMENT '触发价格',
    price_change DECIMAL(10,4) COMMENT '涨跌幅%',
    volume_ratio DECIMAL(10,4) COMMENT '量比',

    -- 分析结果
    news_collected TINYINT DEFAULT 0 COMMENT '是否收集新闻',
    news_analyzed TINYINT DEFAULT 0 COMMENT '是否AI分析',
    ai_analysis TEXT COMMENT 'AI分析结果',
    ai_sentiment VARCHAR(20) COMMENT 'AI情感判断',

    -- 投资建议
    recommendation VARCHAR(50) COMMENT '建议动作',
    confidence DECIMAL(5,4) COMMENT '置信度',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_ts_code_date (ts_code, detect_date),
    INDEX idx_anomaly_type (anomaly_type),
    INDEX idx_detect_date (detect_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票异动检测记录';


-- --------------------------------------------------------
-- 6. 新闻舆情表 news_sentiment
-- 存储股票相关新闻及AI分析结果
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_sentiment (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '股票名称',
    news_date VARCHAR(8) COMMENT '新闻日期',
    title VARCHAR(500) COMMENT '标题',
    content TEXT COMMENT '内容',
    source VARCHAR(100) COMMENT '来源',
    url VARCHAR(500) COMMENT '链接',

    -- 情感分析
    sentiment_score DECIMAL(5,4) COMMENT '情感得分(-1到1)',
    sentiment_label VARCHAR(20) COMMENT '情感标签',

    -- AI分析
    ai_summary TEXT COMMENT 'AI摘要',
    key_points JSON COMMENT '关键要点',
    impact_assessment VARCHAR(50) COMMENT '影响评估',

    -- 关联性
    relevance_score DECIMAL(5,4) COMMENT '相关度得分',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_ts_code_date (ts_code, news_date),
    INDEX idx_news_date (news_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='新闻舆情数据';


-- --------------------------------------------------------
-- 7. 晨间报告表 morning_report
-- 存储每日生成的晨间投资报告
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS morning_report (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    report_date VARCHAR(8) COMMENT '报告日期',

    -- 报告元数据
    gold_stock_count INT COMMENT '监控金股数量',
    anomaly_count INT COMMENT '异动股票数量',
    buy_signals INT COMMENT '买入信号数量',
    sell_signals INT COMMENT '卖出信号数量',

    -- 报告内容
    summary TEXT COMMENT '执行摘要',
    highlight_stocks JSON COMMENT '重点股票',
    market_outlook TEXT COMMENT '市场展望',

    -- 策略信号(预留扩展)
    strategy_signals JSON COMMENT '策略信号(预留)',

    -- 文件路径
    markdown_path VARCHAR(500) COMMENT 'Markdown文件路径',
    pdf_path VARCHAR(500) COMMENT 'PDF文件路径',

    -- 发送记录
    sent_at TIMESTAMP NULL COMMENT '发送时间',
    send_status VARCHAR(20) COMMENT '发送状态',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_report_date (report_date),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='晨间投资报告';


-- --------------------------------------------------------
-- 8. 系统配置表 broker_gold_stock_config
-- 存储系统配置参数
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS broker_gold_stock_config (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    config_key VARCHAR(100) NOT NULL COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    config_type VARCHAR(20) DEFAULT 'string' COMMENT '值类型: string, int, float, json',
    description VARCHAR(500) COMMENT '配置说明',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';


-- --------------------------------------------------------
-- 初始化配置数据
-- --------------------------------------------------------
INSERT INTO broker_gold_stock_config (config_key, config_value, config_type, description) VALUES
('analysis.weight.technical', '0.30', 'float', '技术分析权重'),
('analysis.weight.financial', '0.30', 'float', '财务分析权重'),
('analysis.weight.quant', '0.30', 'float', '量化因子权重'),
('analysis.weight.sentiment', '0.10', 'float', '市场情绪权重'),
('anomaly.threshold.price_change', '5.0', 'float', '价格异动阈值(%)'),
('anomaly.threshold.volume_ratio', '2.0', 'float', '成交量异动阈值(倍)'),
('report.top_stocks_limit', '20', 'int', '报告展示金股数量'),
('report.generate_time', '08:00', 'string', '报告生成时间')
ON DUPLICATE KEY UPDATE config_value = VALUES(config_value);
