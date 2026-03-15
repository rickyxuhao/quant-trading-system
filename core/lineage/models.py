"""
数据血缘模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import uuid


class LineageNodeType(Enum):
    """节点类型"""
    DATA_SOURCE = "data_source"          # 数据源（Tushare、文件等）
    TABLE = "table"                       # 数据库表
    VIEW = "view"                         # 视图
    PIPELINE = "pipeline"                 # 数据处理管道
    SCRIPT = "script"                     # 脚本
    API = "api"                           # API接口
    FILE = "file"                         # 文件
    REPORT = "report"                     # 报告


class LineageRelationType(Enum):
    """血缘关系类型"""
    DERIVED_FROM = "derived_from"         # 派生自
    POPULATED_BY = "populated_by"         # 由...填充
    AGGREGATED_FROM = "aggregated_from"   # 聚合自
    JOINED_WITH = "joined_with"           # 与...关联
    TRANSFORMED_BY = "transformed_by"     # 由...转换
    PRODUCED_BY = "produced_by"           # 由...生成
    DEPENDS_ON = "depends_on"             # 依赖于


@dataclass
class NodeMetadata:
    """节点元数据"""
    schema: Optional[str] = None          # 表结构/字段定义
    row_count: Optional[int] = None       # 行数
    last_update: Optional[str] = None     # 最后更新时间
    owner: Optional[str] = None           # 负责人
    description: Optional[str] = None     # 描述
    tags: List[str] = field(default_factory=list)  # 标签
    extra: Dict[str, Any] = field(default_factory=dict)  # 额外信息

    def to_dict(self) -> Dict:
        return {
            "schema": self.schema,
            "row_count": self.row_count,
            "last_update": self.last_update,
            "owner": self.owner,
            "description": self.description,
            "tags": self.tags,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "NodeMetadata":
        return cls(
            schema=data.get("schema"),
            row_count=data.get("row_count"),
            last_update=data.get("last_update"),
            owner=data.get("owner"),
            description=data.get("description"),
            tags=data.get("tags", []),
            extra=data.get("extra", {}),
        )


@dataclass
class LineageNode:
    """血缘节点"""
    id: str
    name: str
    node_type: LineageNodeType
    namespace: str                          # 命名空间（如数据库名、项目名）
    metadata: NodeMetadata = field(default_factory=NodeMetadata)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "namespace": self.namespace,
            "metadata": self.metadata.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LineageNode":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            node_type=LineageNodeType(data["node_type"]),
            namespace=data.get("namespace", "default"),
            metadata=NodeMetadata.from_dict(data.get("metadata", {})),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )

    @property
    def qualified_name(self) -> str:
        """完全限定名"""
        return f"{self.namespace}.{self.name}"


@dataclass
class LineageEdge:
    """血缘边（关系）"""
    id: str
    source_id: str                          # 源节点ID
    target_id: str                          # 目标节点ID
    relation_type: LineageRelationType      # 关系类型
    transform_logic: Optional[str] = None   # 转换逻辑（如SQL、代码片段）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "transform_logic": self.transform_logic,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LineageEdge":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=LineageRelationType(data.get("relation_type", "derived_from")),
            transform_logic=data.get("transform_logic"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DataLineageRecord:
    """数据血缘记录（一次完整的数据流转）"""
    id: str
    execution_id: str                       # 执行ID（用于追踪某次具体执行）
    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    status: str = "running"                 # running, success, failed
    error_message: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DataLineageRecord":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            execution_id=data.get("execution_id", str(uuid.uuid4())),
            nodes=[LineageNode.from_dict(n) for n in data.get("nodes", [])],
            edges=[LineageEdge.from_dict(e) for e in data.get("edges", [])],
            start_time=data.get("start_time", datetime.now().isoformat()),
            end_time=data.get("end_time"),
            status=data.get("status", "running"),
            error_message=data.get("error_message"),
        )


@dataclass
class ImpactAnalysisResult:
    """影响分析结果"""
    node_id: str
    upstream: List[LineageNode]             # 上游依赖
    downstream: List[LineageNode]           # 下游影响
    direct_dependents: List[LineageNode]    # 直接依赖
    all_dependents: List[LineageNode]       # 所有依赖（递归）
