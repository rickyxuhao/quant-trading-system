#!/usr/bin/env python3
"""
诊断PE缺失原因
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.storage.relational.connection import DatabaseManager

# 1. 检查PE为NULL的股票特征
print("=" * 60)
print("1. PE缺失股票分析 (2024年数据)")
print("=" * 60)

sql = """
SELECT 
    COUNT(*) as total_stocks,
    SUM(CASE WHEN pe_ttm IS NULL THEN 1 ELSE 0 END) as null_pe_count,
    SUM(CASE WHEN pe_ttm IS NOT NULL THEN 1 ELSE 0 END) as valid_pe_count,
    AVG(CASE WHEN pe_ttm IS NULL THEN 1 ELSE 0 END) * 100 as null_pe_pct
FROM t_stock_daily_basic
WHERE trade_date >= '20240101' AND trade_date <= '20241231'
"""
result = DatabaseManager.fetchone("tushare_biz", sql)
print(f"总记录数: {result['total_stocks']}")
print(f"PE缺失: {result['null_pe_count']} ({result['null_pe_pct']:.1f}%)")
print(f"PE有效: {result['valid_pe_count']}")

# 2. 查看这些股票的行业分布
print("\n" + "=" * 60)
print("2. PE缺失股票的行业分布 (抽样)")
print("=" * 60)

sql2 = """
SELECT 
    b.industry,
    COUNT(*) as count
FROM t_stock_daily_basic a
JOIN t_stock_basic b ON a.ts_code = b.ts_code
WHERE a.trade_date >= '20240101' 
  AND a.pe_ttm IS NULL
  AND b.industry IS NOT NULL
GROUP BY b.industry
ORDER BY count DESC
LIMIT 10
"""
results = DatabaseManager.fetchall("tushare_biz", sql2)
for r in results:
    print(f"  {r['industry']}: {r['count']}")

# 3. 查看这些股票的名称特征（是否ST、银行等）
print("\n" + "=" * 60)
print("3. PE缺失股票的名称特征 (抽样)")
print("=" * 60)

sql3 = """
SELECT DISTINCT
    a.ts_code,
    b.name,
    b.industry
FROM t_stock_daily_basic a
JOIN t_stock_basic b ON a.ts_code = b.ts_code
WHERE a.trade_date >= '20240101' 
  AND a.pe_ttm IS NULL
LIMIT 20
"""
results = DatabaseManager.fetchall("tushare_biz", sql3)
for r in results:
    print(f"  {r['ts_code']} {r['name']} ({r['industry']})")

# 4. 查看有哪些行业相关表
print("\n" + "=" * 60)
print("4. 数据库中的行业相关表")
print("=" * 60)

sql_tables = "SHOW TABLES LIKE '%sw%'"
results = DatabaseManager.fetchall("tushare_biz", sql_tables)
print("SW相关表:")
for r in results:
    print(f"  - {list(r.values())[0]}")

# 检查t_sw_member表结构
print("\n" + "=" * 60)
print("5. SW行业成员表 (t_sw_member) 结构")
print("=" * 60)

try:
    sql_desc = "DESCRIBE t_sw_member"
    results = DatabaseManager.fetchall("tushare_biz", sql_desc)
    print("表结构:")
    for r in results:
        print(f"  {r['Field']}: {r['Type']}")
    
    # 获取列名
    columns = [r['Field'] for r in results]
    
    # 根据实际列名查询
    count_col = 'id' if 'id' in columns else columns[0]
    
    sql4 = f"""
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT {columns[0]}) as unique_first_col
    FROM t_sw_member
    """
    result = DatabaseManager.fetchone("tushare_biz", sql4)
    print(f"\n总记录数: {result['total_records']}")
    
    # 检查样本数据
    sql6 = f"""
    SELECT *
    FROM t_sw_member
    LIMIT 5
    """
    results = DatabaseManager.fetchall("tushare_biz", sql6)
    print("\n样本数据:")
    for r in results:
        print(f"  {r}")
        
except Exception as e:
    print(f"查询失败: {e}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
