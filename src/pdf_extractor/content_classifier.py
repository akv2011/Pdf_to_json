"""
Content classification module for PDF text analysis.

This module implements rule-based classification to distinguish between different
content types such as headers, paragraphs, and lists based on font attributes
and layout characteristics.
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import re

from .models import (
    PageContent, ContentBlock, TextSpan, FontInfo, ContentType, TextBlock, BoundingBox
)


class ContentClassifier:
    """Rule-based classifier for PDF content type identification."""
    
    def __init__(self, debug: bool = False):
        """Initialize the content classifier.
        
        Args:
            debug: If True, store debug information during classification
        """
        self.debug = debug
        self.baseline_font_style: Optional[Dict[str, Any]] = None
        self._debug_info: Dict[str, Any] = {}
    
    def classify_page_content(self, page_content: PageContent) -> List[TextBlock]:
        """Classify all text content on a page into structured blocks.
        
        Args:
            page_content: Processed page content with detailed structure
            
        Returns:
            List of classified TextBlock objects
        """
        # First, establish the baseline body text style
        self._establish_baseline_style(page_content)
        
        # Collect all text spans with their spatial information
        all_spans_info = []
        for content_block in page_content.content_blocks:
            if content_block.is_text_block:
                for line in content_block.lines:
                    for span in line.spans:
                        if span.text.strip():  # Only process non-empty text
                            span_info = {
                                'span': span,
                                'content_block': content_block,
                                'y_position': span.bbox.y0,  # Use top of bbox for sorting
                                'content_type': None,  # Will be determined
                                'should_group': True   # Can be grouped with adjacent spans
                            }
                            all_spans_info.append(span_info)
        
        # Sort spans by vertical position (reading order)
        # Sort by y position (smaller y = higher on page = earlier in reading order)
        all_spans_info.sort(key=lambda x: (x['y_position'], x['span'].bbox.x0))
        
        # First pass: identify headers and list items (these break paragraph flow)
        for span_info in all_spans_info:
            span = span_info['span']
            
            if self._is_list_item(span):
                span_info['content_type'] = ContentType.LIST
                span_info['should_group'] = False  # List items don't group
            elif self._is_header(span):
                span_info['content_type'] = ContentType.HEADER
                span_info['should_group'] = False  # Headers don't group
            else:
                span_info['content_type'] = ContentType.PARAGRAPH
                span_info['should_group'] = True
        
        # Second pass: group adjacent paragraph spans
        grouped_spans = self._group_paragraph_spans(all_spans_info)
        
        # Create TextBlock objects from grouped spans
        classified_blocks = []
        for group in grouped_spans:
            text_block = self._create_text_block_from_group(group)
            if text_block:
                classified_blocks.append(text_block)
        
        return classified_blocks
    
    def _establish_baseline_style(self, page_content: PageContent) -> None:
        """Analyze all text spans to determine the most common font style.
        
        This establishes a baseline for 'body text' by finding the modal
        font size, name, and style attributes.
        
        Args:
            page_content: Page content to analyze
        """
        # Collect all font characteristics from text spans
        font_sizes = []
        font_names = []
        is_bold_flags = []
        is_italic_flags = []
        
        for content_block in page_content.content_blocks:
            if content_block.is_text_block:
                for line in content_block.lines:
                    for span in line.spans:
                        if span.text.strip():  # Only count non-empty spans
                            font_sizes.append(span.font_info.font_size)
                            font_names.append(span.font_info.font_name)
                            is_bold_flags.append(span.font_info.is_bold)
                            is_italic_flags.append(span.font_info.is_italic)
        
        if not font_sizes:
            # No text found, use defaults
            self.baseline_font_style = {
                'size': 12.0,
                'font': 'Unknown',
                'bold': False,
                'italic': False
            }
            return
        
        # Calculate the most common (modal) values
        size_counter = Counter(font_sizes)
        font_counter = Counter(font_names)
        bold_counter = Counter(is_bold_flags)
        italic_counter = Counter(is_italic_flags)
        
        # Get the most common values
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
        
        # Store debug information if enabled
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
        """Classify a single text span into a content type.
        
        Args:
            span: Text span to classify
            parent_block: Parent content block for context
            
        Returns:
            Classified TextBlock or None if span should be skipped
        """
        text = span.text.strip()
        if not text:
            return None
        
        # Create font info dictionary for the text block
        font_info = {
            'name': span.font_info.font_name,
            'size': span.font_info.font_size,
            'bold': span.font_info.is_bold,
            'italic': span.font_info.is_italic,
            'flags': span.font_info.flags,
            'color': span.font_info.color
        }
        
        # Determine content type
        content_type = self._determine_content_type(span)
        
        # Create metadata with baseline comparison
        metadata = {
            'block_number': parent_block.block_number,
            'baseline_comparison': self._compare_to_baseline(span.font_info)
        }
        
        # Add header level if this is a header
        if content_type == ContentType.HEADER:
            metadata['header_level'] = self._get_header_level(span)
        
        # Add list marker information if this is a list item
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
        """Determine the content type for a text span.
        
        Args:
            span: Text span to classify
            
        Returns:
            ContentType enum value
        """
        # Check for list items first (they can override header detection)
        if self._is_list_item(span):
            return ContentType.LIST
            
        # Check for header characteristics
        if self._is_header(span):
            return ContentType.HEADER
        
        # TODO: Add paragraph grouping logic in subsequent subtask
        
        # Default to paragraph for now
        return ContentType.PARAGRAPH
    
    def _compare_to_baseline(self, font_info: FontInfo) -> Dict[str, Any]:
        """Compare font characteristics to the established baseline.
        
        Args:
            font_info: Font information to compare
            
        Returns:
            Dictionary with comparison results
        """
        if not self.baseline_font_style:
            return {}
        
        baseline = self.baseline_font_style
        
        # Calculate size ratio
        size_ratio = font_info.font_size / baseline['size'] if baseline['size'] > 0 else 1.0
        
        return {
            'size_ratio': size_ratio,
            'is_larger': font_info.font_size > baseline['size'],
            'is_smaller': font_info.font_size < baseline['size'],
            'font_matches': font_info.font_name == baseline['font'],
            'bold_differs': font_info.is_bold != baseline['bold'],
            'italic_differs': font_info.is_italic != baseline['italic'],
            'significantly_larger': size_ratio >= 1.2,  # 20% larger threshold
            'significantly_smaller': size_ratio <= 0.8   # 20% smaller threshold
        }
    
    def _is_header(self, span: TextSpan) -> bool:
        """Determine if a text span represents a header.
        
        Headers are identified by:
        1. Font size significantly larger than baseline (>120% of baseline)
        2. Bold weight when baseline is not bold
        3. Different font family that suggests emphasis
        
        Args:
            span: Text span to evaluate
            
        Returns:
            True if span appears to be a header, False otherwise
        """
        if not self.baseline_font_style:
            return False
        
        baseline = self.baseline_font_style
        font_info = span.font_info
        
        # Calculate size ratio
        size_ratio = font_info.font_size / baseline['size'] if baseline['size'] > 0 else 1.0
        
        # Header detection criteria
        is_significantly_larger = size_ratio >= 1.2  # 20% larger than baseline
        is_bold_when_baseline_not = font_info.is_bold and not baseline['bold']
        is_much_larger = size_ratio >= 1.5  # 50% larger is almost certainly a header
        
        # Special case: if text is much larger, it's likely a header regardless of other factors
        if is_much_larger:
            return True
        
        # Primary criteria: significantly larger OR bold when baseline isn't
        if is_significantly_larger or is_bold_when_baseline_not:
            # Additional heuristics to reduce false positives
            
            # Very short text (1-3 words) is more likely to be a header
            word_count = len(span.text.strip().split())
            is_short = word_count <= 3
            
            # Text that's all caps might be a header
            is_caps = span.text.strip().isupper()
            
            # If it meets basic criteria and has supporting evidence, it's a header
            if is_short or is_caps or is_bold_when_baseline_not:
                return True
            
            # If it's only slightly larger, require bold or caps
            if 1.2 <= size_ratio < 1.4:
                return is_bold_when_baseline_not or is_caps
            
            # If it's moderately larger, it's probably a header
            if size_ratio >= 1.4:
                return True
        
        return False
    
    def _get_header_level(self, span: TextSpan) -> int:
        """Determine the header level (H1, H2, etc.) based on font characteristics.
        
        Args:
            span: Text span that has been identified as a header
            
        Returns:
            Header level (1-6, where 1 is the largest/most important)
        """
        if not self.baseline_font_style:
            return 1
        
        baseline = self.baseline_font_style
        size_ratio = span.font_info.font_size / baseline['size'] if baseline['size'] > 0 else 1.0
        
        # Determine level based on size ratio
        if size_ratio >= 2.0:      # 200% of baseline
            return 1  # H1
        elif size_ratio >= 1.7:    # 170% of baseline  
            return 2  # H2
        elif size_ratio >= 1.4:    # 140% of baseline
            return 3  # H3
        elif size_ratio >= 1.2:    # 120% of baseline
            return 4  # H4
        else:
            # For headers detected by bold/other criteria but not size
            return 5  # H5
    
    def _is_list_item(self, span: TextSpan) -> bool:
        """Determine if a text span represents a list item.
        
        List items are identified by common prefixes such as:
        - Bullet points: •, *, -, +
        - Numbers: 1., 2), (1), [1]
        - Letters: a), b., A), A.
        - Roman numerals: i., ii), (I), [II]
        
        Args:
            span: Text span to evaluate
            
        Returns:
            True if span appears to be a list item, False otherwise
        """
        text = span.text.strip()
        if not text:
            return False
        
        # Common list item patterns
        list_patterns = [
            # Bullet points with various symbols
            r'^\s*[•·▪▫‣⁃]\s+',           # Unicode bullets
            r'^\s*[*+\-]\s+',             # ASCII bullets  
            r'^\s*[▶►▷▸]\s+',             # Arrow bullets
            
            # Numbered lists
            r'^\s*\d+\.\s+',              # 1. 2. 3.
            r'^\s*\d+\)\s+',              # 1) 2) 3)
            r'^\s*\(\d+\)\s+',            # (1) (2) (3)
            r'^\s*\[\d+\]\s+',            # [1] [2] [3]
            
            # Lettered lists  
            r'^\s*[a-zA-Z]\.\s+',         # a. b. c. or A. B. C.
            r'^\s*[a-zA-Z]\)\s+',         # a) b) c) or A) B) C)
            r'^\s*\([a-zA-Z]\)\s+',       # (a) (b) (c) or (A) (B) (C)
            r'^\s*\[[a-zA-Z]\]\s+',       # [a] [b] [c] or [A] [B] [C]
            
            # Roman numerals (basic patterns)
            r'^\s*[ivxlcdm]+\.\s+',       # i. ii. iii. iv. (lowercase)
            r'^\s*[IVXLCDM]+\.\s+',       # I. II. III. IV. (uppercase)
            r'^\s*[ivxlcdm]+\)\s+',       # i) ii) iii) iv)
            r'^\s*[IVXLCDM]+\)\s+',       # I) II) III) IV)
            r'^\s*\([ivxlcdm]+\)\s+',     # (i) (ii) (iii) (iv)
            r'^\s*\([IVXLCDM]+\)\s+',     # (I) (II) (III) (IV)
        ]
        
        # Check if text matches any list pattern
        for pattern in list_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _get_list_marker_type(self, span: TextSpan) -> str:
        """Determine the type of list marker used.
        
        Args:
            span: Text span that has been identified as a list item
            
        Returns:
            String describing the list marker type
        """
        text = span.text.strip()
        
        # Categorize the list marker
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
        """Group adjacent paragraph spans that should be merged.
        
        Args:
            all_spans_info: List of span info dictionaries sorted by position
            
        Returns:
            List of groups, where each group is a list of span info dictionaries
        """
        groups = []
        current_group = []
        
        for i, span_info in enumerate(all_spans_info):
            # Headers and list items always start a new group
            if not span_info['should_group']:
                # Finish current paragraph group if any
                if current_group:
                    groups.append(current_group)
                    current_group = []
                
                # Add this span as its own group
                groups.append([span_info])
                continue
            
            # This is a paragraph span - check if it should be grouped with previous
            if current_group and self._should_group_with_previous(span_info, current_group[-1]):
                current_group.append(span_info)
            else:
                # Start a new paragraph group
                if current_group:
                    groups.append(current_group)
                current_group = [span_info]
        
        # Don't forget the last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _should_group_with_previous(self, current_span_info: Dict, previous_span_info: Dict) -> bool:
        """Determine if two paragraph spans should be grouped together.
        
        Args:
            current_span_info: Current span information
            previous_span_info: Previous span information
            
        Returns:
            True if spans should be grouped, False otherwise
        """
        current_span = current_span_info['span']
        previous_span = previous_span_info['span']
        
        # Calculate vertical distance between spans
        vertical_distance = abs(previous_span.bbox.y1 - current_span.bbox.y0)
        
        # Use font size to determine reasonable line spacing
        avg_font_size = (current_span.font_info.font_size + previous_span.font_info.font_size) / 2
        max_line_spacing = avg_font_size * 1.5  # Allow up to 1.5x font size spacing
        
        # Check if spans are close enough vertically
        if vertical_distance > max_line_spacing:
            return False
        
        # Check if font styles are similar enough
        if not self._fonts_similar(current_span.font_info, previous_span.font_info):
            return False
        
        # Check horizontal alignment (rough left margin alignment)
        left_margin_diff = abs(current_span.bbox.x0 - previous_span.bbox.x0)
        if left_margin_diff > avg_font_size * 0.5:  # Allow small alignment variations
            return False
        
        return True
    
    def _fonts_similar(self, font1: FontInfo, font2: FontInfo) -> bool:
        """Check if two fonts are similar enough to be grouped.
        
        Args:
            font1: First font to compare
            font2: Second font to compare
            
        Returns:
            True if fonts are similar enough to group
        """
        # Same font family
        if font1.font_name != font2.font_name:
            return False
        
        # Similar size (within 10% tolerance)
        size_ratio = font1.font_size / font2.font_size if font2.font_size > 0 else 1.0
        if size_ratio < 0.9 or size_ratio > 1.1:
            return False
        
        # Same bold/italic status
        if font1.is_bold != font2.is_bold or font1.is_italic != font2.is_italic:
            return False
        
        return True
    
    def _create_text_block_from_group(self, group: List[Dict]) -> Optional[TextBlock]:
        """Create a TextBlock from a group of span info dictionaries.
        
        Args:
            group: List of span info dictionaries to merge
            
        Returns:
            TextBlock object or None if group is empty
        """
        if not group:
            return None
        
        # For single-span groups, use the existing logic
        if len(group) == 1:
            span_info = group[0]
            return self._classify_text_span(span_info['span'], span_info['content_block'])
        
        # For multi-span groups (paragraphs), merge them
        first_span_info = group[0]
        content_type = first_span_info['content_type']
        
        # Combine all text with spaces
        combined_text = ' '.join(span_info['span'].text.strip() for span_info in group)
        
        # Calculate combined bounding box
        min_x0 = min(span_info['span'].bbox.x0 for span_info in group)
        min_y0 = min(span_info['span'].bbox.y0 for span_info in group)
        max_x1 = max(span_info['span'].bbox.x1 for span_info in group)
        max_y1 = max(span_info['span'].bbox.y1 for span_info in group)
        combined_bbox = BoundingBox(min_x0, min_y0, max_x1, max_y1)
        
        # Use font info from the first span as representative
        first_span = first_span_info['span']
        font_info = {
            'name': first_span.font_info.font_name,
            'size': first_span.font_info.font_size,
            'bold': first_span.font_info.is_bold,
            'italic': first_span.font_info.is_italic,
            'flags': first_span.font_info.flags,
            'color': first_span.font_info.color
        }
        
        # Create metadata
        metadata = {
            'block_number': first_span_info['content_block'].block_number,
            'baseline_comparison': self._compare_to_baseline(first_span.font_info),
            'span_count': len(group),  # How many spans were merged
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
        """Get the established baseline font style.
        
        Returns:
            Dictionary with baseline style information or None if not established
        """
        return self.baseline_font_style.copy() if self.baseline_font_style else None
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information from the classification process.
        
        Returns:
            Dictionary with debug information (empty if debug=False)
        """
        return self._debug_info.copy() if self.debug else {}