#!/usr/bin/env python3
"""
数据血缘命令行工具

Usage:
    python scripts/lineage_cli.py register --name t_stock_dailymarketdata --type table
    python scripts/lineage_cli.py trace --node t_stock_dailymarketdata
    python scripts/lineage_cli.py impact --node t_stock_dailymarketdata
    python scripts/lineage_cli.py visualize --node t_stock_dailymarketdata --output lineage.html
    python scripts/lineage_cli.py stats
"""
import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.lineage import (
    DataLineageTracker,
    LineageNodeType,
    LineageRelationType,
    LineageQuery,
    LineageVisualizer,
    NodeMetadata,
)


def cmd_register(args):
    """注册节点"""
    tracker = DataLineageTracker()

    node_type = LineageNodeType(args.type)
    metadata = NodeMetadata(
        description=args.description,
        owner=args.owner,
        tags=args.tags.split(",") if args.tags else [],
    )

    node = tracker.register_node(
        name=args.name,
        node_type=node_type,
        namespace=args.namespace,
        metadata=metadata,
    )

    print(f"✅ 节点已注册: {node.qualified_name} (ID: {node.id})")
    return node


def cmd_relate(args):
    """建立关系"""
    tracker = DataLineageTracker()
    query = LineageQuery()

    # 查找源节点
    source = query.tracker.get_node_by_name(args.source, args.namespace)
    if not source:
        print(f"❌ 源节点不存在: {args.source}")
        return

    # 查找目标节点
    target = query.tracker.get_node_by_name(args.target, args.namespace)
    if not target:
        print(f"❌ 目标节点不存在: {args.target}")
        return

    relation = LineageRelationType(args.relation)

    edge = tracker.register_edge(
        source=source,
        target=target,
        relation_type=relation,
        transform_logic=args.logic,
    )

    print(f"✅ 关系已建立: {source.name} -> {target.name} ({relation.value})")


def cmd_trace(args):
    """追踪血缘"""
    query = LineageQuery()

    node = query.tracker.get_node_by_name(args.node, args.namespace)
    if not node:
        print(f"❌ 节点不存在: {args.node}")
        return

    print(f"\n📊 血缘追踪: {args.node}\n")

    lineage = query.get_full_lineage(node.id)

    print(f"节点: {lineage['node'].name}")
    print(f"类型: {lineage['node'].node_type.value}")
    print(f"\n📥 上游依赖 ({lineage['upstream_count']} 个):")
    for n in lineage['upstream'][:10]:
        print(f"  - {n.name} ({n.node_type.value})")
    if lineage['upstream_count'] > 10:
        print(f"  ... 还有 {lineage['upstream_count'] - 10} 个")

    print(f"\n📤 下游影响 ({lineage['downstream_count']} 个):")
    for n in lineage['downstream'][:10]:
        print(f"  - {n.name} ({n.node_type.value})")
    if lineage['downstream_count'] > 10:
        print(f"  ... 还有 {lineage['downstream_count'] - 10} 个")


def cmd_impact(args):
    """影响分析"""
    query = LineageQuery()

    node = query.tracker.get_node_by_name(args.node, args.namespace)
    if not node:
        print(f"❌ 节点不存在: {args.node}")
        return

    print(f"\n🔍 影响分析: {args.node}\n")

    impact = query.impact_analysis(node.id)

    print(f"直接依赖数: {len(impact.direct_dependents)}")
    print(f"总影响数: {len(impact.all_dependents)}")

    if impact.direct_dependents:
        print("\n⚠️  直接受影响的节点:")
        for n in impact.direct_dependents:
            print(f"  - {n.name}")


def cmd_visualize(args):
    """可视化"""
    visualizer = LineageVisualizer()
    query = LineageQuery()

    node = query.tracker.get_node_by_name(args.node, args.namespace)
    if not node:
        print(f"❌ 节点不存在: {args.node}")
        return

    if args.format == "mermaid":
        content = visualizer.to_mermaid(node.id)
        print(content)
    elif args.format == "txt":
        content = visualizer.to_text_tree(node.id)
        print(content)
    else:  # html
        if args.output:
            visualizer.export_to_file(node.id, args.output, "html")
        else:
            print("HTML格式需要指定 --output 参数")


def cmd_stats(args):
    """统计信息"""
    query = LineageQuery()
    stats = query.get_lineage_statistics()

    print("\n📈 数据血缘统计\n")
    print(f"总节点数: {stats['total_nodes']}")
    print(f"总关系数: {stats['total_edges']}")
    print(f"\n节点类型分布:")
    for node_type, count in stats['node_breakdown'].items():
        print(f"  - {node_type}: {count}")
    print(f"\n关系类型分布:")
    for rel_type, count in stats['edge_breakdown'].items():
        print(f"  - {rel_type}: {count}")


def cmd_search(args):
    """搜索节点"""
    query = LineageQuery()

    node_type = LineageNodeType(args.type) if args.type else None
    results = query.search_nodes(
        keyword=args.keyword,
        node_type=node_type,
        namespace=args.namespace,
    )

    print(f"\n🔎 搜索结果 ({len(results)} 个):\n")
    for node in results:
        print(f"  {node.name} ({node.node_type.value}) - {node.namespace}")


def cmd_orphan(args):
    """查找孤立节点"""
    query = LineageQuery()
    orphans = query.get_orphan_nodes(args.namespace)

    print(f"\n🚫 孤立节点 ({len(orphans)} 个):\n")
    for node in orphans:
        print(f"  - {node.name} ({node.node_type.value})")


def main():
    parser = argparse.ArgumentParser(
        description="数据血缘管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # register 命令
    register_parser = subparsers.add_parser("register", help="注册节点")
    register_parser.add_argument("--name", required=True, help="节点名称")
    register_parser.add_argument("--type", required=True, choices=[t.value for t in LineageNodeType], help="节点类型")
    register_parser.add_argument("--namespace", default="default", help="命名空间")
    register_parser.add_argument("--description", help="描述")
    register_parser.add_argument("--owner", help="负责人")
    register_parser.add_argument("--tags", help="标签（逗号分隔）")
    register_parser.set_defaults(func=cmd_register)

    # relate 命令
    relate_parser = subparsers.add_parser("relate", help="建立关系")
    relate_parser.add_argument("--source", required=True, help="源节点")
    relate_parser.add_argument("--target", required=True, help="目标节点")
    relate_parser.add_argument("--relation", required=True, choices=[r.value for r in LineageRelationType], help="关系类型")
    relate_parser.add_argument("--namespace", default="default", help="命名空间")
    relate_parser.add_argument("--logic", help="转换逻辑")
    relate_parser.set_defaults(func=cmd_relate)

    # trace 命令
    trace_parser = subparsers.add_parser("trace", help="追踪血缘")
    trace_parser.add_argument("--node", required=True, help="节点名称")
    trace_parser.add_argument("--namespace", default="default", help="命名空间")
    trace_parser.set_defaults(func=cmd_trace)

    # impact 命令
    impact_parser = subparsers.add_parser("impact", help="影响分析")
    impact_parser.add_argument("--node", required=True, help="节点名称")
    impact_parser.add_argument("--namespace", default="default", help="命名空间")
    impact_parser.set_defaults(func=cmd_impact)

    # visualize 命令
    viz_parser = subparsers.add_parser("visualize", help="可视化")
    viz_parser.add_argument("--node", required=True, help="节点名称")
    viz_parser.add_argument("--namespace", default="default", help="命名空间")
    viz_parser.add_argument("--format", choices=["html", "mermaid", "txt"], default="html", help="输出格式")
    viz_parser.add_argument("--output", help="输出文件路径")
    viz_parser.set_defaults(func=cmd_visualize)

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="统计信息")
    stats_parser.set_defaults(func=cmd_stats)

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索节点")
    search_parser.add_argument("keyword", help="搜索关键词")
    search_parser.add_argument("--type", choices=[t.value for t in LineageNodeType], help="节点类型")
    search_parser.add_argument("--namespace", help="命名空间")
    search_parser.set_defaults(func=cmd_search)

    # orphan 命令
    orphan_parser = subparsers.add_parser("orphan", help="查找孤立节点")
    orphan_parser.add_argument("--namespace", help="命名空间")
    orphan_parser.set_defaults(func=cmd_orphan)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
