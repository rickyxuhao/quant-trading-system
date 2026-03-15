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

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


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
    # 预期数据量: 约5500只股票 * 80季度(20年) ≈ 44万条
    MIN_EXPECTED_ROWS = 400000


def main():
    parser = create_base_parser("利润表同步 - t_stock_income")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = IncomeSync(config, db, client)
    result = sync_task.execute(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date
    )

    # 输出结果
    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
