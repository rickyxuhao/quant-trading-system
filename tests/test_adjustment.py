"""
复权价格计算模块单元测试
"""
import unittest
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from core.data_processing.adjustment import (
    calculate_adjusted_price,
    adjust_price_for_split_dividend
)


class TestCalculateAdjustedPrice(unittest.TestCase):
    """测试复权价格计算函数"""

    def setUp(self):
        """设置测试数据"""
        # 原始行情数据
        self.price_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 5,
            'trade_date': ['20240101', '20240102', '20240103', '20240104', '20240105'],
            'open': [100.0, 102.0, 105.0, 51.0, 52.0],  # 第4天除权（10送10）
            'high': [105.0, 107.0, 110.0, 54.0, 55.0],
            'low': [98.0, 101.0, 104.0, 50.0, 51.0],
            'close': [102.0, 105.0, 108.0, 53.0, 54.0],
            'vol': [10000] * 5
        })

        # 复权因子（假设第4天前复权因子为2.0，表示10送10）
        self.adj_factor_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 5,
            'trade_date': ['20240101', '20240102', '20240103', '20240104', '20240105'],
            'adj_factor': [2.0, 2.0, 2.0, 1.0, 1.0]
        })

    def test_forward_adjustment(self):
        """测试前复权计算"""
        result = calculate_adjusted_price(
            self.price_data,
            self.adj_factor_data,
            adj_type='forward'
        )

        # 前复权：以最新因子(1.0)为基准
        # 第1天 close = 102.0 * 2.0 / 1.0 = 204.0
        # 第4天 close = 53.0 * 1.0 / 1.0 = 53.0
        self.assertAlmostEqual(result.iloc[0]['adj_close'], 102.0, places=2)
        self.assertAlmostEqual(result.iloc[3]['adj_close'], 53.0, places=2)

    def test_backward_adjustment(self):
        """测试后复权计算"""
        result = calculate_adjusted_price(
            self.price_data,
            self.adj_factor_data,
            adj_type='backward'
        )

        # 后复权：以最早因子(2.0)为基准
        # 第1天 close = 102.0 * 2.0 / 2.0 = 102.0
        # 第4天 close = 53.0 * 1.0 / 2.0 = 26.5
        self.assertAlmostEqual(result.iloc[0]['adj_close'], 102.0, places=2)
        self.assertAlmostEqual(result.iloc[3]['adj_close'], 26.5, places=2)

    def test_missing_adj_factor(self):
        """测试缺少复权因子时的处理"""
        # 移除部分复权因子数据
        incomplete_adj = self.adj_factor_data.iloc[2:].copy()

        result = calculate_adjusted_price(
            self.price_data,
            incomplete_adj,
            adj_type='forward'
        )

        # 应该仍然返回结果，缺失的因子用1.0填充
        self.assertEqual(len(result), 5)
        self.assertFalse(result['adj_close'].isna().any())

    def test_multiple_stocks(self):
        """测试多只股票同时计算"""
        price_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3 + ['000002.SZ'] * 3,
            'trade_date': ['20240101', '20240102', '20240103'] * 2,
            'open': [100.0, 102.0, 105.0, 50.0, 51.0, 52.0],
            'high': [105.0, 107.0, 110.0, 55.0, 56.0, 57.0],
            'low': [98.0, 101.0, 104.0, 48.0, 49.0, 50.0],
            'close': [102.0, 105.0, 108.0, 52.0, 53.0, 54.0],
        })

        adj_factor_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3 + ['000002.SZ'] * 3,
            'trade_date': ['20240101', '20240102', '20240103'] * 2,
            'adj_factor': [1.0, 1.0, 1.0, 2.0, 2.0, 2.0]
        })

        result = calculate_adjusted_price(
            price_data,
            adj_factor_data,
            adj_type='forward'
        )

        # 检查分组计算是否正确
        stock1_data = result[result['ts_code'] == '000001.SZ']
        stock2_data = result[result['ts_code'] == '000002.SZ']

        self.assertEqual(len(stock1_data), 3)
        self.assertEqual(len(stock2_data), 3)

    def test_missing_required_columns(self):
        """测试缺少必需列时的错误处理"""
        invalid_df = pd.DataFrame({
            'open': [100.0, 101.0],
            'close': [101.0, 102.0]
        })

        with self.assertRaises(ValueError) as context:
            calculate_adjusted_price(invalid_df, self.adj_factor_data)

        self.assertIn('ts_code', str(context.exception))


class TestAdjustPriceForSplitDividend(unittest.TestCase):
    """测试单序列复权调整函数"""

    def test_forward_adjustment_series(self):
        """测试前复权序列计算"""
        prices = pd.Series([100.0, 102.0, 105.0, 53.0, 54.0])
        adj_factors = pd.Series([2.0, 2.0, 2.0, 1.0, 1.0])

        result = adjust_price_for_split_dividend(prices, adj_factors, adj_type='forward')

        # 前复权：以最新因子(1.0)为基准
        expected = pd.Series([100.0, 102.0, 105.0, 53.0, 54.0])
        pd.testing.assert_series_equal(result, expected)

    def test_backward_adjustment_series(self):
        """测试后复权序列计算"""
        prices = pd.Series([100.0, 102.0, 105.0, 53.0, 54.0])
        adj_factors = pd.Series([2.0, 2.0, 2.0, 1.0, 1.0])

        result = adjust_price_for_split_dividend(prices, adj_factors, adj_type='backward')

        # 后复权：以最早因子(2.0)为基准
        expected = pd.Series([100.0, 102.0, 105.0, 26.5, 27.0])
        pd.testing.assert_series_equal(result, expected)

    def test_length_mismatch(self):
        """测试序列长度不匹配时的错误"""
        prices = pd.Series([100.0, 102.0, 105.0])
        adj_factors = pd.Series([2.0, 2.0])

        with self.assertRaises(ValueError) as context:
            adjust_price_for_split_dividend(prices, adj_factors)

        self.assertIn('长度不一致', str(context.exception))


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_empty_dataframe(self):
        """测试空DataFrame处理"""
        empty_df = pd.DataFrame(columns=['ts_code', 'trade_date', 'open', 'close'])
        adj_df = pd.DataFrame(columns=['ts_code', 'trade_date', 'adj_factor'])

        # 空数据应该能正常处理
        result = calculate_adjusted_price(empty_df, adj_df)
        self.assertEqual(len(result), 0)

    def test_single_row(self):
        """测试单行数据"""
        single_price = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20240101'],
            'open': [100.0],
            'high': [105.0],
            'low': [98.0],
            'close': [102.0]
        })

        single_adj = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20240101'],
            'adj_factor': [1.5]
        })

        result = calculate_adjusted_price(single_price, single_adj, adj_type='forward')
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result.iloc[0]['adj_close'], 102.0, places=2)

    def test_constant_adj_factor(self):
        """测试复权因子恒为1的情况"""
        price_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3,
            'trade_date': ['20240101', '20240102', '20240103'],
            'open': [100.0, 102.0, 105.0],
            'high': [105.0, 107.0, 110.0],
            'low': [98.0, 101.0, 104.0],
            'close': [102.0, 105.0, 108.0],
        })

        # 所有复权因子都是1
        adj_factor_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3,
            'trade_date': ['20240101', '20240102', '20240103'],
            'adj_factor': [1.0, 1.0, 1.0]
        })

        result = calculate_adjusted_price(price_data, adj_factor_data, adj_type='forward')

        # 复权价格应该等于原始价格
        pd.testing.assert_series_equal(
            result['adj_close'].reset_index(drop=True),
            price_data['close'].reset_index(drop=True)
        )


if __name__ == '__main__':
    unittest.main()
