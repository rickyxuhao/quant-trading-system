#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资产负债表同步脚本
表名: t_stock_balancesheet
数据来源: Tushare balancesheet API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class BalanceSheetSync(BaseSyncTask):
    """资产负债表同步任务"""

    TABLE_NAME = "t_stock_balancesheet"
    API_NAME = "balancesheet"
    COLUMNS = [
        'ts_code', 'ann_date', 'f_ann_date', 'end_date', 'comp_type',
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
        'update_flag'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date', 'f_ann_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    MIN_EXPECTED_ROWS = 400000
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "资产负债表"


def main():
    run_main(BalanceSheetSync, "资产负债表同步 - t_stock_balancesheet")


if __name__ == "__main__":
    main()
