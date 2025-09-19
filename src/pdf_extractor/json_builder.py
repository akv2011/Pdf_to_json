"""
JSON Schema Definition and Output Builder for PDF extraction results.

This module provides comprehensive JSON schema validation and a builder class
that assembles extracted hierarchical data into clean, compliant JSON output.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import logging

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logging.warning("jsonschema package not available. Schema validation will be disabled.")

from .models import (
    ExtractionResult, DocumentStructure, SectionNode, TextBlock, 
    Table, ImageInfo, ContentType, BoundingBox, FontInfo,
    ExtractionConfig
)


class JSONBuilder:
    """
    Builder class that assembles extracted PDF data into a structured JSON format.
    
    This class takes hierarchical data from StructureBuilder, TableExtractor, and 
    ChartExtractor and creates a clean, schema-compliant JSON output.
    """
    
    def __init__(self, validate_schema: bool = True, indent: int = 2):
        """Initialize the JSON builder.
        
        Args:
            validate_schema: Whether to validate output against JSON schema
            indent: JSON indentation for pretty printing
        """
        self.validate_schema = validate_schema and JSONSCHEMA_AVAILABLE
        self.indent = indent
        self.logger = logging.getLogger(__name__)
        
        # Load JSON schema for validation
        self.schema = None
        if self.validate_schema:
            try:
                schema_path = Path(__file__).parent / "schema.json"
                with open(schema_path, 'r') as f:
                    self.schema = json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load JSON schema: {e}")
                self.validate_schema = False
    
    def build_from_document_structure(
        self, 
        doc_structure: DocumentStructure,
        extraction_result: ExtractionResult,
        extraction_config: ExtractionConfig = None
    ) -> Dict[str, Any]:
        """Build JSON output from hierarchical document structure.
        
        Args:
            doc_structure: Hierarchical document structure from StructureBuilder
            extraction_result: Raw extraction result for metadata
            extraction_config: Configuration used for extraction
            
        Returns:
            Dictionary ready for JSON serialization
        """
        # Build the main structure
        json_output = {
            "document": self._build_document_section(doc_structure),
            "metadata": self._build_metadata_section(extraction_result),
            "extraction_info": self._build_extraction_info(
                extraction_result, extraction_config
            )
        }
        
        # Validate against schema if enabled
        if self.validate_schema and self.schema:
            try:
                jsonschema.validate(json_output, self.schema)
                self.logger.debug("JSON output validated successfully against schema")
            except jsonschema.ValidationError as e:
                self.logger.warning(f"JSON schema validation failed: {e}")
        
        return json_output
    
    def build_from_extraction_result(
        self, 
        extraction_result: ExtractionResult,
        extraction_config: ExtractionConfig = None
    ) -> Dict[str, Any]:
        """Build JSON output from flat extraction result (page-based).
        
        Args:
            extraction_result: Extraction result with page-based data
            extraction_config: Configuration used for extraction
            
        Returns:
            Dictionary ready for JSON serialization
        """
        # Convert page-based structure to hierarchical format
        doc_structure = self._convert_pages_to_hierarchy(extraction_result)
        
        return self.build_from_document_structure(
            doc_structure, extraction_result, extraction_config
        )
    
    def to_json_string(self, data: Dict[str, Any]) -> str:
        """Convert dictionary to JSON string with proper formatting.
        
        Args:
            data: Dictionary to serialize
            
        Returns:
            JSON string with UTF-8 encoding and indentation
        """
        return json.dumps(
            data, 
            ensure_ascii=False, 
            indent=self.indent,
            separators=(',', ': ')
        )
    
    def save_to_file(self, data: Dict[str, Any], file_path: Path) -> None:
        """Save JSON data to file.
        
        Args:
            data: Dictionary to save
            file_path: Path where to save the JSON file
        """
        json_string = self.to_json_string(data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json_string)
        
        self.logger.info(f"JSON output saved to: {file_path}")
    
    def _build_document_section(self, doc_structure: DocumentStructure) -> Dict[str, Any]:
        """Build the document section of the JSON output.
        
        Args:
            doc_structure: Document structure to convert
            
        Returns:
            Document section dictionary
        """
        content = []
        
        # Convert sections to content items
        for section in doc_structure.sections:
            content.append(self._convert_section_to_content_item(section))
        
        # Build summary statistics
        summary = {
            "total_sections": len(doc_structure.get_all_sections()),
            "total_pages": doc_structure.total_pages,
            "total_content_blocks": doc_structure.count_total_content_blocks(),
            "content_types": self._count_content_types(doc_structure)
        }
        
        return {
            "title": doc_structure.title,
            "content": content,
            "summary": summary
        }
    
    def _build_metadata_section(self, extraction_result: ExtractionResult) -> Dict[str, Any]:
        """Build the metadata section of the JSON output.
        
        Args:
            extraction_result: Extraction result containing metadata
            
        Returns:
            Metadata section dictionary
        """
        metadata = extraction_result.metadata.copy()
        metadata["file_path"] = extraction_result.file_path
        metadata["page_count"] = len(extraction_result.pages)
        
        return metadata
    
    def _build_extraction_info(
        self, 
        extraction_result: ExtractionResult,
        extraction_config: ExtractionConfig = None
    ) -> Dict[str, Any]:
        """Build the extraction info section.
        
        Args:
            extraction_result: Extraction result
            extraction_config: Configuration used
            
        Returns:
            Extraction info dictionary
        """
        config_dict = {}
        if extraction_config:
            config_dict = {
                "extract_tables": extraction_config.extract_tables,
                "extract_images": extraction_config.extract_images,
                "preserve_layout": extraction_config.preserve_layout,
                "table_extraction_methods": extraction_config.table_extraction_methods
            }
        
        return {
            "processing_time": extraction_result.processing_time or 0.0,
            "extraction_config": config_dict,
            "errors": extraction_result.errors,
            "warnings": extraction_result.warnings
        }
    
    def _convert_section_to_content_item(self, section: SectionNode) -> Dict[str, Any]:
        """Convert a SectionNode to a content item.
        
        Args:
            section: Section node to convert
            
        Returns:
            Content item dictionary
        """
        content_items = []
        
        # Convert content blocks
        for block in section.content_blocks:
            content_item = self._convert_content_block_to_item(block)
            if content_item:
                content_items.append(content_item)
        
        # Convert subsections
        for subsection in section.subsections:
            content_items.append(self._convert_section_to_content_item(subsection))
        
        return {
            "type": "section",
            "title": section.title,
            "level": section.level.value,
            "content": content_items,
            "page_number": section.page_number,
            "bbox": self._convert_bbox(section.bbox),
            "metadata": section.metadata
        }
    
    def _convert_content_block_to_item(
        self, 
        block: Union[TextBlock, Table, ImageInfo]
    ) -> Optional[Dict[str, Any]]:
        """Convert a content block to a content item.
        
        Args:
            block: Content block to convert
            
        Returns:
            Content item dictionary or None if conversion fails
        """
        if isinstance(block, TextBlock):
            return self._convert_text_block(block)
        elif isinstance(block, Table):
            return self._convert_table_block(block)
        elif isinstance(block, ImageInfo):
            return self._convert_image_block(block)
        else:
            self.logger.warning(f"Unknown content block type: {type(block)}")
            return None
    
    def _convert_text_block(self, block: TextBlock) -> Dict[str, Any]:
        """Convert TextBlock to content item.
        
        Args:
            block: Text block to convert
            
        Returns:
            Content item dictionary
        """
        # Determine the content type
        if block.content_type.is_header_type():
            return {
                "type": "header",
                "text": block.text,
                "level": block.content_type.get_header_level() or 1,
                "page_number": block.metadata.get("page_number"),
                "bbox": self._convert_bbox(block.bbox),
                "font_info": self._convert_font_info(block.font_info),
                "metadata": block.metadata
            }
        elif block.content_type == ContentType.LIST:
            return self._convert_list_block(block)
        else:
            # Default to paragraph
            return {
                "type": "paragraph", 
                "text": block.text,
                "page_number": block.metadata.get("page_number"),
                "bbox": self._convert_bbox(block.bbox),
                "font_info": self._convert_font_info(block.font_info),
                "confidence": block.confidence,
                "metadata": block.metadata
            }
    
    def _convert_table_block(self, table: Table) -> Dict[str, Any]:
        """Convert Table to content item.
        
        Args:
            table: Table to convert
            
        Returns:
            Content item dictionary
        """
        data = table.to_2d_array()
        headers = None
        
        # Try to extract headers from first row if it looks like headers
        if data and len(data) > 1:
            first_row = data[0]
            # Simple heuristic: if first row has different style, treat as headers
            headers = first_row
            data = data[1:]  # Remove header row from data
        
        return {
            "type": "table",
            "data": data,
            "headers": headers,
            "rows": table.rows,
            "cols": table.cols,
            "page_number": None,  # Table spans might cross pages
            "bbox": self._convert_bbox(table.bbox),
            "extraction_method": table.extraction_method,
            "confidence": table.confidence,
            "metadata": {}
        }
    
    def _convert_image_block(self, image: ImageInfo) -> Dict[str, Any]:
        """Convert ImageInfo to content item.
        
        Args:
            image: Image info to convert
            
        Returns:
            Content item dictionary
        """
        return {
            "type": "image",
            "image_id": image.image_id,
            "description": image.description,
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "size_bytes": image.size_bytes,
            "page_number": image.page_number,
            "bbox": self._convert_bbox(image.bbox),
            "metadata": image.metadata
        }
    
    def _convert_list_block(self, block: TextBlock) -> Dict[str, Any]:
        """Convert a list TextBlock to a list content item.
        
        Args:
            block: Text block containing list content
            
        Returns:
            List content item dictionary
        """
        # Simple list parsing - split by lines and detect bullet types
        lines = block.text.strip().split('\n')
        items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect bullet type and extract text
            bullet_type = "bullet"
            text = line
            
            # Check for numbered lists
            if line and line[0].isdigit():
                bullet_type = "number"
                # Remove number and period/parenthesis
                import re
                text = re.sub(r'^\d+[.)]\s*', '', line)
            elif line.startswith(('•', '*', '-')):
                bullet_type = "bullet"
                text = line[1:].strip()
            elif line.startswith(('a)', 'b)', 'c)')):
                bullet_type = "letter"
                text = line[2:].strip()
            
            items.append({
                "text": text,
                "level": 0,  # Could be enhanced to detect nested levels
                "bullet_type": bullet_type
            })
        
        return {
            "type": "list",
            "items": items,
            "list_type": "ordered" if items and items[0]["bullet_type"] == "number" else "unordered",
            "page_number": block.metadata.get("page_number"),
            "bbox": self._convert_bbox(block.bbox),
            "metadata": block.metadata
        }
    
    def _convert_bbox(self, bbox: Optional[BoundingBox]) -> Optional[Dict[str, Any]]:
        """Convert BoundingBox to dictionary.
        
        Args:
            bbox: Bounding box to convert
            
        Returns:
            Bounding box dictionary or None
        """
        if not bbox:
            return None
            
        return {
            "x0": bbox.x0,
            "y0": bbox.y0,
            "x1": bbox.x1,
            "y1": bbox.y1,
            "width": bbox.width,
            "height": bbox.height
        }
    
    def _convert_font_info(self, font_info: Any) -> Optional[Dict[str, Any]]:
        """Convert font info to dictionary.
        
        Args:
            font_info: Font information to convert
            
        Returns:
            Font info dictionary or None
        """
        if not font_info:
            return None
        
        if isinstance(font_info, dict):
            return {
                "font_name": font_info.get("font_name"),
                "font_size": font_info.get("font_size"),
                "is_bold": font_info.get("is_bold", False),
                "is_italic": font_info.get("is_italic", False),
                "color": font_info.get("color"),
                "flags": font_info.get("flags")
            }
        elif isinstance(font_info, FontInfo):
            return {
                "font_name": font_info.font_name,
                "font_size": font_info.font_size,
                "is_bold": font_info.is_bold,
                "is_italic": font_info.is_italic,
                "color": font_info.color,
                "flags": font_info.flags
            }
        
        return None
    
    def _count_content_types(self, doc_structure: DocumentStructure) -> Dict[str, int]:
        """Count content types in the document structure.
        
        Args:
            doc_structure: Document structure to analyze
            
        Returns:
            Dictionary with content type counts
        """
        counts = {
            "headers": 0,
            "paragraphs": 0,
            "tables": 0,
            "images": 0,
            "lists": 0
        }
        
        def count_in_section(section: SectionNode):
            for block in section.content_blocks:
                if isinstance(block, TextBlock):
                    if block.content_type.is_header_type():
                        counts["headers"] += 1
                    elif block.content_type == ContentType.LIST:
                        counts["lists"] += 1
                    else:
                        counts["paragraphs"] += 1
                elif isinstance(block, Table):
                    counts["tables"] += 1
                elif isinstance(block, ImageInfo):
                    counts["images"] += 1
            
            for subsection in section.subsections:
                count_in_section(subsection)
        
        for section in doc_structure.sections:
            count_in_section(section)
        
        return counts
    
    def _convert_pages_to_hierarchy(self, extraction_result: ExtractionResult) -> DocumentStructure:
        """Convert page-based extraction result to hierarchical structure.
        
        This is a fallback method when we don't have a StructureBuilder result.
        
        Args:
            extraction_result: Page-based extraction result
            
        Returns:
            Basic hierarchical document structure
        """
        doc_structure = DocumentStructure(
            title=extraction_result.metadata.get("title"),
            total_pages=len(extraction_result.pages),
            processing_time=extraction_result.processing_time,
            metadata=extraction_result.metadata
        )
        
        # Create a simple hierarchy based on pages
        for page in extraction_result.pages:
            section_title = f"Page {page.page_number}"
            
            from .models import HeaderLevel
            section = SectionNode(
                title=section_title,
                level=HeaderLevel.H1,
                page_number=page.page_number
            )
            
            # Add all content from the page
            for block in page.text_blocks:
                section.add_content(block)
            
            for table in page.tables:
                section.add_content(table)
            
            for image in page.images:
                section.add_content(image)
            
            doc_structure.add_section(section)
        
        return doc_structure