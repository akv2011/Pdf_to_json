from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import re

from .models import (
    PageContent, ContentBlock, TextSpan, FontInfo, ContentType, TextBlock, BoundingBox
)


class ContentClassifier:   
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.baseline_font_style: Optional[Dict[str, Any]] = None
        self._debug_info: Dict[str, Any] = {}
    
    def classify_page_content(self, page_content: PageContent) -> List[TextBlock]:
        self._establish_baseline_style(page_content)
        

        all_spans_info = []
        for content_block in page_content.content_blocks:
            if content_block.is_text_block:
                for line in content_block.lines:
                    for span in line.spans:
                        if span.text.strip():
                            span_info = {
                                'span': span,
                                'content_block': content_block,
                                'y_position': span.bbox.y0,
                                'content_type': None,
                                'should_group': True
                            }
                            all_spans_info.append(span_info)
        


        all_spans_info.sort(key=lambda x: (x['y_position'], x['span'].bbox.x0))
        

        for span_info in all_spans_info:
            span = span_info['span']
            
            if self._is_list_item(span):
                span_info['content_type'] = ContentType.LIST
                span_info['should_group'] = False
            elif self._is_header(span):
                span_info['content_type'] = ContentType.HEADER
                span_info['should_group'] = False
            else:
                span_info['content_type'] = ContentType.PARAGRAPH
                span_info['should_group'] = True
        

        grouped_spans = self._group_paragraph_spans(all_spans_info)
        

        classified_blocks = []
        for group in grouped_spans:
            text_block = self._create_text_block_from_group(group)
            if text_block:
                classified_blocks.append(text_block)
        
        return classified_blocks
    
    def _establish_baseline_style(self, page_content: PageContent) -> None:
        font_sizes = []
        font_names = []
        is_bold_flags = []
        is_italic_flags = []
        
        for content_block in page_content.content_blocks:
            if content_block.is_text_block:
                for line in content_block.lines:
                    for span in line.spans:
                        if span.text.strip():
                            font_sizes.append(span.font_info.font_size)
                            font_names.append(span.font_info.font_name)
                            is_bold_flags.append(span.font_info.is_bold)
                            is_italic_flags.append(span.font_info.is_italic)
        
        if not font_sizes:

            self.baseline_font_style = {
                'size': 12.0,
                'font': 'Unknown',
                'bold': False,
                'italic': False
            }
            return
        

        size_counter = Counter(font_sizes)
        font_counter = Counter(font_names)
        bold_counter = Counter(is_bold_flags)
        italic_counter = Counter(is_italic_flags)
        

        most_common_size = size_counter.most_common(1)[0][0]
        most_common_font = font_counter.most_common(1)[0][0]
        most_common_bold = bold_counter.most_common(1)[0][0]
        most_common_italic = italic_counter.most_common(1)[0][0]
        
        self.baseline_font_style = {
            'size': most_common_size,
            'font': most_common_font,
            'bold': most_common_bold,
            'italic': most_common_italic
        }
        

        if self.debug:
            self._debug_info['baseline_analysis'] = {
                'total_spans': len(font_sizes),
                'size_distribution': dict(size_counter.most_common(10)),
                'font_distribution': dict(font_counter.most_common(5)),
                'bold_distribution': dict(bold_counter),
                'italic_distribution': dict(italic_counter),
                'baseline_style': self.baseline_font_style
            }
    
    def _classify_text_span(self, span: TextSpan, parent_block: ContentBlock) -> Optional[TextBlock]:
        text = span.text.strip()
        if not text:
            return None
        

        font_info = {
            'name': span.font_info.font_name,
            'size': span.font_info.font_size,
            'bold': span.font_info.is_bold,
            'italic': span.font_info.is_italic,
            'flags': span.font_info.flags,
            'color': span.font_info.color
        }
        

        content_type = self._determine_content_type(span)
        

        metadata = {
            'block_number': parent_block.block_number,
            'baseline_comparison': self._compare_to_baseline(span.font_info)
        }
        

        if content_type == ContentType.HEADER:
            metadata['header_level'] = self._get_header_level(span)
        

        if content_type == ContentType.LIST:
            metadata['list_marker_type'] = self._get_list_marker_type(span)
        
        return TextBlock(
            text=text,
            content_type=content_type,
            bbox=span.bbox,
            font_info=font_info,
            confidence=1.0,
            metadata=metadata
        )
    
    def _determine_content_type(self, span: TextSpan) -> ContentType:
        if self._is_list_item(span):
            return ContentType.LIST
            

        if self._is_header(span):
            return ContentType.HEADER
        

        

        return ContentType.PARAGRAPH
    
    def _compare_to_baseline(self, font_info: FontInfo) -> Dict[str, Any]:

        if not self.baseline_font_style:
            return {}
        
        baseline = self.baseline_font_style
        

        size_ratio = font_info.font_size / baseline['size'] if baseline['size'] > 0 else 1.0
        
        return {
            'size_ratio': size_ratio,
            'is_larger': font_info.font_size > baseline['size'],
            'is_smaller': font_info.font_size < baseline['size'],
            'font_matches': font_info.font_name == baseline['font'],
            'bold_differs': font_info.is_bold != baseline['bold'],
            'italic_differs': font_info.is_italic != baseline['italic'],
            'significantly_larger': size_ratio >= 1.2,
            'significantly_smaller': size_ratio <= 0.8
        }
    
    def _is_header(self, span: TextSpan) -> bool:
        if not self.baseline_font_style:
            return False
        
        baseline = self.baseline_font_style
        font_info = span.font_info
        

        size_ratio = font_info.font_size / baseline['size'] if baseline['size'] > 0 else 1.0
        

        is_significantly_larger = size_ratio >= 1.2
        is_bold_when_baseline_not = font_info.is_bold and not baseline['bold']
        is_much_larger = size_ratio >= 1.5
        

        if is_much_larger:
            return True
        

        if is_significantly_larger or is_bold_when_baseline_not:

            

            word_count = len(span.text.strip().split())
            is_short = word_count <= 3
            

            is_caps = span.text.strip().isupper()
            

            if is_short or is_caps or is_bold_when_baseline_not:
                return True
            

            if 1.2 <= size_ratio < 1.4:
                return is_bold_when_baseline_not or is_caps
            

            if size_ratio >= 1.4:
                return True
        
        return False
    
    def _get_header_level(self, span: TextSpan) -> int:
        if not self.baseline_font_style:
            return 1
        
        baseline = self.baseline_font_style
        size_ratio = span.font_info.font_size / baseline['size'] if baseline['size'] > 0 else 1.0
        

        if size_ratio >= 2.0:
            return 1
        elif size_ratio >= 1.7:
            return 2
        elif size_ratio >= 1.4:
            return 3
        elif size_ratio >= 1.2:
            return 4
        else:

            return 5
    
    def _is_list_item(self, span: TextSpan) -> bool:
        text = span.text.strip()
        if not text:
            return False
        

        list_patterns = [

            r'^\s*[•·▪▫‣⁃]\s+',
            r'^\s*[*+\-]\s+',
            r'^\s*[▶►▷▸]\s+',
            

            r'^\s*\d+\.\s+',
            r'^\s*\d+\)\s+',
            r'^\s*\(\d+\)\s+',
            r'^\s*\[\d+\]\s+',
            

            r'^\s*[a-zA-Z]\.\s+',
            r'^\s*[a-zA-Z]\)\s+',
            r'^\s*\([a-zA-Z]\)\s+',
            r'^\s*\[[a-zA-Z]\]\s+',
            

            r'^\s*[ivxlcdm]+\.\s+',
            r'^\s*[IVXLCDM]+\.\s+',
            r'^\s*[ivxlcdm]+\)\s+',
            r'^\s*[IVXLCDM]+\)\s+',
            r'^\s*\([ivxlcdm]+\)\s+',
            r'^\s*\([IVXLCDM]+\)\s+',
        ]
        

        for pattern in list_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _get_list_marker_type(self, span: TextSpan) -> str:
        text = span.text.strip()
        

        if re.match(r'^\s*[•·▪▫‣⁃*+\-▶►▷▸]\s+', text):
            return 'bullet'
        elif re.match(r'^\s*\d+[\.\)]\s+', text) or re.match(r'^\s*[\(\[]\d+[\)\]]\s+', text):
            return 'numbered'
        elif re.match(r'^\s*[a-zA-Z][\.\)]\s+', text) or re.match(r'^\s*[\(\[][a-zA-Z][\)\]]\s+', text):
            return 'lettered'
        elif re.match(r'^\s*[ivxlcdmIVXLCDM]+[\.\)]\s+', text) or re.match(r'^\s*[\(\[][ivxlcdmIVXLCDM]+[\)\]]\s+', text):
            return 'roman'
        else:
            return 'unknown'
    
    def _group_paragraph_spans(self, all_spans_info: List[Dict]) -> List[List[Dict]]:
        groups = []
        current_group = []
        
        for i, span_info in enumerate(all_spans_info):

            if not span_info['should_group']:

                if current_group:
                    groups.append(current_group)
                    current_group = []
                

                groups.append([span_info])
                continue
            

            if current_group and self._should_group_with_previous(span_info, current_group[-1]):
                current_group.append(span_info)
            else:

                if current_group:
                    groups.append(current_group)
                current_group = [span_info]
        

        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _should_group_with_previous(self, current_span_info: Dict, previous_span_info: Dict) -> bool:
        current_span = current_span_info['span']
        previous_span = previous_span_info['span']
        

        vertical_distance = abs(previous_span.bbox.y1 - current_span.bbox.y0)
        

        avg_font_size = (current_span.font_info.font_size + previous_span.font_info.font_size) / 2
        max_line_spacing = avg_font_size * 1.5
        

        if vertical_distance > max_line_spacing:
            return False
        

        if not self._fonts_similar(current_span.font_info, previous_span.font_info):
            return False
        

        left_margin_diff = abs(current_span.bbox.x0 - previous_span.bbox.x0)
        if left_margin_diff > avg_font_size * 0.5:
            return False
        
        return True
    
    def _fonts_similar(self, font1: FontInfo, font2: FontInfo) -> bool:
        if font1.font_name != font2.font_name:
            return False
        

        size_ratio = font1.font_size / font2.font_size if font2.font_size > 0 else 1.0
        if size_ratio < 0.9 or size_ratio > 1.1:
            return False
        

        if font1.is_bold != font2.is_bold or font1.is_italic != font2.is_italic:
            return False
        
        return True
    
    def _create_text_block_from_group(self, group: List[Dict]) -> Optional[TextBlock]:
        if not group:
            return None
        

        if len(group) == 1:
            span_info = group[0]
            return self._classify_text_span(span_info['span'], span_info['content_block'])
        

        first_span_info = group[0]
        content_type = first_span_info['content_type']
        

        combined_text = ' '.join(span_info['span'].text.strip() for span_info in group)
        

        min_x0 = min(span_info['span'].bbox.x0 for span_info in group)
        min_y0 = min(span_info['span'].bbox.y0 for span_info in group)
        max_x1 = max(span_info['span'].bbox.x1 for span_info in group)
        max_y1 = max(span_info['span'].bbox.y1 for span_info in group)
        combined_bbox = BoundingBox(min_x0, min_y0, max_x1, max_y1)
        

        first_span = first_span_info['span']
        font_info = {
            'name': first_span.font_info.font_name,
            'size': first_span.font_info.font_size,
            'bold': first_span.font_info.is_bold,
            'italic': first_span.font_info.is_italic,
            'flags': first_span.font_info.flags,
            'color': first_span.font_info.color
        }
        

        metadata = {
            'block_number': first_span_info['content_block'].block_number,
            'baseline_comparison': self._compare_to_baseline(first_span.font_info),
            'span_count': len(group),
            'is_grouped': len(group) > 1
        }
        
        return TextBlock(
            text=combined_text,
            content_type=content_type,
            bbox=combined_bbox,
            font_info=font_info,
            confidence=1.0,
            metadata=metadata
        )
    
    def get_baseline_style(self) -> Optional[Dict[str, Any]]:
        return self.baseline_font_style.copy() if self.baseline_font_style else None
    
    def get_debug_info(self) -> Dict[str, Any]:
        return self._debug_info.copy() if self.debug else {}