"""
Page-level content analysis and structure extraction.

This module implements detailed page processing using PyMuPDF's get_text('dict') 
method to extract content blocks with precise bounding boxes, font information,
and spatial layout data.
"""

from typing import List, Dict, Any, Tuple
import fitz  # PyMuPDF

from .models import (
    PageContent, ContentBlock, TextLine, TextSpan, FontInfo, BoundingBox
)


class PageProcessor:
    """Handles detailed page-level content extraction and analysis."""
    
    def __init__(self, debug: bool = False):
        """Initialize the page processor.
        
        Args:
            debug: If True, store raw text data for debugging purposes
        """
        self.debug = debug
    
    def process_page(self, page: fitz.Page, page_number: int) -> PageContent:
        """Process a single page to extract detailed content structure.
        
        Args:
            page: PyMuPDF page object
            page_number: 1-based page number
            
        Returns:
            PageContent object with detailed structure information
        """
        # Get structured text data with proper sorting for reading order
        text_dict = page.get_text("dict", sort=True)
        
        # Create page content object
        page_content = PageContent(
            page_number=page_number,
            page_width=text_dict.get('width', page.rect.width),
            page_height=text_dict.get('height', page.rect.height),
            rotation=page.rotation
        )
        
        # Store raw data if debugging
        if self.debug:
            page_content.raw_text_data = text_dict
        
        # Process all blocks in the page
        content_blocks = []
        for block_data in text_dict.get('blocks', []):
            content_block = self._process_block(block_data)
            if content_block:
                content_blocks.append(content_block)
        
        page_content.content_blocks = content_blocks
        
        return page_content
    
    def _process_block(self, block_data: Dict[str, Any]) -> ContentBlock:
        """Process a single block from the text dictionary.
        
        Args:
            block_data: Block dictionary from PyMuPDF
            
        Returns:
            ContentBlock object with detailed structure
        """
        block_bbox = self._create_bbox(block_data['bbox'])
        
        content_block = ContentBlock(
            block_number=block_data['number'],
            block_type=block_data['type'],
            bbox=block_bbox
        )
        
        # Only process lines for text blocks (type 0)
        if block_data['type'] == 0 and 'lines' in block_data:
            content_block.lines = [
                self._process_line(line_data) 
                for line_data in block_data['lines']
            ]
        
        return content_block
    
    def _process_line(self, line_data: Dict[str, Any]) -> TextLine:
        """Process a single line from the block data.
        
        Args:
            line_data: Line dictionary from PyMuPDF
            
        Returns:
            TextLine object with spans
        """
        line_bbox = self._create_bbox(line_data['bbox'])
        
        text_line = TextLine(
            spans=[],
            bbox=line_bbox,
            wmode=line_data.get('wmode', 0),
            direction=tuple(line_data.get('dir', (1, 0)))
        )
        
        # Process all spans in the line
        for span_data in line_data.get('spans', []):
            text_span = self._process_span(span_data)
            if text_span:
                text_line.spans.append(text_span)
        
        return text_line
    
    def _process_span(self, span_data: Dict[str, Any]) -> TextSpan:
        """Process a single span from the line data.
        
        Args:
            span_data: Span dictionary from PyMuPDF
            
        Returns:
            TextSpan object with font and position information
        """
        span_bbox = self._create_bbox(span_data['bbox'])
        
        # Create font information object
        font_info = FontInfo(
            font_name=span_data.get('font', ''),
            font_size=span_data.get('size', 0.0),
            flags=span_data.get('flags', 0),
            color=span_data.get('color', 0),
            ascender=span_data.get('ascender'),
            descender=span_data.get('descender')
        )
        
        return TextSpan(
            text=span_data.get('text', ''),
            bbox=span_bbox,
            font_info=font_info,
            origin=tuple(span_data.get('origin', (0, 0)))
        )
    
    def _create_bbox(self, bbox_tuple: Tuple[float, float, float, float]) -> BoundingBox:
        """Create a BoundingBox object from a tuple.
        
        Args:
            bbox_tuple: (x0, y0, x1, y1) coordinates
            
        Returns:
            BoundingBox object
        """
        return BoundingBox(
            x0=bbox_tuple[0],
            y0=bbox_tuple[1],
            x1=bbox_tuple[2],
            y1=bbox_tuple[3]
        )
    
    def get_page_statistics(self, page_content: PageContent) -> Dict[str, Any]:
        """Get statistical information about the page content.
        
        Args:
            page_content: Processed page content
            
        Returns:
            Dictionary with page statistics
        """
        total_blocks = len(page_content.content_blocks)
        text_blocks = sum(1 for block in page_content.content_blocks if block.is_text_block)
        image_blocks = sum(1 for block in page_content.content_blocks if block.is_image_block)
        
        total_lines = sum(len(block.lines) for block in page_content.content_blocks)
        total_spans = sum(
            len(line.spans) 
            for block in page_content.content_blocks 
            for line in block.lines
        )
        
        # Analyze font usage
        font_sizes = []
        font_names = set()
        for block in page_content.content_blocks:
            for line in block.lines:
                for span in line.spans:
                    font_sizes.append(span.font_info.font_size)
                    font_names.add(span.font_info.font_name)
        
        return {
            'total_blocks': total_blocks,
            'text_blocks': text_blocks,
            'image_blocks': image_blocks,
            'total_lines': total_lines,
            'total_spans': total_spans,
            'unique_fonts': len(font_names),
            'font_names': list(font_names),
            'font_size_range': (min(font_sizes) if font_sizes else 0, 
                              max(font_sizes) if font_sizes else 0),
            'avg_font_size': sum(font_sizes) / len(font_sizes) if font_sizes else 0
        }
    
    def extract_text_content(self, page_content: PageContent) -> str:
        """Extract plain text content from processed page.
        
        Args:
            page_content: Processed page content
            
        Returns:
            Plain text string with proper line breaks
        """
        text_parts = []
        for block in page_content.content_blocks:
            if block.is_text_block and block.text.strip():
                text_parts.append(block.text)
        
        return '\n\n'.join(text_parts)
