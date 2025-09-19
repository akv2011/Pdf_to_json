"""
Data models and configuration for PDF Structure Extractor
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum


class ContentType(Enum):
    """Types of content that can be extracted from PDFs."""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    HEADER = "header"
    FOOTER = "footer"
    LIST = "list"
    PARAGRAPH = "paragraph"


@dataclass
class ExtractionConfig:
    """Configuration for PDF extraction process."""
    preserve_layout: bool = False
    extract_tables: bool = True
    extract_images: bool = False
    verbose: bool = False
    table_extraction_methods: List[str] = field(default_factory=lambda: ["pdfplumber", "camelot", "tabula"])
    min_table_rows: int = 2
    min_table_cols: int = 2
    text_extraction_method: str = "pymupdf"  # or "pdfplumber"
    password: Optional[str] = None


@dataclass
class BoundingBox:
    """Represents a bounding box for content positioning."""
    x0: float
    y0: float
    x1: float
    y1: float
    width: Optional[float] = None
    height: Optional[float] = None
    
    def __post_init__(self):
        if self.width is None:
            self.width = self.x1 - self.x0
        if self.height is None:
            self.height = self.y1 - self.y0


@dataclass
class FontInfo:
    """Represents font information for a text span."""
    font_name: str
    font_size: float
    flags: int = 0
    color: int = 0
    ascender: Optional[float] = None
    descender: Optional[float] = None
    
    @property
    def is_bold(self) -> bool:
        """Check if text is bold using flags."""
        return bool(self.flags & 16)
    
    @property
    def is_italic(self) -> bool:
        """Check if text is italic using flags."""
        return bool(self.flags & 2)
    
    @property
    def is_superscript(self) -> bool:
        """Check if text is superscript using flags."""
        return bool(self.flags & 1)
    
    @property
    def is_serif(self) -> bool:
        """Check if font is serif using flags."""
        return bool(self.flags & 4)


@dataclass
class TextSpan:
    """Represents a span of text with consistent formatting."""
    text: str
    bbox: BoundingBox
    font_info: FontInfo
    origin: tuple = field(default_factory=tuple)  # (x, y) baseline origin
    

@dataclass
class TextLine:
    """Represents a line of text containing multiple spans."""
    spans: List[TextSpan]
    bbox: BoundingBox
    wmode: int = 0  # Writing mode: 0=horizontal, 1=vertical
    direction: tuple = field(default_factory=lambda: (1, 0))  # (x, y) writing direction
    
    @property
    def text(self) -> str:
        """Get the full text of the line."""
        return ''.join(span.text for span in self.spans)


@dataclass
class ContentBlock:
    """Represents a block of content (text or image) with detailed structure."""
    block_number: int
    block_type: int  # 0=text, 1=image
    bbox: BoundingBox
    lines: List[TextLine] = field(default_factory=list)
    
    @property
    def text(self) -> str:
        """Get the full text of the block."""
        return '\n'.join(line.text for line in self.lines)
    
    @property
    def is_text_block(self) -> bool:
        """Check if this is a text block."""
        return self.block_type == 0
    
    @property
    def is_image_block(self) -> bool:
        """Check if this is an image block."""
        return self.block_type == 1


@dataclass
class TextBlock:
    """Represents a block of text with metadata."""
    text: str
    content_type: ContentType
    bbox: Optional[BoundingBox] = None
    font_info: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableCell:
    """Represents a single cell in a table."""
    text: str
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    bbox: Optional[BoundingBox] = None


@dataclass
class Table:
    """Represents a table extracted from PDF."""
    cells: List[TableCell]
    rows: int
    cols: int
    bbox: Optional[BoundingBox] = None
    extraction_method: str = "unknown"
    confidence: float = 1.0
    
    def to_2d_array(self) -> List[List[str]]:
        """Convert table to 2D array format."""
        array = [["" for _ in range(self.cols)] for _ in range(self.rows)]
        for cell in self.cells:
            if cell.row < self.rows and cell.col < self.cols:
                array[cell.row][cell.col] = cell.text
        return array
    
    def to_dict_list(self, header_row: int = 0) -> List[Dict[str, str]]:
        """Convert table to list of dictionaries using specified row as headers."""
        array = self.to_2d_array()
        if header_row >= len(array):
            return []
        
        headers = array[header_row]
        result = []
        
        for i, row in enumerate(array):
            if i != header_row:  # Skip header row
                row_dict = {}
                for j, value in enumerate(row):
                    header = headers[j] if j < len(headers) else f"Column_{j}"
                    row_dict[header] = value
                result.append(row_dict)
        
        return result


@dataclass
class ImageInfo:
    """Represents image metadata extracted from PDF."""
    image_id: str
    bbox: Optional[BoundingBox] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    size_bytes: Optional[int] = None
    description: Optional[str] = None


@dataclass
class PageContent:
    """Represents content extracted from a single PDF page."""
    page_number: int
    text_blocks: List[TextBlock] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    images: List[ImageInfo] = field(default_factory=list)
    page_width: Optional[float] = None
    page_height: Optional[float] = None
    rotation: int = 0
    # Enhanced structured content from get_text('dict')
    content_blocks: List[ContentBlock] = field(default_factory=list)
    raw_text_data: Optional[Dict[str, Any]] = None  # Store raw dict for debugging


@dataclass
class ExtractionResult:
    """Complete result of PDF extraction."""
    file_path: str
    pages: List[PageContent]
    metadata: Dict[str, Any] = field(default_factory=dict)
    extraction_config: Optional[ExtractionConfig] = None
    processing_time: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert extraction result to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "metadata": self.metadata,
            "processing_time": self.processing_time,
            "page_count": len(self.pages),
            "errors": self.errors,
            "warnings": self.warnings,
            "pages": [
                {
                    "page_number": page.page_number,
                    "page_width": page.page_width,
                    "page_height": page.page_height,
                    "rotation": page.rotation,
                    "text_blocks": [
                        {
                            "text": block.text,
                            "content_type": block.content_type.value,
                            "bbox": {
                                "x0": block.bbox.x0,
                                "y0": block.bbox.y0,
                                "x1": block.bbox.x1,
                                "y1": block.bbox.y1,
                                "width": block.bbox.width,
                                "height": block.bbox.height
                            } if block.bbox else None,
                            "font_info": block.font_info,
                            "confidence": block.confidence,
                            "metadata": block.metadata
                        } for block in page.text_blocks
                    ],
                    "tables": [
                        {
                            "rows": table.rows,
                            "cols": table.cols,
                            "extraction_method": table.extraction_method,
                            "confidence": table.confidence,
                            "bbox": {
                                "x0": table.bbox.x0,
                                "y0": table.bbox.y0,
                                "x1": table.bbox.x1,
                                "y1": table.bbox.y1,
                                "width": table.bbox.width,
                                "height": table.bbox.height
                            } if table.bbox else None,
                            "data": table.to_2d_array(),
                            "cells": [
                                {
                                    "text": cell.text,
                                    "row": cell.row,
                                    "col": cell.col,
                                    "rowspan": cell.rowspan,
                                    "colspan": cell.colspan,
                                    "bbox": {
                                        "x0": cell.bbox.x0,
                                        "y0": cell.bbox.y0,
                                        "x1": cell.bbox.x1,
                                        "y1": cell.bbox.y1,
                                        "width": cell.bbox.width,
                                        "height": cell.bbox.height
                                    } if cell.bbox else None
                                } for cell in table.cells
                            ]
                        } for table in page.tables
                    ],
                    "images": [
                        {
                            "image_id": img.image_id,
                            "width": img.width,
                            "height": img.height,
                            "format": img.format,
                            "size_bytes": img.size_bytes,
                            "description": img.description,
                            "bbox": {
                                "x0": img.bbox.x0,
                                "y0": img.bbox.y0,
                                "x1": img.bbox.x1,
                                "y1": img.bbox.y1,
                                "width": img.bbox.width,
                                "height": img.bbox.height
                            } if img.bbox else None
                        } for img in page.images
                    ],
                    "content_blocks": [
                        {
                            "block_number": block.block_number,
                            "block_type": block.block_type,
                            "is_text": block.is_text_block,
                            "is_image": block.is_image_block,
                            "bbox": {
                                "x0": block.bbox.x0,
                                "y0": block.bbox.y0,
                                "x1": block.bbox.x1,
                                "y1": block.bbox.y1,
                                "width": block.bbox.width,
                                "height": block.bbox.height
                            },
                            "text": block.text,
                            "lines": [
                                {
                                    "text": line.text,
                                    "wmode": line.wmode,
                                    "direction": line.direction,
                                    "bbox": {
                                        "x0": line.bbox.x0,
                                        "y0": line.bbox.y0,
                                        "x1": line.bbox.x1,
                                        "y1": line.bbox.y1,
                                        "width": line.bbox.width,
                                        "height": line.bbox.height
                                    },
                                    "spans": [
                                        {
                                            "text": span.text,
                                            "bbox": {
                                                "x0": span.bbox.x0,
                                                "y0": span.bbox.y0,
                                                "x1": span.bbox.x1,
                                                "y1": span.bbox.y1,
                                                "width": span.bbox.width,
                                                "height": span.bbox.height
                                            },
                                            "font": {
                                                "name": span.font_info.font_name,
                                                "size": span.font_info.font_size,
                                                "flags": span.font_info.flags,
                                                "color": span.font_info.color,
                                                "is_bold": span.font_info.is_bold,
                                                "is_italic": span.font_info.is_italic,
                                                "is_superscript": span.font_info.is_superscript,
                                                "is_serif": span.font_info.is_serif,
                                                "ascender": span.font_info.ascender,
                                                "descender": span.font_info.descender
                                            },
                                            "origin": span.origin
                                        } for span in line.spans
                                    ]
                                } for line in block.lines
                            ]
                        } for block in page.content_blocks
                    ]
                } for page in self.pages
            ]
        }


class ExtractionError(Exception):
    """Custom exception for PDF extraction errors."""
    pass


class UnsupportedPDFError(ExtractionError):
    """Raised when PDF format is not supported."""
    pass


class PasswordRequiredError(ExtractionError):
    """Raised when PDF requires a password."""
    pass
