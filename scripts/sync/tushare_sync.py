#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare 数据同步脚本 - PostgreSQL 版本
支持增量/全量同步，含错误处理、日志和 UPSERT 功能

使用方法:
    python scripts/sync/tushare_sync.py --table stock_basic --mode full
    python scripts/sync/tushare_sync.py --table daily --mode incremental --start-date 20240101
    python scripts/sync/tushare_sync.py --all --mode incremental
"""

import os
import sys
import argparse
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from contextlib import contextmanager

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 尝试导入 Tushare 客户端
try:
    from core.data_access.tushare.client import get_tushare_client
except ImportError:
    print("⚠️ 警告: 无法导入 core.data_access.tushare.client，将使用内置 Tushare 客户端")
    get_tushare_client = None


# ========================================================
# 配置和日志
# ========================================================

@dataclass
class SyncConfig:
    """同步配置"""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "tushare_biz"
    db_user: str = "postgres"
    db_password: str = ""
    tushare_token: str = ""
    batch_size: int = 1000
    max_retries: int = 3
    retry_delay: int = 5
    rate_limit_per_minute: int = 500
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> 'SyncConfig':
        """从环境变量加载配置"""
        return cls(
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_name=os.getenv("DB_NAME_TUSHARE", "tushare_biz"),
            db_user=os.getenv("DB_USER", "postgres"),
            db_password=os.getenv("DB_PASSWORD", ""),
            tushare_token=os.getenv("TUSHARE_TOKEN", ""),
            batch_size=int(os.getenv("SYNC_BATCH_SIZE", "1000")),
            max_retries=int(os.getenv("SYNC_MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("SYNC_RETRY_DELAY", "5")),
            rate_limit_per_minute=int(os.getenv("TUSHARE_RATE_LIMIT", "500")),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """配置日志"""
    logger = logging.getLogger("tushare_sync")
    logger.setLevel(getattr(logging, log_level.upper()))

    # 清除现有处理器
    logger.handlers.clear()

    # 格式化器
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ========================================================
# 数据库连接管理
# ========================================================

class DatabaseManager:
    """PostgreSQL 数据库管理器"""

    def __init__(self, config: SyncConfig):
        self.config = config
        self._pool = None
        self.logger = logging.getLogger("tushare_sync")

    def get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            database=self.config.db_name,
            user=self.config.db_user,
            password=self.config.db_password
        )

    @contextmanager
    def connection(self):
        """连接上下文管理器"""
        conn = None
        try:
            conn = self.get_connection()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    def execute(self, sql: str, params: tuple = None) -> int:
        """执行 SQL 语句"""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount

    def fetchone(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """查询单条记录"""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                if row and cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                return None

    def fetchall(self, sql: str, params: tuple = None) -> List[Dict]:
        """查询所有记录"""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                if rows and cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in rows]
                return []

    def upsert(self, table: str, columns: List[str], rows: List[List],
               unique_columns: List[str], update_columns: List[str] = None) -> Dict[str, int]:
        """
        UPSERT 操作 - PostgreSQL 使用 ON CONFLICT DO UPDATE

        Args:
            table: 表名
            columns: 列名列表
            rows: 数据行列表
            unique_columns: 唯一键列名
            update_columns: 冲突时需要更新的列，None则更新所有非唯一列

        Returns:
            统计信息字典
        """
        if not rows:
            return {"inserted": 0, "updated": 0, "total": 0}

        # 确定需要更新的列
        if update_columns is None:
            update_columns = [col for col in columns if col not in unique_columns]

        # 构建 INSERT 语句
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))

        sql = f"INSERT INTO {table} ({columns_str}) VALUES %s"

        # 构建 ON CONFLICT 子句
        unique_cols_str = ', '.join(unique_columns)

        if update_columns:
            updates = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            sql += f" ON CONFLICT ({unique_cols_str}) DO UPDATE SET {updates}"
        else:
            sql += f" ON CONFLICT ({unique_cols_str}) DO NOTHING"

        total_affected = 0
        batch_size = self.config.batch_size

        with self.connection() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    # 使用 execute_values 进行批量插入
                    execute_values(cur, sql, batch, page_size=batch_size)
                    total_affected += cur.rowcount

        return {
            "inserted": len(rows),
            "updated": total_affected,
            "total": len(rows)
        }

    def get_max_date(self, table: str, date_column: str = 'trade_date',
                     where_clause: str = None) -> Optional[str]:
        """获取表中最大日期"""
        sql = f"SELECT MAX({date_column}) as max_date FROM {table}"
        if where_clause:
            sql += f" WHERE {where_clause}"

        result = self.fetchone(sql)
        return result['max_date'] if result and result['max_date'] else None

    def get_count(self, table: str, where_clause: str = None) -> int:
        """获取表记录数"""
        sql = f"SELECT COUNT(*) as cnt FROM {table}"
        if where_clause:
            sql += f" WHERE {where_clause}"

        result = self.fetchone(sql)
        return result['cnt'] if result else 0


# ========================================================
# 速率限制器
# ========================================================

class RateLimiter:
    """API 速率限制器"""

    def __init__(self, max_requests_per_minute: int = 500):
        self.max_requests = max_requests_per_minute
        self.interval = 60.0 / max_requests_per_minute
        self.last_request_time = 0
        self.logger = logging.getLogger("tushare_sync")

    def wait_if_needed(self):
        """根据需要等待以符合速率限制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.interval:
            sleep_time = self.interval - elapsed
            time.sleep(sleep_time)

        self.last_request_time = time.time()


# ========================================================
# Tushare 客户端包装
# ========================================================

class TushareSyncClient:
    """Tushare 同步客户端"""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.rate_limiter = RateLimiter(config.rate_limit_per_minute)
        self.logger = logging.getLogger("tushare_sync")
        self._pro = None

        # 尝试使用项目内置客户端
        if get_tushare_client:
            try:
                client = get_tushare_client()
                self._pro = client.pro
                self.logger.info("✅ 使用项目内置 Tushare 客户端")
                return
            except Exception as e:
                self.logger.warning(f"⚠️ 内置客户端初始化失败: {e}")

        # 使用独立 Tushare 连接
        try:
            import tushare as ts
            if not config.tushare_token:
                raise ValueError("TUSHARE_TOKEN 环境变量未设置")
            ts.set_token(config.tushare_token)
            self._pro = ts.pro_api()
            self.logger.info("✅ Tushare 客户端初始化成功")
        except Exception as e:
            self.logger.error(f"❌ Tushare 客户端初始化失败: {e}")
            raise

    def query(self, api_name: str, fields: str = None, **kwargs) -> pd.DataFrame:
        """查询 Tushare API，带重试机制"""
        for attempt in range(self.config.max_retries):
            try:
                self.rate_limiter.wait_if_needed()

                params = kwargs.copy()
                if fields:
                    params['fields'] = fields

                df = self._pro.query(api_name, **params)
                return df if df is not None else pd.DataFrame()

            except Exception as e:
                self.logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise

        return pd.DataFrame()


# ========================================================
# 同步任务定义
# ========================================================

# 表配置映射
TABLE_CONFIGS = {
    # 基础数据表
    "stock_basic": {
        "api": "stock_basic",
        "table": "t_stock_basic",
        "columns": ['ts_code', 'symbol', 'name', 'area', 'industry', 'fullname',
                   'enname', 'cnspell', 'market', 'exchange', 'curr_type',
                   'list_status', 'list_date', 'delist_date', 'is_hs',
                   'act_name', 'act_ent_type'],
        "unique_columns": ['ts_code'],
        "update_columns": ['symbol', 'name', 'area', 'industry', 'fullname',
                          'enname', 'cnspell', 'market', 'exchange', 'curr_type',
                          'list_status', 'list_date', 'delist_date', 'is_hs',
                          'act_name', 'act_ent_type'],
        "sync_type": "full",
        "fetch_params": {"list_status": ""}  # 空字符串表示获取全部
    },
    "trade_cal": {
        "api": "trade_cal",
        "table": "t_stock_tradedate",
        "columns": ['exchange', 'cal_date', 'is_open', 'pretrade_date'],
        "unique_columns": ['exchange', 'cal_date'],
        "sync_type": "full",
        "date_range": True
    },
    "namechange": {
        "api": "namechange",
        "table": "t_stock_name_history",
        "columns": ['ts_code', 'name', 'start_date', 'end_date', 'ann_date'],
        "unique_columns": ['ts_code', 'start_date'],
        "sync_type": "incremental"
    },
    "hs_const": {
        "api": "hs_const",
        "table": "t_stock_hs_const",
        "columns": ['ts_code', 'hs_type', 'in_date', 'out_date', 'is_new'],
        "unique_columns": ['ts_code', 'hs_type'],
        "sync_type": "full"
    },
    "new_share": {
        "api": "new_share",
        "table": "t_stock_ipo",
        "columns": ['ts_code', 'sub_code', 'name', 'ipo_date', 'issue_date',
                   'amount', 'market_amount', 'price', 'pe', 'limit_amount',
                   'funds', 'ballot'],
        "unique_columns": ['ts_code'],
        "sync_type": "incremental"
    },
    "stock_company": {
        "api": "stock_company",
        "table": "t_stock_company",
        "columns": ['ts_code', 'exchange', 'chairman', 'manager', 'secretary',
                   'reg_capital', 'setup_date', 'province', 'city', 'introduction',
                   'website', 'email', 'office', 'employees', 'main_business',
                   'business_scope'],
        "unique_columns": ['ts_code'],
        "update_columns": ['exchange', 'chairman', 'manager', 'secretary',
                          'reg_capital', 'setup_date', 'province', 'city', 'introduction',
                          'website', 'email', 'office', 'employees', 'main_business',
                          'business_scope'],
        "sync_type": "full"
    },

    # 行情数据表
    "daily": {
        "api": "daily",
        "table": "t_stock_dailymarketdata",
        "columns": ['ts_code', 'trade_date', 'open', 'high', 'low', 'close',
                   'pre_close', 'change', 'pct_chg', 'vol', 'amount'],
        "unique_columns": ['ts_code', 'trade_date'],
        "update_columns": ['open', 'high', 'low', 'close', 'pre_close',
                          'change', 'pct_chg', 'vol', 'amount'],
        "sync_type": "incremental",
        "date_column": "trade_date"
    },
    "adj_factor": {
        "api": "adj_factor",
        "table": "t_stock_adjfactor",
        "columns": ['ts_code', 'trade_date', 'adj_factor'],
        "unique_columns": ['ts_code', 'trade_date'],
        "sync_type": "incremental",
        "date_column": "trade_date"
    },
    "daily_basic": {
        "api": "daily_basic",
        "table": "t_stock_daily_basic",
        "columns": ['ts_code', 'trade_date', 'close', 'turnover_rate',
                   'turnover_rate_f', 'volume_ratio', 'pe', 'pe_ttm', 'pb',
                   'ps', 'ps_ttm', 'dv_ratio', 'dv_ttm', 'total_share',
                   'float_share', 'free_share', 'total_mv', 'circ_mv'],
        "unique_columns": ['ts_code', 'trade_date'],
        "sync_type": "incremental",
        "date_column": "trade_date"
    },
    "stock_st": {
        "api": "stock_st",
        "table": "t_stock_st_list",
        "columns": ['ts_code', 'name', 'in_date', 'out_date', 'is_new'],
        "unique_columns": ['ts_code', 'in_date'],
        "sync_type": "incremental",
        "date_column": "in_date"
    },
    "limit_list": {
        "api": "limit_list",
        "table": "t_stock_dailylimitprice",
        "columns": ['ts_code', 'trade_date', 'name', 'close', 'pct_chg',
                   'amp', 'up_limit', 'down_limit'],
        "unique_columns": ['ts_code', 'trade_date'],
        "sync_type": "incremental",
        "date_column": "trade_date"
    },
    "moneyflow": {
        "api": "moneyflow",
        "table": "t_stock_moneyflow",
        "columns": ['ts_code', 'trade_date', 'buy_sm_vol', 'buy_sm_amount',
                   'sell_sm_vol', 'sell_sm_amount', 'buy_md_vol', 'buy_md_amount',
                   'sell_md_vol', 'sell_md_amount', 'buy_lg_vol', 'buy_lg_amount',
                   'sell_lg_vol', 'sell_lg_amount', 'buy_elg_vol', 'buy_elg_amount'],
        "unique_columns": ['ts_code', 'trade_date'],
        "sync_type": "incremental",
        "date_column": "trade_date"
    },
    "moneyflow_hsgt": {
        "api": "moneyflow_hsgt",
        "table": "t_stock_moneyflow_market",
        "columns": ['trade_date', 'ggt_ss', 'ggt_sz', 'hgt', 'sgt',
                   'north_money', 'south_money'],
        "unique_columns": ['trade_date'],
        "sync_type": "incremental",
        "date_column": "trade_date"
    },

    # 财务数据表 - 利润表
    "income": {
        "api": "income",
        "table": "t_stock_income",
        "columns": ['ts_code', 'ann_date', 'f_ann_date', 'end_date', 'comp_type',
                   'basic_eps', 'diluted_eps', 'total_revenue', 'revenue',
                   'int_income', 'prem_earned', 'comm_income', 'n_commis_income',
                   'n_oth_income', 'n_oth_b_income', 'prem_income', 'out_prem',
                   'une_prem_reser', 'reins_income', 'n_sec_tb_income',
                   'n_sec_uw_income', 'n_asset_mg_income', 'oth_b_income',
                   'fv_value_chg_gain', 'invest_income', 'a_j_income',
                   'assets_dispos_income', 'total_cogs', 'operate_exp',
                   'int_exp', 'comm_exp', 'prem_refund', 'compens_payout',
                   'reser_insur_liab', 'policy_div_payt', 'reinsur_exp',
                   'operate_taxes', 'sale_exp', 'admin_exp', 'finan_exp',
                   'assets_impair_loss', 'credit_impair_loss', 'oth_loss',
                   'net_exp_other_business', 'operate_profit', 'noperate_income',
                   'noperate_exp', 'nca_disploss', 'total_profit', 'income_tax',
                   'n_income', 'n_income_attr_p', 'minority_gain',
                   'oth_compr_income', 't_compr_income', 'compr_inc_attr_p',
                   'compr_inc_attr_m_s'],
        "unique_columns": ['ts_code', 'end_date', 'f_ann_date'],
        "sync_type": "incremental",
        "date_column": "end_date",
        "ts_code_required": True
    },

    # 财务数据表 - 资产负债表
    "balancesheet": {
        "api": "balancesheet",
        "table": "t_stock_balancesheet",
        "columns": ['ts_code', 'ann_date', 'f_ann_date', 'end_date', 'comp_type',
                   'total_share', 'cap_rese', 'undistr_porfit', 'surplus_rese',
                   'special_rese', 'money_cap', 'trad_asset', 'notes_receiv',
                   'accounts_receiv', 'oth_receiv', 'prepayment', 'div_receiv',
                   'int_receiv', 'inventories', 'amor_exp', 'nca_within_1y',
                   'sett_rsrv', 'loanto_oth_bank_fi', 'premium_receiv',
                   'reinsur_receiv', 'reinsur_res_receiv', 'pur_resale_fa',
                   'oth_cur_assets', 'total_cur_assets', 'fa_avail_for_sale',
                   'htm_invest', 'lt_eqt_invest', 'invest_real_estate',
                   'time_deposits', 'oth_assets', 'lt_rec', 'fix_assets',
                   'cip', 'const_materials', 'fixed_assets_disp',
                   'produc_bio_assets', 'oil_and_gas_assets', 'intan_assets',
                   'r_and_d', 'goodwill', 'lt_amor_exp', 'defer_tax_assets',
                   'decr_in_disbur', 'oth_nca', 'total_nca', 'cash_reser_cb',
                   'depos_in_oth_bfi', 'prec_metals', 'deriv_assets',
                   'total_assets', 'c_borr_from_oth_fi', 'notes_payable',
                   'acct_payable', 'adv_receipts', 'sold_for_repur_fa',
                   'comm_payable', 'payroll_payable', 'taxes_payable',
                   'int_payable', 'div_payable', 'oth_payable', 'acc_exp',
                   'deferred_inc', 'st_bonds_payable', 'payable_to_reinsurer',
                   'rsrv_insur_cont', 'acting_trading_sec', 'acting_uw_sec',
                   'non_cur_liab_due_1y', 'oth_cur_liab', 'total_cur_liab',
                   'bonds_payable', 'lt_payable', 'specific_payables',
                   'estimated_liab', 'defer_tax_liab', 'defer_inc_non_cur_liab',
                   'oth_ncl', 'total_ncl', 'depos_oth_bfi', 'deriv_liab',
                   'depos_fr_non_bank', 'loan_oth_bank', 'trading_fl',
                   'notes_payable_1', 'int_payable_1', 'div_payable_1',
                   'oth_payable_1', 'acc_exp_1', 'total_liab', 'rec_dep_invests',
                   'total_equity', 'minority_int', 'total_hldr_eqy_exc_min_int',
                   'total_hldr_eqy_inc_min_int', 'total_liab_hldr_eqy',
                   'lt_payroll_payable', 'oth_comp_income', 'oth_eqt_tools',
                   'oth_eqt_tools_p_shr', 'lending_funds', 'acc_receivable',
                   'st_fin_payable', 'payables', 'hfs_assets', 'hfs_sales',
                   'update_flag'],
        "unique_columns": ['ts_code', 'end_date', 'f_ann_date'],
        "sync_type": "incremental",
        "date_column": "end_date",
        "ts_code_required": True
    },

    # 财务数据表 - 现金流量表
    "cashflow": {
        "api": "cashflow",
        "table": "t_stock_cashflow",
        "columns": ['ts_code', 'ann_date', 'f_ann_date', 'end_date', 'comp_type',
                   'c_cash_equ_end_period', 'n_cashflow_act', 'c_recp_sell_goods',
                   'n_depos_incr_fi', 'n_incr_loans_cb', 'n_inc_borr_oth_fi',
                   'prem_fr_orig_contr', 'n_incr_insured_dep', 'n_reinsur_prem',
                   'n_incr_disp_tfa', 'ifc_cash_incr', 'n_incr_disp_faas',
                   'n_incr_loans_oth_bank', 'n_cap_incr_repur',
                   'c_fr_oth_operate_a', 'c_inf_fr_operate_a', 'c_paid_goods_s',
                   'c_paid_to_for_empl', 'c_paid_for_taxes', 'n_incr_clt_loan_adv',
                   'n_incr_dep_cbob', 'c_pay_claims_orig_inco', 'pay_handling_chrg',
                   'pay_comm_insur_plcy', 'oth_cash_pay_oper_act', 'st_cash_out_act',
                   'n_cashflow_inv_act', 'c_recp_disp_withdrwl_invest',
                   'c_recp_return_invest', 'n_recp_disp_fiolta', 'n_recp_disp_sobu',
                   'stot_inflows_inv_act', 'c_pay_acq_const_fiolta', 'c_paid_invest',
                   'n_disp_subs_oth_biz', 'oth_pay_ral_inv_act', 'n_incr_pledge_loan',
                   'stot_out_inv_act', 'n_recp_borrow_oth', 'n_recp_borr_from_cb',
                   'proc_issue_bonds', 'oth_cash_recp_ral_fnc_act',
                   'stot_cash_inflow_fnc_act', 'free_cashflow', 'c_prepay_amt_borr',
                   'c_pay_dist_dcpint_profits', 'c_pay_debts', 'stot_cashout_fnc_act',
                   'n_incr_cash_equ'],
        "unique_columns": ['ts_code', 'end_date', 'f_ann_date'],
        "sync_type": "incremental",
        "date_column": "end_date",
        "ts_code_required": True
    },

    # 财务指标数据
    "fina_indicator": {
        "api": "fina_indicator",
        "table": "t_stock_fina_indicator",
        "columns": ['ts_code', 'ann_date', 'end_date', 'roe', 'roe_diluted',
                   'roe_avg', 'roa', 'roa_yearly', 'sales_margin', 'net_profit_margin',
                   'gross_profit_margin', 'sales_to_admin_ratio', 'sales_to_sale_ratio',
                   'asset_turnover', 'ca_turnover', 'fa_turnover', 'current_ratio',
                   'quick_ratio', 'cash_ratio', 'inv_days', 'ar_days', 'debt_to_assets',
                   'assets_to_eqt', 'debt_to_eqt', 'netdebt_to_eqt', 'ocf_to_shortdebt',
                   'ocf_to_debt', 'ocf_to_interest', 'profit_to_op', 'basic_eps_yoy',
                   'dt_eps_yoy', 'cfps_yoy', 'op_yoy', 'ebt_yoy', 'netprofit_yoy',
                   'dt_netprofit_yoy', 'roe_yoy', 'bps_yoy', 'assets_yoy', 'eqt_yoy',
                   'tr_yoy', 'or_yoy', 'q_sales_yoy', 'q_op_qoq', 'equity_yoy'],
        "unique_columns": ['ts_code', 'end_date'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 财务审计意见
    "fina_audit": {
        "api": "fina_audit",
        "table": "t_stock_fina_audit",
        "columns": ['ts_code', 'ann_date', 'end_date', 'audit_result',
                   'audit_fees', 'audit_agency', 'sign_account'],
        "unique_columns": ['ts_code', 'end_date'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 主营业务构成
    "fina_mainbz": {
        "api": "fina_mainbz",
        "table": "t_stock_fina_mainbz",
        "columns": ['ts_code', 'end_date', 'bz_item', 'bz_sales',
                   'bz_profit', 'bz_cost', 'curr_type', 'update_flag'],
        "unique_columns": ['ts_code', 'end_date', 'bz_item'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 业绩预告
    "forecast": {
        "api": "forecast",
        "table": "t_stock_forecast",
        "columns": ['ts_code', 'ann_date', 'end_date', 'type', 'p_change_min',
                   'p_change_max', 'net_profit_min', 'net_profit_max',
                   'last_parent_net', 'first_ann_date', 'summary', 'change_reason'],
        "unique_columns": ['ts_code', 'end_date'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 业绩快报
    "express": {
        "api": "express",
        "table": "t_stock_express",
        "columns": ['ts_code', 'ann_date', 'end_date', 'revenue', 'operate_profit',
                   'total_profit', 'n_income', 'total_assets', 'total_hldr_eqy_exc_min_int',
                   'diluted_eps', 'dps', 'yoy_sales', 'yoy_op', 'yoy_tp', 'yoy_netprofit',
                   'growth_assets', 'yoy_equity', 'growth_bps', 'or_last_year',
                   'op_last_year', 'tp_last_year', 'np_last_year', 'assets_last_year',
                   'equity_last_year', 'bps_last_year', 'update_flag'],
        "unique_columns": ['ts_code', 'end_date'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 分红送股
    "dividend": {
        "api": "dividend",
        "table": "t_stock_dividend",
        "columns": ['ts_code', 'end_date', 'ann_date', 'div_proc', 'stk_div',
                   'stk_bo_rate', 'stk_co_rate', 'cash_div', 'cash_div_tax',
                   'record_date', 'ex_date', 'pay_date', 'div_listdate', 'imp_ann_date',
                   'base_date', 'base_share'],
        "unique_columns": ['ts_code', 'end_date'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 前十大股东
    "top10_holders": {
        "api": "top10_holders",
        "table": "t_stock_top10_holders",
        "columns": ['ts_code', 'ann_date', 'end_date', 'holder_name',
                   'hold_amount', 'hold_ratio', 'hold_change'],
        "unique_columns": ['ts_code', 'end_date', 'holder_name'],
        "sync_type": "incremental",
        "date_column": "end_date",
        "ts_code_required": True
    },

    # 前十大流通股东
    "top10_fh": {
        "api": "top10_fh",
        "table": "t_stock_top10_float_holders",
        "columns": ['ts_code', 'ann_date', 'end_date', 'holder_name',
                   'hold_amount', 'hold_ratio', 'hold_change'],
        "unique_columns": ['ts_code', 'end_date', 'holder_name'],
        "sync_type": "incremental",
        "date_column": "end_date",
        "ts_code_required": True
    },

    # 股东人数
    "stk_holdernumber": {
        "api": "stk_holdernumber",
        "table": "t_stock_holder_number",
        "columns": ['ts_code', 'ann_date', 'end_date', 'holder_num',
                   'holder_num_change', 'holder_num_ratio'],
        "unique_columns": ['ts_code', 'end_date'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 股东增减持
    "stk_holdertrade": {
        "api": "stk_holdertrade",
        "table": "t_stock_holder_trade",
        "columns": ['ts_code', 'ann_date', 'holder_name', 'holder_type',
                   'in_de', 'change_vol', 'change_ratio', 'after_share',
                   'after_ratio', 'avg_price', 'total_share', 'begin_date', 'close_date'],
        "unique_columns": ['ts_code', 'ann_date', 'holder_name'],
        "sync_type": "incremental",
        "date_column": "ann_date"
    },

    # 股权质押
    "cgq": {
        "api": "cgq",
        "table": "t_stock_cgq",
        "columns": ['ts_code', 'ann_date', 'holder_name', 'hold_vol',
                   'hold_ratio', 'pledge_vol', 'pledge_ratio'],
        "unique_columns": ['ts_code', 'ann_date', 'holder_name'],
        "sync_type": "incremental",
        "date_column": "ann_date"
    },

    # 机构持股汇总
    "jgcc": {
        "api": "jgcc",
        "table": "t_stock_jgcc",
        "columns": ['ts_code', 'ann_date', 'end_date', 'org_type',
                   'org_num', 'hold_vol', 'hold_ratio'],
        "unique_columns": ['ts_code', 'end_date', 'org_type'],
        "sync_type": "incremental",
        "date_column": "end_date"
    },

    # 机构调研
    "jgdy": {
        "api": "jgdy",
        "table": "t_stock_jgdy",
        "columns": ['ts_code', 'ann_date', 'end_date', 'org_name', 'org_type',
                   'org_num', 'personnel', 'way', 'content'],
        "unique_columns": ['ts_code', 'ann_date'],
        "sync_type": "incremental",
        "date_column": "ann_date"
    },

    # 股权质押明细
    "gdfx": {
        "api": "gdfx",
        "table": "t_stock_gdfx",
        "columns": ['ts_code', 'ann_date', 'holder_name', 'hold_vol',
                   'hold_ratio', 'pledge_vol', 'pledge_ratio', 'froze_vol', 'unfroze_vol'],
        "unique_columns": ['ts_code', 'ann_date', 'holder_name'],
        "sync_type": "incremental",
        "date_column": "ann_date"
    },
}


# ========================================================
# 同步任务执行器
# ========================================================

class SyncTaskExecutor:
    """同步任务执行器"""

    def __init__(self, config: SyncConfig, db: DatabaseManager, client: TushareSyncClient):
        self.config = config
        self.db = db
        self.client = client
        self.logger = logging.getLogger("tushare_sync")
        self.stats = {
            "start_time": None,
            "end_time": None,
            "tables_processed": 0,
            "rows_fetched": 0,
            "rows_inserted": 0,
            "errors": []
        }

    def get_stock_list(self) -> List[str]:
        """获取股票列表"""
        df = self.client.query("stock_basic", list_status='L',
                              fields='ts_code')
        if df.empty:
            return []
        return df['ts_code'].tolist()

    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        results = self.db.fetchall(
            f"""
            SELECT cal_date FROM t_stock_tradedate
            WHERE cal_date BETWEEN %s AND %s
            AND is_open = 1
            ORDER BY cal_date
            """,
            (start_date, end_date)
        )
        return [r['cal_date'] for r in results]

    def execute_sync(self, table_name: str, mode: str = "auto",
                     start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        执行同步任务

        Args:
            table_name: 表配置名称
            mode: 同步模式 (full/incremental/auto)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            同步结果统计
        """
        if table_name not in TABLE_CONFIGS:
            raise ValueError(f"未知表配置: {table_name}")

        config = TABLE_CONFIGS[table_name]
        table = config['table']
        api = config['api']

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 开始同步: {table_name} -> {table}")
        self.logger.info(f"📌 同步模式: {mode}")

        # 确定日期范围
        if mode == "auto":
            mode = config.get('sync_type', 'incremental')

        # 对于需要股票代码循环的接口
        if config.get('ts_code_required', False):
            return self._sync_by_stock_code(config, mode, start_date, end_date)

        # 按日期获取的接口
        if config.get('date_column'):
            return self._sync_by_date(config, mode, start_date, end_date)

        # 全量获取接口
        return self._sync_full(config, mode)

    def _sync_full(self, config: Dict, mode: str) -> Dict[str, Any]:
        """全量同步"""
        table = config['table']
        api = config['api']
        columns = config['columns']
        unique_columns = config['unique_columns']
        update_columns = config.get('update_columns', [c for c in columns if c not in unique_columns])

        # 获取数据
        self.logger.info(f"📥 从 Tushare 获取数据...")
        df = self.client.query(api)

        if df.empty:
            self.logger.info("⚠️ 无数据返回")
            return {"status": "success", "rows": 0}

        self.logger.info(f"✅ 获取 {len(df)} 条记录")

        # 清理列名
        for col in columns:
            if col not in df.columns:
                df[col] = None
        df = df[columns]

        # 处理 NaN 值
        df = df.where(pd.notnull(df), None)

        # 转换数据为列表
        rows = df.values.tolist()

        # UPSERT
        self.logger.info(f"💾 写入数据库...")
        result = self.db.upsert(table, columns, rows, unique_columns, update_columns)

        self.logger.info(f"✅ 同步完成: 插入 {result['inserted']}, 更新 {result['updated']}")

        return {
            "status": "success",
            "table": table,
            "rows_fetched": len(df),
            "rows_inserted": result['inserted'],
            "rows_updated": result['updated']
        }

    def _sync_by_date(self, config: Dict, mode: str,
                      start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """按日期同步"""
        table = config['table']
        api = config['api']
        columns = config['columns']
        unique_columns = config['unique_columns']
        update_columns = config.get('update_columns', [c for c in columns if c not in unique_columns])
        date_column = config['date_column']

        # 确定日期范围
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        if mode == 'incremental' and not start_date:
            # 获取数据库中最新日期
            max_date = self.db.get_max_date(table, date_column)
            if max_date:
                start_date = (datetime.strptime(max_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            else:
                # 首次同步，从2005年开始
                start_date = '20050101'
                self.logger.info("🆕 首次全量同步，从 2005-01-01 开始")

        if not start_date:
            start_date = '20050101'

        # 检查是否需要同步
        if start_date > end_date:
            self.logger.info("✅ 数据已是最新，无需同步")
            return {"status": "skipped", "reason": "up_to_date"}

        self.logger.info(f"📅 日期范围: {start_date} - {end_date}")

        # 获取交易日列表
        trade_dates = self.get_trade_dates(start_date, end_date)
        if not trade_dates:
            self.logger.info("⚠️ 无交易日需要同步")
            return {"status": "skipped", "reason": "no_trade_dates"}

        self.logger.info(f"📊 需要同步 {len(trade_dates)} 个交易日")

        # 逐日同步
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_dates = []

        for i, trade_date in enumerate(trade_dates, 1):
            try:
                self.logger.info(f"   [{i}/{len(trade_dates)}] 处理 {trade_date}...",)

                # 获取单日数据
                df = self.client.query(api, trade_date=trade_date)

                if df.empty:
                    continue

                # 清理数据
                for col in columns:
                    if col not in df.columns:
                        df[col] = None
                df = df[columns]
                df = df.where(pd.notnull(df), None)

                rows = df.values.tolist()

                # UPSERT
                result = self.db.upsert(table, columns, rows, unique_columns, update_columns)

                total_fetched += len(df)
                total_inserted += result['inserted']
                total_updated += result['updated']

                self.logger.info(f"   ✓ {len(df)} 条")

            except Exception as e:
                self.logger.error(f"   ✗ 失败: {e}")
                failed_dates.append(trade_date)
                continue

        self.logger.info(f"\n✅ 同步完成: 获取 {total_fetched} 条, 插入 {total_inserted}, 更新 {total_updated}")
        if failed_dates:
            self.logger.warning(f"⚠️ 失败日期: {failed_dates}")

        return {
            "status": "success",
            "table": table,
            "rows_fetched": total_fetched,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "failed_dates": failed_dates
        }

    def _sync_by_stock_code(self, config: Dict, mode: str,
                            start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """按股票代码循环同步（用于财务数据）"""
        table = config['table']
        api = config['api']
        columns = config['columns']
        unique_columns = config['unique_columns']
        update_columns = config.get('update_columns', [c for c in columns if c not in unique_columns])
        date_column = config['date_column']

        # 获取股票列表
        stock_list = self.get_stock_list()
        if not stock_list:
            return {"status": "error", "reason": "no_stocks"}

        self.logger.info(f"📈 需要处理 {len(stock_list)} 只股票")

        # 日期范围
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        if not start_date:
            # 获取最新日期
            max_date = self.db.get_max_date(table, date_column)
            if max_date:
                start_date = (datetime.strptime(max_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            else:
                start_date = '20050101'

        if start_date > end_date:
            self.logger.info("✅ 数据已是最新")
            return {"status": "skipped", "reason": "up_to_date"}

        self.logger.info(f"📅 日期范围: {start_date} - {end_date}")

        # 逐股票同步
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_stocks = []

        for i, ts_code in enumerate(stock_list, 1):
            try:
                if i % 100 == 0:
                    self.logger.info(f"   进度: {i}/{len(stock_list)} ({i*100//len(stock_list)}%)")

                # 获取数据
                df = self.client.query(api, ts_code=ts_code,
                                      start_date=start_date, end_date=end_date)

                if df.empty:
                    continue

                # 清理数据
                for col in columns:
                    if col not in df.columns:
                        df[col] = None
                df = df[columns]
                df = df.where(pd.notnull(df), None)

                rows = df.values.tolist()

                # UPSERT
                result = self.db.upsert(table, columns, rows, unique_columns, update_columns)

                total_fetched += len(df)
                total_inserted += result['inserted']
                total_updated += result['updated']

            except Exception as e:
                self.logger.error(f"   ✗ {ts_code} 失败: {e}")
                failed_stocks.append(ts_code)
                continue

        self.logger.info(f"\n✅ 同步完成: 获取 {total_fetched} 条, 插入 {total_inserted}, 更新 {total_updated}")
        if failed_stocks:
            self.logger.warning(f"⚠️ 失败股票数: {len(failed_stocks)}")

        return {
            "status": "success",
            "table": table,
            "rows_fetched": total_fetched,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "failed_stocks": len(failed_stocks)
        }


# ========================================================
# 命令行接口
# ========================================================

def main():
    parser = argparse.ArgumentParser(
        description='Tushare 数据同步工具 - PostgreSQL 版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 同步股票基础信息（全量）
    python scripts/sync/tushare_sync.py --table stock_basic --mode full

    # 同步日线行情（增量）
    python scripts/sync/tushare_sync.py --table daily --mode incremental

    # 同步指定日期范围
    python scripts/sync/tushare_sync.py --table daily --start-date 20240101 --end-date 20240131

    # 同步所有基础数据表
    python scripts/sync/tushare_sync.py --all-basic

    # 同步所有行情数据表
    python scripts/sync/tushare_sync.py --all-market

    # 查看支持的表
    python scripts/sync/tushare_sync.py --list
        """
    )

    parser.add_argument('--table', type=str, help='要同步的表配置名称')
    parser.add_argument('--mode', type=str, choices=['full', 'incremental', 'auto'],
                       default='auto', help='同步模式 (默认: auto)')
    parser.add_argument('--start-date', type=str, help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (YYYYMMDD)')
    parser.add_argument('--all-basic', action='store_true', help='同步所有基础数据表')
    parser.add_argument('--all-market', action='store_true', help='同步所有行情数据表')
    parser.add_argument('--all-fina', action='store_true', help='同步所有财务数据表')
    parser.add_argument('--all', action='store_true', help='同步所有表')
    parser.add_argument('--list', action='store_true', help='列出支持的表')
    parser.add_argument('--log-file', type=str, help='日志文件路径')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式（不写入数据库）')

    args = parser.parse_args()

    # 列出支持的表
    if args.list:
        print("\n📋 支持的表配置:")
        print("-" * 60)
        categories = {
            '基础数据': ['stock_basic', 'trade_cal', 'namechange', 'hs_const', 'new_share', 'stock_company'],
            '行情数据': ['daily', 'adj_factor', 'daily_basic', 'stock_st', 'limit_list', 'moneyflow', 'moneyflow_hsgt'],
            '财务数据-利润表': ['income'],
            '财务数据-资产负债表': ['balancesheet'],
            '财务数据-现金流量表': ['cashflow'],
            '财务数据-指标': ['fina_indicator', 'fina_audit', 'fina_mainbz'],
            '财务数据-业绩': ['forecast', 'express', 'dividend'],
            '市场行为': ['top10_holders', 'top10_fh', 'stk_holdernumber', 'stk_holdertrade',
                      'cgq', 'jgcc', 'jgdy', 'gdfx']
        }
        for category, tables in categories.items():
            print(f"\n【{category}】")
            for t in tables:
                if t in TABLE_CONFIGS:
                    cfg = TABLE_CONFIGS[t]
                    print(f"  {t:<20} -> {cfg['table']:<30} ({cfg.get('sync_type', 'incremental')})")
        print()
        return

    # 加载配置
    config = SyncConfig.from_env()

    # 设置日志
    logger = setup_logging(config.log_level, args.log_file)
    logger.info("=" * 60)
    logger.info("🚀 Tushare 数据同步工具启动")
    logger.info(f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 验证配置
    if not config.db_password:
        logger.error("❌ 错误: DB_PASSWORD 环境变量未设置")
        sys.exit(1)

    # 初始化组件
    try:
        db = DatabaseManager(config)
        client = TushareSyncClient(config)
        executor = SyncTaskExecutor(config, db, client)
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        sys.exit(1)

    # 确定要同步的表
    tables_to_sync = []

    if args.table:
        tables_to_sync = [args.table]
    elif args.all_basic:
        tables_to_sync = ['stock_basic', 'trade_cal', 'hs_const', 'new_share', 'stock_company']
    elif args.all_market:
        tables_to_sync = ['daily', 'adj_factor', 'daily_basic', 'stock_st', 'limit_list',
                         'moneyflow', 'moneyflow_hsgt']
    elif args.all_fina:
        tables_to_sync = ['income', 'balancesheet', 'cashflow', 'fina_indicator',
                         'fina_audit', 'fina_mainbz', 'forecast', 'express', 'dividend']
    elif args.all:
        tables_to_sync = list(TABLE_CONFIGS.keys())
    else:
        parser.print_help()
        return

    # 执行同步
    results = []
    start_time = time.time()

    for table_name in tables_to_sync:
        try:
            result = executor.execute_sync(
                table_name=table_name,
                mode=args.mode,
                start_date=args.start_date,
                end_date=args.end_date
            )
            results.append({"table": table_name, **result})
        except Exception as e:
            logger.error(f"❌ 同步 {table_name} 失败: {e}")
            results.append({"table": table_name, "status": "error", "error": str(e)})

    # 输出汇总
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("📊 同步汇总")
    logger.info("-" * 60)

    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = len(results) - success_count

    for r in results:
        status_icon = "✅" if r['status'] == 'success' else "⚠️" if r['status'] == 'skipped' else "❌"
        logger.info(f"{status_icon} {r['table']:<20} {r['status']}")

    logger.info("-" * 60)
    logger.info(f"总计: {len(results)} 个表, 成功: {success_count}, 失败: {failed_count}")
    logger.info(f"耗时: {elapsed:.2f} 秒")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
