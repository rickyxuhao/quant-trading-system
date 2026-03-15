"""
数据血缘追踪器

自动追踪数据从源头到目的的完整流转过程
"""
import json
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from functools import wraps

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from core.lineage.models import (
    LineageNode,
    LineageEdge,
    LineageNodeType,
    LineageRelationType,
    DataLineageRecord,
    NodeMetadata,
)

logger = get_logger(__name__)


class DataLineageTracker:
    """数据血缘追踪器"""

    def __init__(self, db_name: str = "interface"):
        self.db_name = db_name
        self._ensure_tables()

    def _ensure_tables(self):
        """确保血缘表存在"""
        # 节点表
        sql_nodes = """
        CREATE TABLE IF NOT EXISTS data_lineage_nodes (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            node_type VARCHAR(50) NOT NULL,
            namespace VARCHAR(100) NOT NULL DEFAULT 'default',
            schema_info TEXT,
            row_count BIGINT,
            last_update VARCHAR(20),
            owner VARCHAR(100),
            description TEXT,
            tags JSON,
            extra JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_namespace_name (namespace, name, node_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='血缘节点表'
        """

        # 边表（关系）
        sql_edges = """
        CREATE TABLE IF NOT EXISTS data_lineage_edges (
            id VARCHAR(64) PRIMARY KEY,
            source_id VARCHAR(64) NOT NULL,
            target_id VARCHAR(64) NOT NULL,
            relation_type VARCHAR(50) NOT NULL,
            transform_logic TEXT,
            metadata JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES data_lineage_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY (target_id) REFERENCES data_lineage_nodes(id) ON DELETE CASCADE,
            UNIQUE KEY uk_source_target (source_id, target_id, relation_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='血缘关系表'
        """

        # 执行记录表
        sql_executions = """
        CREATE TABLE IF NOT EXISTS data_lineage_executions (
            id VARCHAR(64) PRIMARY KEY,
            execution_id VARCHAR(64) NOT NULL,
            node_ids JSON,
            edge_ids JSON,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP NULL,
            status VARCHAR(20) DEFAULT 'running',
            error_message TEXT,
            INDEX idx_execution (execution_id),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='血缘执行记录表'
        """

        try:
            DatabaseManager.execute(self.db_name, sql_nodes)
            DatabaseManager.execute(self.db_name, sql_edges)
            DatabaseManager.execute(self.db_name, sql_executions)
            logger.info("数据血缘表初始化完成")
        except Exception as e:
            logger.error(f"创建血缘表失败: {e}")

    def register_node(
        self,
        name: str,
        node_type: LineageNodeType,
        namespace: str = "default",
        metadata: Optional[NodeMetadata] = None,
    ) -> LineageNode:
        """
        注册血缘节点

        Args:
            name: 节点名称（如表名、脚本名）
            node_type: 节点类型
            namespace: 命名空间
            metadata: 元数据

        Returns:
            LineageNode 对象
        """
        node = LineageNode(
            id=str(uuid.uuid4()),
            name=name,
            node_type=node_type,
            namespace=namespace,
            metadata=metadata or NodeMetadata(),
        )

        sql = """
            INSERT INTO data_lineage_nodes
            (id, name, node_type, namespace, schema_info, row_count, last_update,
             owner, description, tags, extra)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            schema_info = VALUES(schema_info),
            row_count = VALUES(row_count),
            last_update = VALUES(last_update),
            owner = VALUES(owner),
            description = VALUES(description),
            tags = VALUES(tags),
            extra = VALUES(extra),
            updated_at = CURRENT_TIMESTAMP
        """

        meta = node.metadata
        params = (
            node.id,
            node.name,
            node.node_type.value,
            node.namespace,
            meta.schema,
            meta.row_count,
            meta.last_update,
            meta.owner,
            meta.description,
            json.dumps(meta.tags, ensure_ascii=False),
            json.dumps(meta.extra, ensure_ascii=False),
        )

        try:
            DatabaseManager.execute(self.db_name, sql, params)
            logger.debug(f"注册血缘节点: {node.qualified_name}")
        except Exception as e:
            logger.error(f"注册节点失败: {e}")

        return node

    def register_edge(
        self,
        source: LineageNode,
        target: LineageNode,
        relation_type: LineageRelationType,
        transform_logic: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> LineageEdge:
        """
        注册血缘关系

        Args:
            source: 源节点
            target: 目标节点
            relation_type: 关系类型
            transform_logic: 转换逻辑（如SQL）
            metadata: 额外元数据

        Returns:
            LineageEdge 对象
        """
        edge = LineageEdge(
            id=str(uuid.uuid4()),
            source_id=source.id,
            target_id=target.id,
            relation_type=relation_type,
            transform_logic=transform_logic,
            metadata=metadata or {},
        )

        sql = """
            INSERT INTO data_lineage_edges
            (id, source_id, target_id, relation_type, transform_logic, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            transform_logic = VALUES(transform_logic),
            metadata = VALUES(metadata)
        """

        params = (
            edge.id,
            edge.source_id,
            edge.target_id,
            edge.relation_type.value,
            edge.transform_logic,
            json.dumps(edge.metadata, ensure_ascii=False),
        )

        try:
            DatabaseManager.execute(self.db_name, sql, params)
            logger.debug(f"注册血缘关系: {source.name} -> {target.name}")
        except Exception as e:
            logger.error(f"注册关系失败: {e}")

        return edge

    def record_execution(
        self,
        execution_id: str,
        nodes: List[LineageNode],
        edges: List[LineageEdge],
        status: str = "running",
    ) -> str:
        """记录执行"""
        record_id = str(uuid.uuid4())

        sql = """
            INSERT INTO data_lineage_executions
            (id, execution_id, node_ids, edge_ids, status)
            VALUES (%s, %s, %s, %s, %s)
        """

        params = (
            record_id,
            execution_id,
            json.dumps([n.id for n in nodes]),
            json.dumps([e.id for e in edges]),
            status,
        )

        try:
            DatabaseManager.execute(self.db_name, sql, params)
        except Exception as e:
            logger.error(f"记录执行失败: {e}")

        return record_id

    def finish_execution(
        self,
        record_id: str,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        """完成执行记录"""
        sql = """
            UPDATE data_lineage_executions
            SET status = %s, end_time = CURRENT_TIMESTAMP, error_message = %s
            WHERE id = %s
        """

        try:
            DatabaseManager.execute(self.db_name, sql, (status, error_message, record_id))
        except Exception as e:
            logger.error(f"更新执行记录失败: {e}")

    def get_node_by_name(
        self,
        name: str,
        namespace: str = "default",
        node_type: Optional[LineageNodeType] = None,
    ) -> Optional[LineageNode]:
        """通过名称获取节点"""
        if node_type:
            sql = """
                SELECT * FROM data_lineage_nodes
                WHERE name = %s AND namespace = %s AND node_type = %s
                LIMIT 1
            """
            params = (name, namespace, node_type.value)
        else:
            sql = """
                SELECT * FROM data_lineage_nodes
                WHERE name = %s AND namespace = %s
                LIMIT 1
            """
            params = (name, namespace)

        result = DatabaseManager.fetchone(self.db_name, sql, params)
        if result:
            return self._row_to_node(result)
        return None

    def _row_to_node(self, row: Dict) -> LineageNode:
        """数据库行转节点对象"""
        metadata = NodeMetadata(
            schema=row.get("schema_info"),
            row_count=row.get("row_count"),
            last_update=row.get("last_update"),
            owner=row.get("owner"),
            description=row.get("description"),
            tags=json.loads(row["tags"]) if row.get("tags") else [],
            extra=json.loads(row["extra"]) if row.get("extra") else {},
        )

        return LineageNode(
            id=row["id"],
            name=row["name"],
            node_type=LineageNodeType(row["node_type"]),
            namespace=row["namespace"],
            metadata=metadata,
            created_at=row["created_at"].isoformat() if row.get("created_at") else None,
            updated_at=row["updated_at"].isoformat() if row.get("updated_at") else None,
        )

    @contextmanager
    def trace_execution(self, execution_name: str, namespace: str = "default"):
        """
        执行追踪上下文管理器

        Usage:
            with tracker.trace_execution("daily_sync") as trace:
                source = trace.add_source("tushare_api")
                target = trace.add_table("t_stock_dailymarketdata")
                trace.add_relation(source, target, LineageRelationType.POPULATED_BY)
        """
        execution_id = str(uuid.uuid4())
        nodes: List[LineageNode] = []
        edges: List[LineageEdge] = []

        class ExecutionTrace:
            def __init__(self, tracker: DataLineageTracker):
                self.tracker = tracker
                self.nodes = nodes
                self.edges = edges

            def add_source(self, name: str, metadata: Optional[NodeMetadata] = None) -> LineageNode:
                node = self.tracker.register_node(name, LineageNodeType.DATA_SOURCE, namespace, metadata)
                self.nodes.append(node)
                return node

            def add_table(self, name: str, metadata: Optional[NodeMetadata] = None) -> LineageNode:
                node = self.tracker.register_node(name, LineageNodeType.TABLE, namespace, metadata)
                self.nodes.append(node)
                return node

            def add_pipeline(self, name: str, metadata: Optional[NodeMetadata] = None) -> LineageNode:
                node = self.tracker.register_node(name, LineageNodeType.PIPELINE, namespace, metadata)
                self.nodes.append(node)
                return node

            def add_script(self, name: str, metadata: Optional[NodeMetadata] = None) -> LineageNode:
                node = self.tracker.register_node(name, LineageNodeType.SCRIPT, namespace, metadata)
                self.nodes.append(node)
                return node

            def add_relation(
                self,
                source: LineageNode,
                target: LineageNode,
                relation_type: LineageRelationType,
                transform_logic: Optional[str] = None,
            ) -> LineageEdge:
                edge = self.tracker.register_edge(source, target, relation_type, transform_logic)
                self.edges.append(edge)
                return edge

        trace = ExecutionTrace(self)
        record_id = self.record_execution(execution_id, nodes, edges, "running")

        try:
            yield trace
            self.finish_execution(record_id, "success")
        except Exception as e:
            self.finish_execution(record_id, "failed", str(e))
            raise


def trace_sync_task(func: Callable) -> Callable:
    """
    同步任务血缘追踪装饰器

    Usage:
        @trace_sync_task
        def sync_daily_data():
            # 同步逻辑
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        tracker = DataLineageTracker()
        task_name = func.__name__

        with tracker.trace_execution(task_name, namespace="sync_tasks") as trace:
            # 添加脚本节点
            script_node = trace.add_script(task_name)

            # 执行原函数
            result = func(*args, **kwargs)

            # 如果函数返回了节点信息，建立关系
            if isinstance(result, dict):
                if "source" in result and "target" in result:
                    source = trace.add_source(result["source"])
                    target = trace.add_table(result["target"])
                    trace.add_relation(source, target, LineageRelationType.POPULATED_BY, result.get("logic"))

            return result

    return wrapper


def trace_dataflow(source: str, target: str, transform: Optional[str] = None):
    """
    简易数据流追踪装饰器

    Usage:
        @trace_dataflow("tushare_api", "t_stock_dailymarketdata")
        def sync_daily():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = DataLineageTracker()

            with tracker.trace_execution(func.__name__) as trace:
                src_node = trace.add_source(source)
                tgt_node = trace.add_table(target)
                trace.add_relation(src_node, tgt_node, LineageRelationType.POPULATED_BY, transform)

                return func(*args, **kwargs)

        return wrapper
    return decorator
