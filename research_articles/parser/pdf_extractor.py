"""
PDF文本提取模块 - 使用pdfplumber进行结构化文本提取

支持：
- 分层提取：标题、摘要、正文、表格、公式
- 保留页面布局和字体信息
- 复杂学术论文排版处理
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pdfplumber

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TextBlock:
    """文本块数据结构"""
    text: str
    page_num: int
    y_position: float
    font_size: float = 0.0
    font_name: str = ""
    is_bold: bool = False
    block_type: str = "text"  # text, header, footer, table, formula


@dataclass
class ExtractedTable:
    """提取的表格数据结构"""
    page_num: int
    table_data: list[list[str]]
    bbox: tuple[float, float, float, float]


@dataclass
class PDFContent:
    """PDF内容完整结构"""
    # 元数据
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)

    # 正文内容
    text_blocks: list[TextBlock] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)

    # 章节映射 {章节名: 起始页码}
    section_map: dict[str, int] = field(default_factory=dict)

    # 原始统计信息
    total_pages: int = 0
    word_count: int = 0

    def get_full_text(self) -> str:
        """获取完整文本（按页面顺序）"""
        sorted_blocks = sorted(
            self.text_blocks,
            key=lambda b: (b.page_num, b.y_position)
        )
        return "\n".join(block.text for block in sorted_blocks)

    def get_section_text(self, section_name: str) -> str:
        """获取特定章节的文本"""
        if section_name not in self.section_map:
            return ""

        start_page = self.section_map[section_name]
        section_blocks = [
            b for b in self.text_blocks
            if b.page_num >= start_page
        ]

        # 找到下一个章节的起始位置
        next_page = float('inf')
        for name, page in self.section_map.items():
            if page > start_page and page < next_page:
                next_page = page

        if next_page != float('inf'):
            section_blocks = [
                b for b in section_blocks
                if b.page_num < next_page
            ]

        sorted_blocks = sorted(section_blocks, key=lambda b: b.y_position)
        return "\n".join(block.text for block in sorted_blocks)


class PDFExtractor:
    """PDF提取器主类"""

    # 学术论文常见章节标题模式
    SECTION_PATTERNS = [
        r"^(?:Abstract|摘要)",
        r"^(?:1\.\s*|I\.\s*|)\s*(?:Introduction|引言|绪论)",
        r"^(?:2\.\s*|II\.\s*|)\s*(?:Related Work|相关工作|文献综述)",
        r"^(?:3\.\s*|III\.\s*|)\s*(?:Methodology|方法|方法论|模型)",
        r"^(?:4\.\s*|IV\.\s*|)\s*(?:Experiments?|实验|实证分析)",
        r"^(?:5\.\s*|V\.\s*|)\s*(?:Results?|结果)",
        r"^(?:6\.\s*|VI\.\s*|)\s*(?:Conclusion|结论|总结)",
        r"^(?:References?|参考文献)",
        r"^(?:Appendix|附录)",
    ]

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.content = PDFContent()
        self._font_size_stats: dict[float, int] = {}

    def extract(self) -> PDFContent:
        """
        执行完整的PDF提取流程

        Returns:
            PDFContent: 结构化的PDF内容对象
        """
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {self.pdf_path}")

        logger.info(f"开始提取PDF: {self.pdf_path}")

        with pdfplumber.open(self.pdf_path) as pdf:
            self.content.total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, 1):
                self._process_page(page, page_num)

        # 后处理：识别标题、作者、摘要
        self._extract_metadata()
        self._identify_sections()
        self._calculate_word_count()

        logger.info(
            f"PDF提取完成: {self.content.total_pages}页, "
            f"{len(self.content.text_blocks)}文本块, "
            f"{len(self.content.tables)}表格"
        )

        return self.content

    def _process_page(self, page: pdfplumber.page.Page, page_num: int) -> None:
        """处理单个页面"""
        # 提取文本块（带字体信息）
        words = page.extract_words(
            keep_blank_chars=True,
            x_tolerance=3,
            y_tolerance=3
        )

        if words:
            self._process_text_blocks(words, page_num)

        # 提取表格
        tables = page.extract_tables()
        for table in tables:
            if table and len(table) > 1:
                self.content.tables.append(ExtractedTable(
                    page_num=page_num,
                    table_data=table,
                    bbox=(0, 0, 0, 0)  # 简化处理
                ))

    def _process_text_blocks(
        self,
        words: list[dict[str, Any]],
        page_num: int
    ) -> None:
        """处理文本块，保留字体信息"""
        current_line_y = None
        current_line_text = []
        current_line_fonts = []

        for word in words:
            y = word.get("top", 0)
            text = word.get("text", "")
            font_size = word.get("size", 0)
            font_name = word.get("fontname", "")

            # 统计字体大小分布
            self._font_size_stats[font_size] = (
                self._font_size_stats.get(font_size, 0) + 1
            )

            # 同一行的文本（y坐标接近）
            if current_line_y is None or abs(y - current_line_y) < 3:
                current_line_y = y
                current_line_text.append(text)
                current_line_fonts.append((font_size, font_name))
            else:
                # 保存当前行
                self._save_text_block(
                    current_line_text,
                    current_line_fonts,
                    page_num,
                    current_line_y
                )
                # 开始新行
                current_line_y = y
                current_line_text = [text]
                current_line_fonts = [(font_size, font_name)]

        # 保存最后一行
        if current_line_text:
            self._save_text_block(
                current_line_text,
                current_line_fonts,
                page_num,
                current_line_y or 0
            )

    def _save_text_block(
        self,
        texts: list[str],
        fonts: list[tuple[float, str]],
        page_num: int,
        y_position: float
    ) -> None:
        """保存文本块"""
        full_text = " ".join(texts).strip()
        if not full_text:
            return

        # 计算平均字体大小
        avg_font_size = sum(f[0] for f in fonts) / len(fonts) if fonts else 0
        font_name = fonts[0][1] if fonts else ""

        # 判断是否粗体
        is_bold = "Bold" in font_name or "bold" in font_name.lower()

        # 判断块类型
        block_type = "text"
        if avg_font_size > 14 or is_bold:
            block_type = "header"
        elif self._is_likely_formula(full_text):
            block_type = "formula"

        block = TextBlock(
            text=full_text,
            page_num=page_num,
            y_position=y_position,
            font_size=avg_font_size,
            font_name=font_name,
            is_bold=is_bold,
            block_type=block_type
        )
        self.content.text_blocks.append(block)

    def _is_likely_formula(self, text: str) -> bool:
        """判断是否为公式"""
        formula_indicators = [
            r"\$[^$]+\$",  # LaTeX 行内公式
            r"\\\[.*?\\\]",  # LaTeX 行间公式
            r"[=<>]+",  # 数学运算符
            r"\\sum|\\int|\\frac|\\alpha|\\beta",  # LaTeX命令
        ]
        for pattern in formula_indicators:
            if re.search(pattern, text):
                return True
        return False

    def _extract_metadata(self) -> None:
        """提取元数据（标题、作者、摘要）"""
        if not self.content.text_blocks:
            return

        # 按页面和位置排序
        sorted_blocks = sorted(
            self.content.text_blocks,
            key=lambda b: (b.page_num, b.y_position)
        )

        # 提取标题（第一页最大的字体）
        first_page_blocks = [b for b in sorted_blocks if b.page_num == 1]
        if first_page_blocks:
            largest = max(first_page_blocks, key=lambda b: b.font_size)
            if largest.font_size > 16:
                self.content.title = largest.text

        # 提取摘要
        abstract_text = []
        in_abstract = False
        for block in sorted_blocks:
            if re.match(r"^(Abstract|摘要)[:：]?", block.text, re.I):
                in_abstract = True
                continue
            if in_abstract:
                # 遇到下一个章节标题时停止
                if re.match(r"^(1\.?|I\.?|Introduction|引言)", block.text, re.I):
                    break
                if block.block_type != "header":
                    abstract_text.append(block.text)

        self.content.abstract = " ".join(abstract_text)

    def _identify_sections(self) -> None:
        """识别论文章节结构"""
        for block in self.content.text_blocks:
            if block.block_type != "header":
                continue

            for pattern in self.SECTION_PATTERNS:
                if re.match(pattern, block.text, re.I):
                    section_name = block.text.strip()
                    self.content.section_map[section_name] = block.page_num
                    logger.debug(f"识别到章节: {section_name} (第{block.page_num}页)")
                    break

    def _calculate_word_count(self) -> None:
        """计算字数统计"""
        full_text = self.content.get_full_text()
        # 中文字符 + 英文单词
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", full_text))
        english_words = len(re.findall(r"[a-zA-Z]+", full_text))
        self.content.word_count = chinese_chars + english_words

    def get_font_statistics(self) -> dict[float, int]:
        """获取字体大小统计"""
        return self._font_size_stats.copy()


class PDFBatchExtractor:
    """批量PDF提取器"""

    def __init__(self, output_dir: str | Path = "research_articles/examples"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_single(
        self,
        pdf_path: str | Path,
        save_json: bool = False
    ) -> PDFContent:
        """
        提取单个PDF

        Args:
            pdf_path: PDF文件路径
            save_json: 是否保存为JSON格式

        Returns:
            PDFContent对象
        """
        extractor = PDFExtractor(pdf_path)
        content = extractor.extract()

        if save_json:
            import json
            output_file = self.output_dir / f"{Path(pdf_path).stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(self._content_to_dict(content), f, ensure_ascii=False, indent=2)
            logger.info(f"已保存JSON: {output_file}")

        return content

    def extract_batch(
        self,
        pdf_dir: str | Path,
        pattern: str = "*.pdf"
    ) -> list[PDFContent]:
        """
        批量提取目录下的PDF

        Args:
            pdf_dir: PDF文件目录
            pattern: 文件匹配模式

        Returns:
            PDFContent对象列表
        """
        pdf_dir = Path(pdf_dir)
        pdf_files = list(pdf_dir.glob(pattern))

        logger.info(f"找到 {len(pdf_files)} 个PDF文件")

        results = []
        for pdf_file in pdf_files:
            try:
                content = self.extract_single(pdf_file, save_json=True)
                results.append(content)
            except Exception as e:
                logger.error(f"提取失败 {pdf_file}: {e}")

        return results

    def _content_to_dict(self, content: PDFContent) -> dict:
        """将PDFContent转换为字典"""
        return {
            "title": content.title,
            "authors": content.authors,
            "abstract": content.abstract,
            "keywords": content.keywords,
            "total_pages": content.total_pages,
            "word_count": content.word_count,
            "section_map": content.section_map,
            "text_blocks": [
                {
                    "text": b.text,
                    "page": b.page_num,
                    "font_size": b.font_size,
                    "type": b.block_type
                }
                for b in content.text_blocks
            ],
            "tables": [
                {
                    "page": t.page_num,
                    "data": t.table_data
                }
                for t in content.tables
            ]
        }


if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        extractor = PDFExtractor(pdf_file)
        content = extractor.extract()

        print(f"\n标题: {content.title}")
        print(f"摘要: {content.abstract[:200]}...")
        print(f"总页数: {content.total_pages}")
        print(f"字数: {content.word_count}")
        print(f"\n章节结构: {content.section_map}")
