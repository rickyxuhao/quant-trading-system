#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
利润表同步脚本
表名: t_stock_income
数据来源: Tushare income API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class IncomeSync(BaseSyncTask):
    """利润表同步任务"""

    TABLE_NAME = "t_stock_income"
    API_NAME = "income"
    COLUMNS = [
        'ts_code', 'ann_date', 'f_ann_date', 'end_date', 'comp_type',
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
        'compr_inc_attr_m_s'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date', 'f_ann_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    MIN_EXPECTED_ROWS = 400000
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "利润表"


def main():
    run_main(IncomeSync, "利润表同步 - t_stock_income")


if __name__ == "__main__":
    main()
