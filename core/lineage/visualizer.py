"""
数据血缘可视化模块

支持生成Mermaid图表、网络图等可视化格式
"""
from typing import Dict, List, Optional, Set
from datetime import datetime

from core.lineage.models import LineageNode, LineageEdge, LineageNodeType
from core.lineage.query import LineageQuery


class LineageVisualizer:
    """血缘可视化器"""

    # 节点类型颜色映射
    NODE_COLORS = {
        LineageNodeType.DATA_SOURCE: "#4CAF50",  # 绿色
        LineageNodeType.TABLE: "#2196F3",        # 蓝色
        LineageNodeType.VIEW: "#9C27B0",         # 紫色
        LineageNodeType.PIPELINE: "#FF9800",     # 橙色
        LineageNodeType.SCRIPT: "#607D8B",       # 灰色
        LineageNodeType.API: "#F44336",          # 红色
        LineageNodeType.FILE: "#795548",         # 棕色
        LineageNodeType.REPORT: "#E91E63",       # 粉色
    }

    # 节点类型图标映射
    NODE_ICONS = {
        LineageNodeType.DATA_SOURCE: "🌐",
        LineageNodeType.TABLE: "🗄️",
        LineageNodeType.VIEW: "👁️",
        LineageNodeType.PIPELINE: "⚙️",
        LineageNodeType.SCRIPT: "📜",
        LineageNodeType.API: "🔌",
        LineageNodeType.FILE: "📄",
        LineageNodeType.REPORT: "📊",
    }

    def __init__(self, db_name: str = "interface"):
        self.db_name = db_name
        self.query = LineageQuery(db_name)

    def to_mermaid(
        self,
        node_id: str,
        direction: str = "LR",
        max_depth: int = 3,
    ) -> str:
        """
        生成Mermaid流程图

        Args:
            node_id: 中心节点ID
            direction: 方向 (TB, BT, LR, RL)
            max_depth: 最大深度

        Returns:
            Mermaid语法字符串
        """
        lines = [f"graph {direction}"]

        # 收集节点和边
        nodes: Dict[str, LineageNode] = {}
        edges: List[tuple] = []

        center_node = self.query._get_node_by_id(node_id)
        if center_node:
            nodes[node_id] = center_node

        # 上游
        upstream = self.query.get_upstream(node_id, depth=max_depth)
        for node in upstream:
            nodes[node.id] = node

        # 下游
        downstream = self.query.get_downstream(node_id, depth=max_depth)
        for node in downstream:
            nodes[node.id] = node

        # 获取边
        if nodes:
            node_ids = list(nodes.keys())
            placeholders = ", ".join(["%s"] * len(node_ids))
            from core.storage.relational.connection import DatabaseManager
            sql = f"""
                SELECT source_id, target_id, relation_type
                FROM data_lineage_edges
                WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})
            """
            params = node_ids + node_ids
            results = DatabaseManager.fetchall(self.db_name, sql, params)

            for r in results:
                edges.append((r["source_id"], r["target_id"], r["relation_type"]))

        # 生成节点定义
        for nid, node in nodes.items():
            color = self.NODE_COLORS.get(node.node_type, "#999")
            icon = self.NODE_ICONS.get(node.node_type, "📦")
            safe_name = node.name.replace("(", "_").replace(")", "_").replace(" ", "_")
            lines.append(f'    {nid}["{icon} {node.name}"]')
            lines.append(f'    style {nid} fill:{color},color:#fff')

        # 生成边定义
        for source, target, rel_type in edges:
            arrow = "-->|" + rel_type.replace("_", " ") + "|"
            lines.append(f"    {source} {arrow} {target}")

        return "\n".join(lines)

    def to_text_tree(
        self,
        node_id: str,
        direction: str = "both",
        max_depth: int = 3,
    ) -> str:
        """
        生成文本树形图

        Args:
            node_id: 中心节点ID
            direction: upstream, downstream, both
            max_depth: 最大深度
        """
        lines = []
        node = self.query._get_node_by_id(node_id)
        if not node:
            return f"节点不存在: {node_id}"

        icon = self.NODE_ICONS.get(node.node_type, "📦")
        lines.append(f"{icon} {node.name} ({node.node_type.value})")
        lines.append("=" * 60)

        if direction in ("upstream", "both"):
            lines.append("\n📥 上游依赖 (Sources):")
            upstream = self.query.get_upstream(node_id, depth=max_depth)
            if upstream:
                for i, n in enumerate(upstream, 1):
                    indent = "  " * i
                    icon = self.NODE_ICONS.get(n.node_type, "📦")
                    lines.append(f"{indent}{icon} {n.name}")
            else:
                lines.append("  (无)")

        if direction in ("downstream", "both"):
            lines.append("\n📤 下游影响 (Targets):")
            downstream = self.query.get_downstream(node_id, depth=max_depth)
            if downstream:
                for i, n in enumerate(downstream, 1):
                    indent = "  " * i
                    icon = self.NODE_ICONS.get(n.node_type, "📦")
                    lines.append(f"{indent}{icon} {n.name}")
            else:
                lines.append("  (无)")

        return "\n".join(lines)

    def to_html(
        self,
        node_id: str,
        title: str = "数据血缘图",
    ) -> str:
        """
        生成可交互的HTML页面

        使用vis.js生成网络图
        """
        # 获取数据
        lineage = self.query.get_full_lineage(node_id)
        if "error" in lineage:
            return f"<h1>错误: {lineage['error']}</h1>"

        all_nodes = [lineage["node"]] + lineage["upstream"] + lineage["downstream"]

        # 构建节点数据
        nodes_data = []
        for node in all_nodes:
            nodes_data.append({
                "id": node.id,
                "label": node.name,
                "title": f"{node.node_type.value}: {node.name}",
                "color": self.NODE_COLORS.get(node.node_type, "#999"),
                "shape": "box",
            })

        # 构建边数据
        from core.storage.relational.connection import DatabaseManager
        node_ids = [n.id for n in all_nodes]
        placeholders = ", ".join(["%s"] * len(node_ids))
        sql = f"""
            SELECT source_id, target_id, relation_type
            FROM data_lineage_edges
            WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})
        """
        params = node_ids + node_ids
        edges_result = DatabaseManager.fetchall(self.db_name, sql, params)

        edges_data = []
        for r in edges_result:
            edges_data.append({
                "from": r["source_id"],
                "to": r["target_id"],
                "label": r["relation_type"],
                "arrows": "to",
            })

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
        #mynetwork {{ width: 100%; height: 800px; border: 1px solid #ccc; }}
        .header {{ padding: 20px; background: #f5f5f5; }}
        .legend {{ padding: 10px; background: #fff; border-bottom: 1px solid #ddd; }}
        .legend-item {{ display: inline-block; margin-right: 20px; }}
        .legend-color {{ display: inline-block; width: 20px; height: 20px; margin-right: 5px; vertical-align: middle; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>中心节点: {lineage["node"].name}</p>
    </div>
    <div class="legend">
        {self._generate_legend_html()}
    </div>
    <div id="mynetwork"></div>
    <script>
        var nodes = new vis.DataSet({nodes_data});
        var edges = new vis.DataSet({edges_data});
        var container = document.getElementById('mynetwork');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            layout: {{ hierarchical: false }},
            physics: {{
                forceAtlas2Based: {{
                    gravitationalConstant: -50,
                    centralGravity: 0.005,
                    springLength: 230,
                    springConstant: 0.18
                }},
                maxVelocity: 146,
                solver: 'forceAtlas2Based',
                timestep: 0.35,
                stabilization: {{ iterations: 150 }}
            }},
            edges: {{
                font: {{ size: 12 }},
                smooth: {{ type: 'continuous' }}
            }},
            nodes: {{
                font: {{ size: 14, color: '#fff' }},
                borderWidth: 2,
                shadow: true
            }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>"""

        return html.replace("{nodes_data}", str(nodes_data)).replace("{edges_data}", str(edges_data))

    def _generate_legend_html(self) -> str:
        """生成图例HTML"""
        items = []
        for node_type, color in self.NODE_COLORS.items():
            icon = self.NODE_ICONS.get(node_type, "📦")
            items.append(
                f'<span class="legend-item">'
                f'<span class="legend-color" style="background:{color}"></span>'
                f'{icon} {node_type.value}</span>'
            )
        return "\n".join(items)

    def export_to_file(
        self,
        node_id: str,
        filepath: str,
        format: str = "html",
    ):
        """
        导出血缘图到文件

        Args:
            node_id: 节点ID
            filepath: 输出文件路径
            format: 格式 (html, mermaid, txt)
        """
        if format == "html":
            content = self.to_html(node_id)
        elif format == "mermaid":
            content = self.to_mermaid(node_id)
        elif format == "txt":
            content = self.to_text_tree(node_id)
        else:
            raise ValueError(f"不支持的格式: {format}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"血缘图已导出: {filepath}")
