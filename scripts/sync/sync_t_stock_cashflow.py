#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
现金流量表同步脚本
表名: t_stock_cashflow
数据来源: Tushare cashflow API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class CashFlowSync(BaseSyncTask):
    """现金流量表同步任务"""

    TABLE_NAME = "t_stock_cashflow"
    API_NAME = "cashflow"
    COLUMNS = [
        'ts_code', 'ann_date', 'f_ann_date', 'end_date', 'comp_type',
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
        'n_incr_cash_equ'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date', 'f_ann_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    MIN_EXPECTED_ROWS = 400000
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "现金流量表"


def main():
    run_main(CashFlowSync, "现金流量表同步 - t_stock_cashflow")


if __name__ == "__main__":
    main()
