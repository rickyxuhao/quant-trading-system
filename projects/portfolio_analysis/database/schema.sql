-- 持仓分析系统数据库表结构
-- 数据库: interface
-- 说明: 存储真实持仓数据、交易记录和净值快照（支持股票和基金）

-- 当前持仓表
CREATE TABLE IF NOT EXISTS positions (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    code VARCHAR(20) NOT NULL COMMENT '资产代码',
    name VARCHAR(50) COMMENT '资产名称',
    asset_type ENUM('stock', 'etf', 'lof', 'fund_oe', 'bond', 'cash') DEFAULT 'stock' COMMENT '资产类型',
    volume DECIMAL(12, 4) DEFAULT 0 COMMENT '持仓数量/份额',
    cost_price DECIMAL(12, 4) COMMENT '加权成本价',
    current_price DECIMAL(12, 4) COMMENT '当前价格/净值',
    market_value DECIMAL(15, 2) COMMENT '市值',
    sector VARCHAR(50) COMMENT '所属行业',
    fund_type VARCHAR(20) COMMENT '基金类型',
    fund_company VARCHAR(50) COMMENT '基金公司',
    nav DECIMAL(10, 4) COMMENT '最新净值',
    entry_date DATE COMMENT '首次买入日期',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_code (code),
    KEY idx_asset_type (asset_type),
    KEY idx_sector (sector),
    KEY idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='当前持仓表';

-- 交易记录表
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    trade_date DATE NOT NULL COMMENT '交易日期',
    code VARCHAR(20) NOT NULL COMMENT '资产代码',
    name VARCHAR(50) COMMENT '资产名称',
    asset_type ENUM('stock', 'etf', 'lof', 'fund_oe', 'bond', 'cash') DEFAULT 'stock' COMMENT '资产类型',
    trade_type ENUM('buy', 'sell') NOT NULL COMMENT '交易类型',
    volume DECIMAL(12, 4) NOT NULL COMMENT '交易数量/份额',
    price DECIMAL(12, 4) NOT NULL COMMENT '成交价格',
    amount DECIMAL(15, 2) COMMENT '成交金额',
    commission DECIMAL(10, 2) DEFAULT 0 COMMENT '佣金',
    stamp_tax DECIMAL(10, 2) DEFAULT 0 COMMENT '印花税',
    transfer_fee DECIMAL(10, 2) DEFAULT 0 COMMENT '过户费',
    other_fee DECIMAL(10, 2) DEFAULT 0 COMMENT '其他费用',
    fee DECIMAL(10, 2) DEFAULT 0 COMMENT '总手续费',
    strategy VARCHAR(50) COMMENT '策略名称',
    notes TEXT COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',

    KEY idx_trade_date (trade_date),
    KEY idx_code (code),
    KEY idx_code_date (code, trade_date),
    KEY idx_strategy (strategy)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易记录表';

-- 每日净值快照
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    date DATE NOT NULL COMMENT '日期',
    total_asset DECIMAL(15, 2) COMMENT '总资产',
    cash DECIMAL(15, 2) COMMENT '现金余额',
    market_value DECIMAL(15, 2) COMMENT '股票市值',
    net_value DECIMAL(12, 6) COMMENT '单位净值',
    daily_return DECIMAL(10, 6) COMMENT '日收益率',
    cumulative_return DECIMAL(10, 6) COMMENT '累计收益率',
    benchmark_return DECIMAL(10, 6) COMMENT '基准日收益率',
    notes TEXT COMMENT '备注',

    UNIQUE KEY uk_date (date),
    KEY idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日净值快照';

-- 历史持仓记录
CREATE TABLE IF NOT EXISTS position_history (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    date DATE NOT NULL COMMENT '日期',
    code VARCHAR(20) NOT NULL COMMENT '股票代码',
    name VARCHAR(50) COMMENT '股票名称',
    volume INT COMMENT '持股数量',
    cost_price DECIMAL(12, 4) COMMENT '成本价',
    close_price DECIMAL(12, 4) COMMENT '当日收盘价',
    market_value DECIMAL(15, 2) COMMENT '市值',
    pnl DECIMAL(15, 2) COMMENT '累计盈亏',
    pnl_pct DECIMAL(10, 6) COMMENT '盈亏比例',
    weight DECIMAL(8, 6) COMMENT '权重',

    UNIQUE KEY uk_date_code (date, code),
    KEY idx_date (date),
    KEY idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史持仓记录';

-- 创建视图：持仓汇总
CREATE OR REPLACE VIEW v_position_summary AS
SELECT
    p.code,
    p.name,
    p.volume,
    p.cost_price,
    p.sector,
    p.entry_date,
    ph.close_price,
    ph.market_value,
    ph.pnl,
    ph.pnl_pct,
    ph.weight
FROM positions p
LEFT JOIN position_history ph ON p.code = ph.code
    AND ph.date = (SELECT MAX(date) FROM position_history);

-- 创建视图：月度收益统计
CREATE OR REPLACE VIEW v_monthly_returns AS
SELECT
    DATE_FORMAT(date, '%Y-%m') AS month,
    (MAX(net_value) - MIN(net_value)) / MIN(net_value) AS monthly_return,
    MIN(net_value) AS start_nav,
    MAX(net_value) AS end_nav,
    COUNT(*) AS trading_days
FROM portfolio_snapshots
GROUP BY DATE_FORMAT(date, '%Y-%m')
ORDER BY month;

-- 历史持仓记录
CREATE TABLE IF NOT EXISTS position_history (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    date DATE NOT NULL COMMENT '日期',
    code VARCHAR(20) NOT NULL COMMENT '资产代码',
    name VARCHAR(50) COMMENT '资产名称',
    volume DECIMAL(12, 4) COMMENT '持股数量/份额',
    cost_price DECIMAL(12, 4) COMMENT '成本价',
    close_price DECIMAL(12, 4) COMMENT '当日收盘价',
    market_value DECIMAL(15, 2) COMMENT '市值',
    pnl DECIMAL(15, 2) COMMENT '累计盈亏',
    pnl_pct DECIMAL(10, 6) COMMENT '盈亏比例',
    weight DECIMAL(8, 6) COMMENT '权重',

    UNIQUE KEY uk_date_code (date, code),
    KEY idx_date (date),
    KEY idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史持仓记录';

-- 基金基本信息表
CREATE TABLE IF NOT EXISTS fund_info (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    code VARCHAR(20) UNIQUE NOT NULL COMMENT '基金代码',
    name VARCHAR(100) COMMENT '基金名称',
    fund_type VARCHAR(20) COMMENT '基金类型',
    company VARCHAR(50) COMMENT '基金公司',
    setup_date DATE COMMENT '成立日期',
    management_fee DECIMAL(6, 4) COMMENT '管理费率',
    custodian_fee DECIMAL(6, 4) COMMENT '托管费率',
    purchase_fee DECIMAL(6, 4) COMMENT '申购费率',
    redemption_fee DECIMAL(6, 4) COMMENT '赎回费率',
    redemption_fee_structure TEXT COMMENT '赎回费率结构JSON',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    KEY idx_code (code),
    KEY idx_fund_type (fund_type),
    KEY idx_company (company)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金基本信息表';

-- 基金净值表
CREATE TABLE IF NOT EXISTS fund_net_values (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    code VARCHAR(20) NOT NULL COMMENT '基金代码',
    name VARCHAR(50) COMMENT '基金名称',
    date DATE NOT NULL COMMENT '净值日期',
    nav DECIMAL(10, 4) COMMENT '单位净值',
    accumulated_nav DECIMAL(10, 4) COMMENT '累计净值',
    daily_return DECIMAL(8, 4) COMMENT '日涨跌幅',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_fund_date (code, date),
    KEY idx_code (code),
    KEY idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金净值表';

-- 定投计划表
CREATE TABLE IF NOT EXISTS sip_plans (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    code VARCHAR(20) NOT NULL COMMENT '基金代码',
    name VARCHAR(50) COMMENT '基金名称',
    asset_type ENUM('stock', 'etf', 'lof', 'fund_oe', 'bond', 'cash') DEFAULT 'fund_oe' COMMENT '资产类型',
    cycle ENUM('weekly', 'biweekly', 'monthly') NOT NULL COMMENT '定投周期',
    cycle_day INT COMMENT '定投日（周几/每月几号）',
    fixed_amount DECIMAL(12, 2) COMMENT '每期金额',
    start_date DATE COMMENT '开始日期',
    end_date DATE COMMENT '结束日期（可选）',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否进行中',
    total_invested DECIMAL(15, 2) DEFAULT 0 COMMENT '累计投入',
    total_shares DECIMAL(12, 4) DEFAULT 0 COMMENT '累计份额',
    notes TEXT COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    KEY idx_code (code),
    KEY idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定投计划表';

-- 定投执行记录表
CREATE TABLE IF NOT EXISTS sip_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    plan_id INT NOT NULL COMMENT '计划ID',
    execute_date DATE NOT NULL COMMENT '执行日期',
    nav DECIMAL(10, 4) COMMENT '当日净值',
    shares DECIMAL(12, 4) COMMENT '获得份额',
    amount DECIMAL(12, 2) COMMENT '投入金额',
    fee DECIMAL(10, 2) DEFAULT 0 COMMENT '申购费',
    is_auto BOOLEAN DEFAULT TRUE COMMENT '是否自动执行',
    status VARCHAR(20) DEFAULT 'success' COMMENT '执行状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    KEY idx_plan_date (plan_id, execute_date),
    KEY idx_execute_date (execute_date),
    FOREIGN KEY (plan_id) REFERENCES sip_plans(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定投执行记录表';

-- 创建视图：持仓汇总
CREATE OR REPLACE VIEW v_position_summary AS
SELECT
    p.code,
    p.name,
    p.asset_type,
    p.volume,
    p.cost_price,
    p.sector,
    p.entry_date,
    ph.close_price,
    ph.market_value,
    ph.pnl,
    ph.pnl_pct,
    ph.weight
FROM positions p
LEFT JOIN position_history ph ON p.code = ph.code
    AND ph.date = (SELECT MAX(date) FROM position_history);

-- 创建视图：月度收益统计
CREATE OR REPLACE VIEW v_monthly_returns AS
SELECT
    DATE_FORMAT(date, '%Y-%m') AS month,
    (MAX(net_value) - MIN(net_value)) / MIN(net_value) AS monthly_return,
    MIN(net_value) AS start_nav,
    MAX(net_value) AS end_nav,
    COUNT(*) AS trading_days
FROM portfolio_snapshots
GROUP BY DATE_FORMAT(date, '%Y-%m')
ORDER BY month;

-- 创建触发器：更新持仓时自动更新更新时间
DELIMITER //
CREATE TRIGGER trg_position_update_time
BEFORE UPDATE ON positions
FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END//
DELIMITER ;
