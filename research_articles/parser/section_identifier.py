"""
章节识别模块 - 基于字体大小和关键词匹配识别论文章节结构

识别章节类型：
- Abstract/摘要
- Introduction/引言
- Methodology/方法论
- Experiments/实验
- Results/结果
- Conclusion/结论
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.logger import get_logger

from .pdf_extractor import PDFContent, TextBlock

logger = get_logger(__name__)


class SectionType(Enum):
    """章节类型枚举"""
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    RELATED_WORK = "related_work"
    METHODOLOGY = "methodology"
    EXPERIMENTS = "experiments"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    REFERENCES = "references"
    APPENDIX = "appendix"
    UNKNOWN = "unknown"


@dataclass
class Section:
    """章节数据结构"""
    section_type: SectionType
    title: str
    page_start: int
    page_end: Optional[int] = None
    content: str = ""
    subsections: list["Section"] = field(default_factory=list)


class SectionIdentifier:
    """章节识别器"""

    # 章节关键词映射
    SECTION_KEYWORDS: dict[SectionType, list[str]] = {
        SectionType.ABSTRACT: [
            "abstract", "摘要", "概要", "overview"
        ],
        SectionType.INTRODUCTION: [
            "introduction", "引言", "绪论", "前言", "intro",
            "1. introduction", "i. introduction"
        ],
        SectionType.RELATED_WORK: [
            "related work", "相关工作", "文献综述", "literature review",
            "background", "背景", "related works"
        ],
        SectionType.METHODOLOGY: [
            "methodology", "方法", "方法论", "模型", "model",
            "methods", "approach", "framework", "algorithm",
            "3. methodology", "iii. methodology"
        ],
        SectionType.EXPERIMENTS: [
            "experiments", "experiment", "实验", "实证分析",
            "empirical analysis", "experimental setup",
            "4. experiments", "iv. experiments"
        ],
        SectionType.RESULTS: [
            "results", "结果", "findings", "performance",
            "5. results", "v. results"
        ],
        SectionType.DISCUSSION: [
            "discussion", "讨论", "分析讨论"
        ],
        SectionType.CONCLUSION: [
            "conclusion", "conclusions", "结论", "总结", "结束语",
            "6. conclusion", "vi. conclusion", "concluding remarks"
        ],
        SectionType.REFERENCES: [
            "references", "参考文献", "bibliography", "refs"
        ],
        SectionType.APPENDIX: [
            "appendix", "附录", "appendices", "supplementary"
        ],
    }

    # 正则表达式模式
    SECTION_PATTERNS: dict[SectionType, list[str]] = {
        SectionType.ABSTRACT: [
            r"^\s*(?:abstract|摘要)[:：]?\s*",
            r"^\s*A[Bb][Ss][Tt][Rr][Aa][Cc][Tt]\s*"
        ],
        SectionType.INTRODUCTION: [
            r"^\s*(?:1[.\s]+|I[.\s]+)?\s*(?:introduction|引言|绪论)[:：]?\s*",
            r"^\s*1\.\s+Introduction\s*"
        ],
        SectionType.METHODOLOGY: [
            r"^\s*(?:3[.\s]+|III[.\s]+)?\s*(?:methodology|methods?|方法|方法论|模型)[:：]?\s*",
            r"^\s*3\.\s+(?:Methodology|Methods?)\s*",
            r"^\s*Model\s+(?:Architecture|Design)\s*"
        ],
        SectionType.EXPERIMENTS: [
            r"^\s*(?:4[.\s]+|IV[.\s]+)?\s*(?:experiments?|实验|实证)[:：]?\s*",
            r"^\s*4\.\s+Experiments?\s*",
            r"^\s*Empirical\s+(?:Analysis|Study)\s*"
        ],
        SectionType.RESULTS: [
            r"^\s*(?:5[.\s]+|V[.\s]+)?\s*(?:results?|结果|发现)[:：]?\s*",
            r"^\s*5\.\s+Results?\s*"
        ],
        SectionType.CONCLUSION: [
            r"^\s*(?:6[.\s]+|VI[.\s]+)?\s*(?:conclusion|conclusions|结论|总结)[:：]?\s*",
            r"^\s*6\.\s+Conclusions?\s*",
            r"^\s*Concluding\s+Remarks\s*"
        ],
    }

    def __init__(self, content: PDFContent):
        self.content = content
        self.sections: list[Section] = []
        self._header_blocks: list[TextBlock] = []

    def identify(self) -> list[Section]:
        """
        执行章节识别

        Returns:
            识别出的章节列表
        """
        logger.info("开始识别论文章节结构")

        # 收集可能的标题块
        self._collect_header_blocks()

        # 识别各章节
        self._identify_sections()

        # 确定章节页码范围
        self._determine_page_ranges()

        # 提取章节内容
        self._extract_section_contents()

        logger.info(f"识别到 {len(self.sections)} 个主要章节")
        return self.sections

    def _collect_header_blocks(self) -> None:
        """收集可能的标题块"""
        for block in self.content.text_blocks:
            # 标题块的特征：字体较大或加粗
            if block.block_type == "header" or block.font_size > 12:
                self._header_blocks.append(block)

        # 按页码和位置排序
        self._header_blocks.sort(key=lambda b: (b.page_num, b.y_position))

    def _identify_sections(self) -> None:
        """识别各章节"""
        found_sections: dict[SectionType, Section] = {}

        for block in self._header_blocks:
            section_type = self._classify_header(block.text)

            if section_type != SectionType.UNKNOWN:
                # 避免重复识别同一类型
                if section_type not in found_sections:
                    section = Section(
                        section_type=section_type,
                        title=block.text.strip(),
                        page_start=block.page_num
                    )
                    found_sections[section_type] = section
                    self.sections.append(section)
                    logger.debug(f"识别到章节: {section_type.value} - {block.text}")

        # 按页码排序
        self.sections.sort(key=lambda s: s.page_start)

    def _classify_header(self, text: str) -> SectionType:
        """根据文本分类标题类型"""
        text_lower = text.lower().strip()

        # 使用正则表达式匹配
        for section_type, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, text_lower):
                    return section_type

        # 使用关键词匹配
        for section_type, keywords in self.SECTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return section_type

        return SectionType.UNKNOWN

    def _determine_page_ranges(self) -> None:
        """确定各章节的页码范围"""
        for i, section in enumerate(self.sections):
            if i < len(self.sections) - 1:
                next_section = self.sections[i + 1]
                section.page_end = next_section.page_start
            else:
                # 最后一个章节到文档末尾
                section.page_end = self.content.total_pages + 1

    def _extract_section_contents(self) -> None:
        """提取各章节的内容"""
        for section in self.sections:
            section_blocks = [
                b for b in self.content.text_blocks
                if section.page_start <= b.page_num < (section.page_end or float('inf'))
            ]

            # 排除标题块本身
            content_blocks = [
                b for b in section_blocks
                if b.block_type != "header" or not self._is_section_header(b.text, section.section_type)
            ]

            # 按位置排序并合并文本
            content_blocks.sort(key=lambda b: (b.page_num, b.y_position))
            section.content = "\n".join(b.text for b in content_blocks)

    def _is_section_header(self, text: str, section_type: SectionType) -> bool:
        """判断文本是否为指定类型的章节标题"""
        patterns = self.SECTION_PATTERNS.get(section_type, [])
        text_lower = text.lower().strip()

        for pattern in patterns:
            if re.match(pattern, text_lower):
                return True

        return False

    def get_section(self, section_type: SectionType) -> Optional[Section]:
        """获取指定类型的章节"""
        for section in self.sections:
            if section.section_type == section_type:
                return section
        return None

    def get_methodology_content(self) -> str:
        """获取方法论章节内容"""
        section = self.get_section(SectionType.METHODOLOGY)
        return section.content if section else ""

    def get_experiments_content(self) -> str:
        """获取实验章节内容"""
        section = self.get_section(SectionType.EXPERIMENTS)
        return section.content if section else ""

    def get_results_content(self) -> str:
        """获取结果章节内容"""
        section = self.get_section(SectionType.RESULTS)
        return section.content if section else ""

    def get_structure_summary(self) -> dict:
        """获取章节结构摘要"""
        return {
            "total_sections": len(self.sections),
            "sections": [
                {
                    "type": s.section_type.value,
                    "title": s.title,
                    "page_start": s.page_start,
                    "page_end": s.page_end,
                    "content_length": len(s.content)
                }
                for s in self.sections
            ]
        }


class SectionHierarchyBuilder:
    """章节层次结构构建器 - 识别子章节"""

    # 子章节编号模式
    SUBSECTION_PATTERNS = [
        r"^\s*(\d+\.\d+)\s+(.+)",  # 1.1, 2.3等
        r"^\s*(\d+\.\d+\.\d+)\s+(.+)",  # 1.1.1, 2.3.1等
        r"^\s*([A-D]\.)\s+(.+)",  # A., B.等
    ]

    def __init__(self, content: PDFContent):
        self.content = content

    def build_hierarchy(self, sections: list[Section]) -> list[Section]:
        """
        构建章节层次结构

        Args:
            sections: 已识别的章节列表

        Returns:
            带有子章节层次的章节列表
        """
        for section in sections:
            subsections = self._find_subsections(section)
            section.subsections = subsections

        return sections

    def _find_subsections(self, parent: Section) -> list[Section]:
        """查找指定章节的子章节"""
        subsections: list[Section] = []

        # 获取该章节的文本块
        section_blocks = [
            b for b in self.content.text_blocks
            if parent.page_start <= b.page_num < (parent.page_end or float('inf'))
        ]

        for block in section_blocks:
            if block.block_type != "header":
                continue

            # 检查是否匹配子章节模式
            for pattern in self.SUBSECTION_PATTERNS:
                match = re.match(pattern, block.text)
                if match:
                    subsection = Section(
                        section_type=SectionType.UNKNOWN,
                        title=block.text.strip(),
                        page_start=block.page_num
                    )
                    subsections.append(subsection)
                    break

        return subsections


def identify_sections(content: PDFContent) -> list[Section]:
    """
    便捷函数：识别PDF内容的章节结构

    Args:
        content: PDFContent对象

    Returns:
        章节列表
    """
    identifier = SectionIdentifier(content)
    sections = identifier.identify()

    # 构建层次结构
    hierarchy_builder = SectionHierarchyBuilder(content)
    return hierarchy_builder.build_hierarchy(sections)
