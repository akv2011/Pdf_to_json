from typing import List, Dict, Any, Tuple
import fitz

from .models import (
    PageContent, ContentBlock, TextLine, TextSpan, FontInfo, BoundingBox,
    TextBlock, ContentType, ImageInfo
)
from .chart_extractor import ChartExtractor
from .logging_utils import get_logger


class PageProcessor:
    def __init__(self, debug: bool = False, extract_images: bool = False):
        self.debug = debug
        self.extract_images = extract_images
        self.chart_extractor = ChartExtractor(debug=debug) if extract_images else None
    
    def process_page(self, page: fitz.Page, page_number: int) -> PageContent:
        logger = get_logger('pdf_extractor.page_processor')
        
        try:

            try:
                text_dict = page.get_text("dict", sort=True)
                logger.debug(f"Retrieved text dictionary for page {page_number}")
            except Exception as e:
                logger.warning(f"Failed to get text dict for page {page_number}: {str(e)}")

                text_dict = {
                    'width': page.rect.width,
                    'height': page.rect.height,
                    'blocks': []
                }
            

            page_content = PageContent(
                page_number=page_number,
                page_width=text_dict.get('width', page.rect.width),
                page_height=text_dict.get('height', page.rect.height),
                rotation=getattr(page, 'rotation', 0)
            )
            

            if self.debug:
                page_content.raw_text_data = text_dict
            

            content_blocks = []
            for block_idx, block_data in enumerate(text_dict.get('blocks', [])):
                try:
                    content_block = self._process_block(block_data)
                    if content_block:
                        content_blocks.append(content_block)
                except Exception as e:
                    logger.warning(
                        f"Failed to process block {block_idx} on page {page_number}: {str(e)}"
                    )

                    continue
            
            page_content.content_blocks = content_blocks
            

            if self.extract_images and self.chart_extractor:
                try:

                    text_blocks = self._create_text_blocks_for_caption_detection(content_blocks)
                    

                    images = self.chart_extractor.extract_images_from_page(
                        page, page_number, text_blocks
                    )
                    page_content.images = images
                    logger.debug(f"Extracted {len(images)} images from page {page_number}")
                    
                except Exception as e:
                    logger.warning(f"Failed to extract images from page {page_number}: {str(e)}")

                    page_content.images = []
            
            logger.debug(f"Successfully processed page {page_number} with {len(content_blocks)} content blocks")
            return page_content
            
        except Exception as e:
            logger.error(f"Critical error processing page {page_number}: {str(e)}")

            return PageContent(
                page_number=page_number,
                page_width=page.rect.width if hasattr(page, 'rect') else 0,
                page_height=page.rect.height if hasattr(page, 'rect') else 0,
                rotation=0,
                content_blocks=[],
                images=[]
            )
    
    def _create_text_blocks_for_caption_detection(
        self, 
        content_blocks: List[ContentBlock]
    ) -> List[TextBlock]:
        text_blocks = []
        
        for block in content_blocks:
            if block.is_text_block and block.text.strip():

                font_info = None
                if block.lines and block.lines[0].spans:
                    first_span = block.lines[0].spans[0]
                    font_info = {
                        'font_name': first_span.font_info.font_name,
                        'font_size': first_span.font_info.font_size,
                        'is_bold': first_span.font_info.is_bold,
                        'is_italic': first_span.font_info.is_italic,
                        'is_superscript': first_span.font_info.is_superscript,
                        'flags': first_span.font_info.flags,
                        'color': first_span.font_info.color
                    }
                
                text_block = TextBlock(
                    text=block.text,
                    content_type=ContentType.TEXT,
                    bbox=block.bbox,
                    font_info=font_info
                )
                
                text_blocks.append(text_block)
        
        return text_blocks
    
    def _process_block(self, block_data: Dict[str, Any]) -> ContentBlock:
        block_bbox = self._create_bbox(block_data['bbox'])
        
        content_block = ContentBlock(
            block_number=block_data['number'],
            block_type=block_data['type'],
            bbox=block_bbox
        )
        

        if block_data['type'] == 0 and 'lines' in block_data:
            content_block.lines = [
                self._process_line(line_data) 
                for line_data in block_data['lines']
            ]
        
        return content_block
    
    def _process_line(self, line_data: Dict[str, Any]) -> TextLine:
        line_bbox = self._create_bbox(line_data['bbox'])
        
        text_line = TextLine(
            spans=[],
            bbox=line_bbox,
            wmode=line_data.get('wmode', 0),
            direction=tuple(line_data.get('dir', (1, 0)))
        )
        

        for span_data in line_data.get('spans', []):
            text_span = self._process_span(span_data)
            if text_span:
                text_line.spans.append(text_span)
        
        return text_line
    
    def _process_span(self, span_data: Dict[str, Any]) -> TextSpan:
        span_bbox = self._create_bbox(span_data['bbox'])
        

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
        return BoundingBox(
            x0=bbox_tuple[0],
            y0=bbox_tuple[1],
            x1=bbox_tuple[2],
            y1=bbox_tuple[3]
        )
    
    def get_page_statistics(self, page_content: PageContent) -> Dict[str, Any]:
        total_blocks = len(page_content.content_blocks)
        text_blocks = sum(1 for block in page_content.content_blocks if block.is_text_block)
        image_blocks = sum(1 for block in page_content.content_blocks if block.is_image_block)
        
        total_lines = sum(len(block.lines) for block in page_content.content_blocks)
        total_spans = sum(
            len(line.spans) 
            for block in page_content.content_blocks 
            for line in block.lines
        )
        

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
        text_parts = []
        for block in page_content.content_blocks:
            if block.is_text_block and block.text.strip():
                text_parts.append(block.text)
        
        return '\n\n'.join(text_parts)
