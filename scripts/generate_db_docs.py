#!/usr/bin/env python3
"""
数据库文档自动生成脚本

从数据库 INFORMATION_SCHEMA 读取表结构并生成 Markdown 文档

用法:
    # 生成所有数据库的文档
    poetry run python scripts/generate_db_docs.py --all

    # 生成指定数据库的文档
    poetry run python scripts/generate_db_docs.py --db tushare_biz

    # 生成指定表的文档
    poetry run python scripts/generate_db_docs.py --table t_stock_basic

    # 输出到指定目录
    poetry run python scripts/generate_db_docs.py --all --output docs/database/
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

import click

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.storage.relational.connection import DatabaseManager


# 支持的数据库列表
SUPPORTED_DATABASES = ["tushare_biz", "interface"]


class DatabaseDocGenerator:
    """数据库文档生成器"""

    def __init__(self, db_name: str):
        self.db_name = db_name
        self.actual_db_name = self._get_actual_db_name(db_name)

    def _get_actual_db_name(self, db_name: str) -> str:
        """获取实际的数据库名称（考虑环境变量）"""
        import os
        db_names = {
            "tushare_biz": os.getenv("DB_NAME_TUSHARE", "tushare_biz"),
            "interface": os.getenv("DB_NAME_INTERFACE", "interface"),
        }
        return db_names.get(db_name, db_name)

    def _query(self, sql: str, params: tuple = None) -> List[Dict]:
        """执行查询"""
        return DatabaseManager.fetchall(self.db_name, sql, params)

    def get_tables(self) -> List[Dict]:
        """获取数据库中所有表的信息"""
        sql = """
            SELECT
                TABLE_NAME as table_name,
                TABLE_COMMENT as table_comment,
                ENGINE as engine,
                TABLE_ROWS as table_rows,
                DATA_LENGTH as data_length,
                INDEX_LENGTH as index_length,
                CREATE_TIME as create_time,
                UPDATE_TIME as update_time,
                TABLE_COLLATION as collation
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """
        return self._query(sql, (self.actual_db_name,))

    def get_table_info(self, table_name: str) -> Optional[Dict]:
        """获取单个表的详细信息"""
        tables = self.get_tables()
        for table in tables:
            if table["table_name"] == table_name:
                return table
        return None

    def get_columns(self, table_name: str) -> List[Dict]:
        """获取表的所有字段信息"""
        sql = """
            SELECT
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                IS_NULLABLE as is_nullable,
                COLUMN_DEFAULT as column_default,
                COLUMN_COMMENT as column_comment,
                CHARACTER_MAXIMUM_LENGTH as char_max_length,
                NUMERIC_PRECISION as numeric_precision,
                NUMERIC_SCALE as numeric_scale,
                COLUMN_TYPE as column_type,
                ORDINAL_POSITION as ordinal_position,
                EXTRA as extra
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        return self._query(sql, (self.actual_db_name, table_name))

    def get_indexes(self, table_name: str) -> List[Dict]:
        """获取表的所有索引信息"""
        sql = """
            SELECT
                INDEX_NAME as index_name,
                NON_UNIQUE as non_unique,
                COLUMN_NAME as column_name,
                INDEX_TYPE as index_type,
                SEQ_IN_INDEX as seq_in_index,
                CARDINALITY as cardinality
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """
        return self._query(sql, (self.actual_db_name, table_name))

    def get_create_table_sql(self, table_name: str) -> str:
        """获取建表语句"""
        sql = "SHOW CREATE TABLE `{}`".format(table_name)
        try:
            result = self._query(sql)
            if result:
                return result[0].get("Create Table", "")
        except Exception:
            pass
        return ""

    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict]:
        """获取表的数据示例"""
        sql = "SELECT * FROM `{}` LIMIT {}".format(table_name, limit)
        try:
            return self._query(sql)
        except Exception:
            return []

    def format_size(self, size_bytes: int) -> str:
        """格式化字节大小为人类可读格式"""
        if size_bytes is None or size_bytes == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def format_number(self, num: int) -> str:
        """格式化数字，添加千位分隔符"""
        if num is None:
            return "0"
        return f"{num:,}"

    def format_data_type(self, col: Dict) -> str:
        """格式化数据类型显示"""
        data_type = col["data_type"].upper()
        char_max = col.get("char_max_length")
        num_precision = col.get("numeric_precision")
        num_scale = col.get("numeric_scale")

        if data_type in ["VARCHAR", "CHAR"] and char_max:
            return f"{data_type}({char_max})"
        elif data_type in ["DECIMAL", "NUMERIC"] and num_precision:
            if num_scale:
                return f"{data_type}({num_precision},{num_scale})"
            return f"{data_type}({num_precision})"
        return data_type

    def generate_table_doc(self, table_name: str) -> str:
        """生成单个表的 Markdown 文档"""
        table_info = self.get_table_info(table_name)
        if not table_info:
            return f"# 表不存在: {table_name}\n\n表 `{table_name}` 在数据库中不存在。\n"

        columns = self.get_columns(table_name)
        indexes = self.get_indexes(table_name)
        create_sql = self.get_create_table_sql(table_name)
        sample_data = self.get_sample_data(table_name)

        lines = []

        # 标题
        lines.append(f"# {table_name}")
        lines.append("")

        # 表信息
        lines.append("## 表信息")
        lines.append("")
        lines.append("| 属性 | 值 |")
        lines.append("|:---|:---|")
        lines.append(f"| 数据库 | {self.db_name} |")
        lines.append(f"| 表名 | {table_name} |")
        lines.append(f"| 中文名 | {table_info.get('table_comment', '-')} |")
        lines.append(f"| 存储引擎 | {table_info.get('engine', 'InnoDB')} |")
        lines.append(f"| 字符集 | {table_info.get('collation', 'utf8mb4')} |")
        lines.append(f"| 数据量 | {self.format_number(table_info.get('table_rows'))} 行 |")
        lines.append(f"| 数据大小 | {self.format_size(table_info.get('data_length'))} |")
        lines.append(f"| 索引大小 | {self.format_size(table_info.get('index_length'))} |")

        create_time = table_info.get('create_time')
        if create_time:
            lines.append(f"| 创建时间 | {create_time} |")

        update_time = table_info.get('update_time')
        if update_time:
            lines.append(f"| 更新时间 | {update_time} |")

        lines.append("")

        # 字段列表
        lines.append("## 字段列表")
        lines.append("")
        lines.append("| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |")
        lines.append("|:---|:---|:---|:---|:---|")

        for col in columns:
            col_name = col["column_name"]
            data_type = self.format_data_type(col)
            is_nullable = "YES" if col["is_nullable"] == "YES" else "NO"
            default = col["column_default"]
            default_str = str(default) if default is not None else "-"
            if default_str == "None":
                default_str = "-"
            comment = col.get("column_comment", "")

            lines.append(f"| `{col_name}` | {data_type} | {is_nullable} | {default_str} | {comment} |")

        lines.append("")

        # 索引
        if indexes:
            lines.append("## 索引")
            lines.append("")
            lines.append("| 索引名 | 类型 | 字段 | 说明 |")
            lines.append("|:---|:---|:---|:---|")

            # 按索引名分组
            index_groups: Dict[str, List[Dict]] = {}
            for idx in indexes:
                idx_name = idx["index_name"]
                if idx_name not in index_groups:
                    index_groups[idx_name] = []
                index_groups[idx_name].append(idx)

            for idx_name, idx_cols in index_groups.items():
                # 确定索引类型
                if idx_name == "PRIMARY":
                    idx_type = "主键"
                elif idx_cols[0]["non_unique"] == 0:
                    idx_type = "唯一"
                else:
                    idx_type = "普通"

                # 组合字段
                columns_str = ", ".join([c["column_name"] for c in idx_cols])

                lines.append(f"| {idx_name} | {idx_type} | {columns_str} | - |")

            lines.append("")

        # 数据示例
        if sample_data:
            lines.append("## 数据示例")
            lines.append("")

            # 获取列名（从前几个字段中选择）
            display_cols = columns[:6]  # 最多显示前6列
            col_names = [c["column_name"] for c in display_cols]

            # 表头
            lines.append("| " + " | ".join(col_names) + " |")
            lines.append("| " + " | ".join([":---"] * len(col_names)) + " |")

            # 数据行
            for row in sample_data:
                values = []
                for col in display_cols:
                    val = row.get(col["column_name"])
                    if val is None:
                        val = "NULL"
                    else:
                        val = str(val)[:50]  # 截断长文本
                        if len(str(row.get(col["column_name"], ""))) > 50:
                            val += "..."
                    values.append(val)
                lines.append("| " + " | ".join(values) + " |")

            if len(columns) > 6:
                lines.append("")
                lines.append(f"> 注：仅显示前 6 列，完整字段见上方「字段列表」。")

            lines.append("")

        # 建表语句
        if create_sql:
            lines.append("## 建表语句")
            lines.append("")
            lines.append("```sql")
            lines.append(create_sql)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def generate_db_summary(self) -> str:
        """生成数据库概览文档"""
        tables = self.get_tables()

        lines = []
        lines.append(f"# {self.db_name} 数据库文档")
        lines.append("")
        lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 统计信息
        total_tables = len(tables)
        total_rows = sum(t.get("table_rows", 0) or 0 for t in tables)
        total_data_size = sum(t.get("data_length", 0) or 0 for t in tables)
        total_index_size = sum(t.get("index_length", 0) or 0 for t in tables)

        lines.append("## 统计概览")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|:---|:---|")
        lines.append(f"| 表数量 | {total_tables} |")
        lines.append(f"| 总数据行数 | {self.format_number(total_rows)} |")
        lines.append(f"| 总数据大小 | {self.format_size(total_data_size)} |")
        lines.append(f"| 总索引大小 | {self.format_size(total_index_size)} |")
        lines.append(f"| 总存储大小 | {self.format_size(total_data_size + total_index_size)} |")
        lines.append("")

        # 表列表
        lines.append("## 表清单")
        lines.append("")
        lines.append("| 表名 | 中文名 | 数据行数 | 数据大小 | 说明 |")
        lines.append("|:---|:---|---:|---:|:---|")

        for table in tables:
            name = table["table_name"]
            comment = table.get("table_comment", "") or ""
            rows = table.get("table_rows", 0) or 0
            size = self.format_size(table.get("data_length", 0) or 0)
            doc_link = f"[{name}](./{name}.md)"
            lines.append(f"| {doc_link} | {comment} | {self.format_number(rows)} | {size} | [详情](./{name}.md) |")

        lines.append("")

        return "\n".join(lines)


def generate_docs(
    db_name: Optional[str] = None,
    table_name: Optional[str] = None,
    output_dir: str = "docs/database",
    generate_all: bool = False,
):
    """生成文档的主函数"""
    output_path = Path(output_dir)

    if generate_all:
        # 生成所有数据库的文档
        databases = SUPPORTED_DATABASES
    elif db_name:
        # 生成指定数据库的文档
        databases = [db_name]
    elif table_name:
        # 生成指定表的文档（需要确定表属于哪个数据库）
        databases = []
        for db in SUPPORTED_DATABASES:
            try:
                gen = DatabaseDocGenerator(db)
                if gen.get_table_info(table_name):
                    databases = [db]
                    break
            except Exception:
                continue
        if not databases:
            print(f"错误: 表 {table_name} 不存在于任何数据库中")
            sys.exit(1)
    else:
        print("错误: 请指定 --all, --db 或 --table 参数")
        sys.exit(1)

    # 生成文档
    for db in databases:
        print(f"\n正在生成 {db} 数据库的文档...")

        try:
            gen = DatabaseDocGenerator(db)
        except Exception as e:
            print(f"  ❌ 连接数据库 {db} 失败: {e}")
            continue

        # 创建输出目录
        db_output_dir = output_path / db
        db_output_dir.mkdir(parents=True, exist_ok=True)

        if table_name:
            # 只生成指定表的文档
            tables = [table_name]
        else:
            # 获取所有表
            tables_info = gen.get_tables()
            tables = [t["table_name"] for t in tables_info]

            # 生成数据库概览
            summary_doc = gen.generate_db_summary()
            summary_path = db_output_dir / "README.md"
            summary_path.write_text(summary_doc, encoding="utf-8")
            print(f"  ✅ 生成概览文档: {summary_path}")

        # 生成每个表的文档
        for i, tbl in enumerate(tables, 1):
            doc = gen.generate_table_doc(tbl)
            doc_path = db_output_dir / f"{tbl}.md"
            doc_path.write_text(doc, encoding="utf-8")
            print(f"  ✅ [{i}/{len(tables)}] 生成表文档: {tbl}")

    print(f"\n文档生成完成！输出目录: {output_dir}")


@click.command()
@click.option("--all", "generate_all", is_flag=True, help="生成所有数据库的文档")
@click.option("--db", "db_name", type=str, help="指定数据库名称")
@click.option("--table", "table_name", type=str, help="指定表名称")
@click.option("--output", "output_dir", default="docs/database", help="输出目录 (默认: docs/database)")
def main(generate_all: bool, db_name: Optional[str], table_name: Optional[str], output_dir: str):
    """
    数据库文档自动生成脚本

    从数据库 INFORMATION_SCHEMA 读取表结构并生成 Markdown 文档

    示例:
        # 生成所有数据库的文档
        poetry run python scripts/generate_db_docs.py --all

        # 生成指定数据库的文档
        poetry run python scripts/generate_db_docs.py --db tushare_biz

        # 生成指定表的文档
        poetry run python scripts/generate_db_docs.py --table t_stock_basic

        # 指定输出目录
        poetry run python scripts/generate_db_docs.py --all --output docs/database/
    """
    # 验证参数
    if db_name and db_name not in SUPPORTED_DATABASES:
        print(f"错误: 不支持的数据库 {db_name}")
        print(f"支持的数据库: {', '.join(SUPPORTED_DATABASES)}")
        sys.exit(1)

    if not generate_all and not db_name and not table_name:
        # 显示帮助信息
        click.echo(main.get_help(click.Context(main)))
        sys.exit(0)

    generate_docs(
        db_name=db_name,
        table_name=table_name,
        output_dir=output_dir,
        generate_all=generate_all,
    )


if __name__ == "__main__":
    main()
