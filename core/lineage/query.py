"""
数据血缘查询模块

支持血缘追溯、影响分析、依赖查询
"""
from typing import Dict, List, Optional, Set
from collections import deque

from core.storage.relational.connection import DatabaseManager
from core.lineage.models import (
    LineageNode,
    LineageEdge,
    LineageNodeType,
    LineageRelationType,
    ImpactAnalysisResult,
)
from core.lineage.tracker import DataLineageTracker


class LineageQuery:
    """血缘查询器"""

    def __init__(self, db_name: str = "interface"):
        self.db_name = db_name
        self.tracker = DataLineageTracker(db_name)

    def get_upstream(
        self,
        node_id: str,
        depth: int = -1,
        relation_types: Optional[List[LineageRelationType]] = None,
    ) -> List[LineageNode]:
        """
        获取上游依赖（溯源）

        Args:
            node_id: 节点ID
            depth: 查询深度，-1表示不限制
            relation_types: 限制关系类型

        Returns:
            上游节点列表（按距离排序）
        """
        return self._traverse(
            node_id,
            direction="upstream",
            depth=depth,
            relation_types=relation_types,
        )

    def get_downstream(
        self,
        node_id: str,
        depth: int = -1,
        relation_types: Optional[List[LineageRelationType]] = None,
    ) -> List[LineageNode]:
        """
        获取下游影响

        Args:
            node_id: 节点ID
            depth: 查询深度，-1表示不限制
            relation_types: 限制关系类型

        Returns:
            下游节点列表（按距离排序）
        """
        return self._traverse(
            node_id,
            direction="downstream",
            depth=depth,
            relation_types=relation_types,
        )

    def get_full_lineage(self, node_id: str) -> Dict:
        """
        获取完整血缘（上游+下游）

        Returns:
            {
                "node": LineageNode,
                "upstream": List[LineageNode],
                "downstream": List[LineageNode],
                "paths": List[List[str]]  # 完整路径
            }
        """
        node = self._get_node_by_id(node_id)
        if not node:
            return {"error": f"节点不存在: {node_id}"}

        upstream = self.get_upstream(node_id)
        downstream = self.get_downstream(node_id)

        return {
            "node": node,
            "upstream": upstream,
            "downstream": downstream,
            "upstream_count": len(upstream),
            "downstream_count": len(downstream),
        }

    def impact_analysis(self, node_id: str) -> ImpactAnalysisResult:
        """
        影响分析

        分析修改某个节点会影响哪些下游节点
        """
        node = self._get_node_by_id(node_id)
        if not node:
            raise ValueError(f"节点不存在: {node_id}")

        upstream = self.get_upstream(node_id)
        downstream = self.get_downstream(node_id)

        # 直接依赖（第一层下游）
        direct = self.get_downstream(node_id, depth=1)

        return ImpactAnalysisResult(
            node_id=node_id,
            upstream=upstream,
            downstream=downstream,
            direct_dependents=direct,
            all_dependents=downstream,
        )

    def find_common_sources(self, node_ids: List[str]) -> List[LineageNode]:
        """
        查找多个节点的共同上游

        用于分析数据一致性问题的根因
        """
        all_sources = []

        for node_id in node_ids:
            upstream = self.get_upstream(node_id)
            source_ids = {n.id for n in upstream}
            all_sources.append(source_ids)

        if not all_sources:
            return []

        # 取交集
        common_ids = all_sources[0]
        for sources in all_sources[1:]:
            common_ids &= sources

        return [self._get_node_by_id(nid) for nid in common_ids if self._get_node_by_id(nid)]

    def get_orphan_nodes(self, namespace: Optional[str] = None) -> List[LineageNode]:
        """
        获取孤立节点（无血缘关系）

        用于数据治理，发现未被追踪的数据
        """
        where_clause = ""
        params = ()
        if namespace:
            where_clause = "WHERE namespace = %s"
            params = (namespace,)

        sql = f"""
            SELECT n.* FROM data_lineage_nodes n
            {where_clause}
            AND NOT EXISTS (
                SELECT 1 FROM data_lineage_edges e
                WHERE e.source_id = n.id OR e.target_id = n.id
            )
        """

        results = DatabaseManager.fetchall(self.db_name, sql, params)
        return [self.tracker._row_to_node(r) for r in results]

    def get_table_dependencies(self, table_name: str, namespace: str = "default") -> Dict:
        """
        获取表的依赖关系（便捷方法）

        Returns:
            {
                "table": table_name,
                "sources": [...],
                "targets": [...],
                "logic": [...]
            }
        """
        node = self.tracker.get_node_by_name(table_name, namespace, LineageNodeType.TABLE)
        if not node:
            return {"error": f"表不存在: {table_name}"}

        upstream = self.get_upstream(node.id)
        downstream = self.get_downstream(node.id)

        # 获取转换逻辑
        sql = """
            SELECT transform_logic FROM data_lineage_edges
            WHERE target_id = %s AND transform_logic IS NOT NULL
        """
        results = DatabaseManager.fetchall(self.db_name, sql, (node.id,))
        logic = [r["transform_logic"] for r in results if r["transform_logic"]]

        return {
            "table": table_name,
            "sources": [n.name for n in upstream],
            "targets": [n.name for n in downstream],
            "logic": logic,
        }

    def search_nodes(
        self,
        keyword: str,
        node_type: Optional[LineageNodeType] = None,
        namespace: Optional[str] = None,
    ) -> List[LineageNode]:
        """搜索节点"""
        conditions = ["(name LIKE %s OR description LIKE %s)"]
        params = [f"%{keyword}%", f"%{keyword}%"]

        if node_type:
            conditions.append("node_type = %s")
            params.append(node_type.value)

        if namespace:
            conditions.append("namespace = %s")
            params.append(namespace)

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT * FROM data_lineage_nodes
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT 100
        """

        results = DatabaseManager.fetchall(self.db_name, sql, params)
        return [self.tracker._row_to_node(r) for r in results]

    def _get_node_by_id(self, node_id: str) -> Optional[LineageNode]:
        """通过ID获取节点"""
        sql = "SELECT * FROM data_lineage_nodes WHERE id = %s"
        result = DatabaseManager.fetchone(self.db_name, sql, (node_id,))
        if result:
            return self.tracker._row_to_node(result)
        return None

    def _traverse(
        self,
        start_node_id: str,
        direction: str,
        depth: int = -1,
        relation_types: Optional[List[LineageRelationType]] = None,
    ) -> List[LineageNode]:
        """
        遍历血缘图

        Args:
            start_node_id: 起始节点ID
            direction: upstream 或 downstream
            depth: 遍历深度，-1为不限制
            relation_types: 限制关系类型
        """
        visited: Set[str] = set()
        result: List[LineageNode] = []
        queue: deque = deque([(start_node_id, 0)])

        type_filter = None
        if relation_types:
            type_filter = {t.value for t in relation_types}

        while queue:
            current_id, current_depth = queue.popleft()

            if current_id in visited:
                continue
            visited.add(current_id)

            # 跳过起始节点本身
            if current_id != start_node_id:
                node = self._get_node_by_id(current_id)
                if node:
                    result.append(node)

            # 检查深度限制
            if depth != -1 and current_depth >= depth:
                continue

            # 获取下一层节点
            next_nodes = self._get_neighbors(
                current_id, direction, type_filter
            )

            for next_id in next_nodes:
                if next_id not in visited:
                    queue.append((next_id, current_depth + 1))

        return result

    def _get_neighbors(
        self,
        node_id: str,
        direction: str,
        type_filter: Optional[Set[str]] = None,
    ) -> List[str]:
        """获取相邻节点"""
        if direction == "upstream":
            # 上游：查找以当前节点为目标的边
            sql = "SELECT source_id FROM data_lineage_edges WHERE target_id = %s"
        else:
            # 下游：查找以当前节点为源的边
            sql = "SELECT target_id FROM data_lineage_edges WHERE source_id = %s"

        params = [node_id]

        if type_filter:
            sql += " AND relation_type IN (%s)"
            params.append(",".join(f"'{t}'" for t in type_filter))

        results = DatabaseManager.fetchall(self.db_name, sql, params)

        if direction == "upstream":
            return [r["source_id"] for r in results]
        return [r["target_id"] for r in results]

    def get_lineage_statistics(self) -> Dict:
        """获取血缘统计信息"""
        # 节点统计
        node_sql = """
            SELECT node_type, COUNT(*) as count
            FROM data_lineage_nodes
            GROUP BY node_type
        """
        node_stats = DatabaseManager.fetchall(self.db_name, node_sql)

        # 关系统计
        edge_sql = """
            SELECT relation_type, COUNT(*) as count
            FROM data_lineage_edges
            GROUP BY relation_type
        """
        edge_stats = DatabaseManager.fetchall(self.db_name, edge_sql)

        # 总节点数
        total_nodes = sum(r["count"] for r in node_stats)
        total_edges = sum(r["count"] for r in edge_stats)

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_breakdown": {r["node_type"]: r["count"] for r in node_stats},
            "edge_breakdown": {r["relation_type"]: r["count"] for r in edge_stats},
            "average_fan_in": total_edges / total_nodes if total_nodes > 0 else 0,
            "average_fan_out": total_edges / total_nodes if total_nodes > 0 else 0,
        }
