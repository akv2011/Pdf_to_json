"""
Hierarchical Structure Builder for PDF content.

This module implements the StructureBuilder class that converts flat content blocks
into a nested, hierarchical document structure based on header levels and content flow.
"""

from typing import List, Dict, Any, Optional, Union
from collections import deque

from .models import (
    DocumentStructure, SectionNode, HeaderLevel, ContentType, 
    TextBlock, Table, ImageInfo, PageContent, BoundingBox
)


class HeaderStack:
    """Stack-based manager for tracking current section hierarchy."""
    
    def __init__(self):
        """Initialize the header stack."""
        self._stack: List[SectionNode] = []
        self._level_map: Dict[int, SectionNode] = {}  # level -> current section at that level
    
    def push(self, section: SectionNode) -> None:
        """Push a new section onto the stack.
        
        This automatically handles popping sections at equal or higher levels
        and maintains the proper parent-child relationships.
        
        Args:
            section: The section to push onto the stack
        """
        level = section.level.value
        
        # Pop sections at equal or higher levels (lower numbers = higher hierarchy)
        while self._stack and self._stack[-1].level.value >= level:
            popped = self._stack.pop()
            if popped.level.value in self._level_map:
                del self._level_map[popped.level.value]
        
        # Add as subsection to the current parent (if any)
        if self._stack:
            parent = self._stack[-1]
            parent.add_subsection(section)
        
        # Push the new section
        self._stack.append(section)
        self._level_map[level] = section
    
    def get_current_section(self) -> Optional[SectionNode]:
        """Get the current active section (top of stack)."""
        return self._stack[-1] if self._stack else None
    
    def get_section_at_level(self, level: int) -> Optional[SectionNode]:
        """Get the current section at a specific level."""
        return self._level_map.get(level)
    
    def clear(self) -> None:
        """Clear the stack."""
        self._stack.clear()
        self._level_map.clear()
    
    def is_empty(self) -> bool:
        """Check if the stack is empty."""
        return len(self._stack) == 0
    
    def get_root_sections(self) -> List[SectionNode]:
        """Get all top-level sections from the stack history."""
        # Find the deepest level that has been processed
        if not self._level_map:
            return []
        
        min_level = min(self._level_map.keys())
        root_section = self._level_map[min_level]
        
        # Walk up to find the true root
        current = root_section
        while hasattr(current, '_parent') and current._parent:
            current = current._parent
        
        return [current] if current else []


class StructureBuilder:
    """Builds hierarchical document structure from flat content blocks."""
    
    def __init__(self, 
                 debug: bool = False,
                 auto_detect_headers: bool = True,
                 min_header_font_size: float = 12.0):
        """Initialize the structure builder.
        
        Args:
            debug: If True, store debug information during processing
            auto_detect_headers: If True, attempt to detect header levels from font sizes
            min_header_font_size: Minimum font size to consider for header detection
        """
        self.debug = debug
        self.auto_detect_headers = auto_detect_headers
        self.min_header_font_size = min_header_font_size
        self._debug_info: Dict[str, Any] = {}
    
    def build_structure(self, 
                       pages: List[PageContent],
                       title: Optional[str] = None) -> DocumentStructure:
        """Build hierarchical structure from pages of content.
        
        Args:
            pages: List of PageContent objects with classified content
            title: Optional document title
            
        Returns:
            DocumentStructure with nested sections and content
        """
        # Initialize document structure
        doc = DocumentStructure(
            title=title,
            total_pages=len(pages),
            metadata={"processing_method": "StructureBuilder"}
        )
        
        # Initialize header stack
        header_stack = HeaderStack()
        
        # Track all content blocks across pages
        all_blocks = []
        
        # Collect all content blocks from all pages
        for page in pages:
            page_blocks = self._extract_content_blocks(page)
            all_blocks.extend(page_blocks)
        
        if self.debug:
            self._debug_info["total_blocks"] = len(all_blocks)
            self._debug_info["block_types"] = {}
        
        # Process blocks sequentially to build hierarchy
        for block in all_blocks:
            if self.debug:
                block_type = self._get_block_type(block)
                self._debug_info["block_types"][block_type] = \
                    self._debug_info["block_types"].get(block_type, 0) + 1
            
            if self._is_header_block(block):
                # Create new section for header
                section = self._create_section_from_header(block)
                header_stack.push(section)
                
                # If this is a top-level section, add to document
                if section.level == HeaderLevel.H1:
                    doc.add_section(section)
            
            else:
                # Use enhanced content association logic
                self._associate_content_with_section(block, header_stack, doc)
        
        if self.debug:
            doc.metadata["debug_info"] = self._debug_info
        
        return doc
    
    def _extract_content_blocks(self, page: PageContent) -> List[Union[TextBlock, Table, ImageInfo]]:
        """Extract all content blocks from a page in reading order.
        
        Args:
            page: PageContent to extract from
            
        Returns:
            List of content blocks sorted by reading order
        """
        blocks = []
        
        # Add text blocks
        for text_block in page.text_blocks:
            # Add page number information
            text_block.metadata = text_block.metadata or {}
            text_block.metadata['page_number'] = page.page_number
            blocks.append(text_block)
        
        # Add tables
        for table in page.tables:
            # Add page number information
            table.metadata = getattr(table, 'metadata', {})
            table.metadata['page_number'] = page.page_number
            blocks.append(table)
        
        # Add images
        for image in page.images:
            # Add page number information  
            image.metadata = getattr(image, 'metadata', {})
            image.metadata['page_number'] = page.page_number
            blocks.append(image)
        
        # Sort by vertical position (reading order)
        def get_sort_key(block):
            if hasattr(block, 'bbox') and block.bbox:
                return (block.bbox.y0, block.bbox.x0)
            return (0, 0)  # Default for blocks without position
        
        blocks.sort(key=get_sort_key)
        return blocks
    
    def _is_header_block(self, block: Union[TextBlock, Table, ImageInfo]) -> bool:
        """Check if a block represents a header.
        
        Args:
            block: Content block to check
            
        Returns:
            True if the block is a header
        """
        if hasattr(block, 'content_type'):
            return block.content_type.is_header_type()
        return False
    
    def _get_block_type(self, block: Union[TextBlock, Table, ImageInfo]) -> str:
        """Get a string representation of the block type for debugging."""
        if hasattr(block, 'content_type'):
            return block.content_type.value
        elif hasattr(block, 'rows'):  # Table
            return "table"
        elif hasattr(block, 'format'):  # Image
            return "image"
        else:
            return "unknown"
    
    def _associate_content_with_section(self, 
                                       content_block: Union[TextBlock, Table, ImageInfo],
                                       header_stack: HeaderStack,
                                       doc: DocumentStructure) -> None:
        """Associate a content block with the appropriate section in the hierarchy.
        
        This is the enhanced content association logic that handles different content types
        and determines the best section placement.
        
        Args:
            content_block: The content block to associate
            header_stack: Current header stack state
            doc: Document structure being built
        """
        # Get the current active section
        current_section = header_stack.get_current_section()
        
        if current_section:
            # We have an active section - add content to it
            self._add_content_to_section(content_block, current_section)
        else:
            # No active section - create a default section
            default_section = self._create_default_section(content_block)
            header_stack.push(default_section)
            doc.add_section(default_section)
            self._add_content_to_section(content_block, default_section)
    
    def _add_content_to_section(self, 
                               content_block: Union[TextBlock, Table, ImageInfo],
                               section: SectionNode) -> None:
        """Add a content block to a section with enhanced metadata handling.
        
        Args:
            content_block: Content block to add
            section: Section to add it to
        """
        # Enhance metadata before adding to section
        self._enhance_content_metadata(content_block, section)
        
        # Add to section
        section.add_content(content_block)
        
        # Track content statistics in section metadata
        self._update_section_content_stats(section, content_block)
    
    def _enhance_content_metadata(self, 
                                 content_block: Union[TextBlock, Table, ImageInfo],
                                 section: SectionNode) -> None:
        """Enhance content block metadata with section context.
        
        Args:
            content_block: Content block to enhance
            section: Parent section providing context
        """
        # Ensure metadata exists
        if not hasattr(content_block, 'metadata') or content_block.metadata is None:
            content_block.metadata = {}
        
        # Add section context
        content_block.metadata['parent_section'] = {
            'title': section.title,
            'level': section.level.value,
            'section_id': id(section)  # Unique identifier for this section
        }
        
        # Add content type specific metadata
        block_type = self._get_block_type(content_block)
        content_block.metadata['content_type_category'] = block_type
        
        # Add positional context within section
        current_content_count = len(section.content_blocks)
        content_block.metadata['position_in_section'] = current_content_count
    
    def _update_section_content_stats(self, 
                                     section: SectionNode,
                                     content_block: Union[TextBlock, Table, ImageInfo]) -> None:
        """Update section metadata with content statistics.
        
        Args:
            section: Section to update
            content_block: Content block being added
        """
        # Ensure section metadata exists
        if not hasattr(section, 'metadata') or section.metadata is None:
            section.metadata = {}
        
        # Initialize content stats if not present
        if 'content_stats' not in section.metadata:
            section.metadata['content_stats'] = {
                'total_blocks': 0,
                'text_blocks': 0,
                'tables': 0,
                'images': 0,
                'paragraphs': 0,
                'lists': 0,
                'other': 0
            }
        
        stats = section.metadata['content_stats']
        stats['total_blocks'] += 1
        
        # Update type-specific counts
        block_type = self._get_block_type(content_block)
        if block_type == 'table':
            stats['tables'] += 1
        elif block_type == 'image':
            stats['images'] += 1
        elif hasattr(content_block, 'content_type'):
            if content_block.content_type == ContentType.PARAGRAPH:
                stats['paragraphs'] += 1
            elif content_block.content_type in [ContentType.LIST_ITEM, ContentType.BULLET_LIST]:
                stats['lists'] += 1
            else:
                stats['text_blocks'] += 1
        else:
            stats['other'] += 1
    
    def _create_default_section(self, 
                               content_block: Union[TextBlock, Table, ImageInfo]) -> SectionNode:
        """Create a default section for orphaned content.
        
        Args:
            content_block: Content block that needs a section
            
        Returns:
            Default section for the content
        """
        # Determine page number from content block
        page_number = None
        if hasattr(content_block, 'metadata') and content_block.metadata:
            page_number = content_block.metadata.get('page_number')
        
        # Create descriptive title based on content type
        block_type = self._get_block_type(content_block)
        if block_type == 'table':
            title = "Tables and Data"
        elif block_type == 'image':
            title = "Images and Figures"
        else:
            title = "Content"
        
        # Create section
        section = SectionNode(
            title=title,
            level=HeaderLevel.H1,
            page_number=page_number,
            metadata={
                'is_default_section': True,
                'created_for_content_type': block_type,
                'auto_generated': True
            }
        )
        
        return section
    
    def _group_related_content_blocks(self, 
                                     blocks: List[Union[TextBlock, Table, ImageInfo]]) -> List[List[Union[TextBlock, Table, ImageInfo]]]:
        """Group related content blocks together for better processing.
        
        This method identifies content blocks that should be processed together,
        such as consecutive paragraphs, list items, or table-related content.
        
        Args:
            blocks: List of content blocks to group
            
        Returns:
            List of grouped content blocks
        """
        if not blocks:
            return []
        
        groups = []
        current_group = [blocks[0]]
        
        for i in range(1, len(blocks)):
            current_block = blocks[i]
            prev_block = blocks[i-1]
            
            # Check if blocks should be grouped together
            if self._should_group_blocks(prev_block, current_block):
                current_group.append(current_block)
            else:
                # Start a new group
                groups.append(current_group)
                current_group = [current_block]
        
        # Add the last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _should_group_blocks(self, 
                            block1: Union[TextBlock, Table, ImageInfo],
                            block2: Union[TextBlock, Table, ImageInfo]) -> bool:
        """Determine if two consecutive blocks should be grouped together.
        
        Args:
            block1: First block
            block2: Second block
            
        Returns:
            True if blocks should be grouped
        """
        # Don't group headers with anything
        if self._is_header_block(block1) or self._is_header_block(block2):
            return False
        
        # Group consecutive paragraphs
        if (hasattr(block1, 'content_type') and hasattr(block2, 'content_type') and
            block1.content_type == ContentType.PARAGRAPH and 
            block2.content_type == ContentType.PARAGRAPH):
            
            # Check if they're close vertically (on same page)
            if (hasattr(block1, 'bbox') and hasattr(block2, 'bbox') and
                block1.bbox and block2.bbox):
                vertical_gap = abs(block2.bbox.y0 - block1.bbox.y1)
                return vertical_gap < 50  # Threshold for paragraph grouping
        
        # Group consecutive list items
        if (hasattr(block1, 'content_type') and hasattr(block2, 'content_type') and
            block1.content_type == ContentType.LIST_ITEM and 
            block2.content_type == ContentType.LIST_ITEM):
            return True
        
        # Don't group different types by default
        return False
    
    def _create_section_from_header(self, header_block: TextBlock) -> SectionNode:
        """Create a SectionNode from a header block.
        
        Args:
            header_block: TextBlock representing a header
            
        Returns:
            SectionNode for the header
        """
        # Determine header level
        header_level = self._determine_header_level(header_block)
        
        # Extract title text
        title = header_block.text.strip()
        
        # Get page number
        page_number = header_block.metadata.get('page_number') if header_block.metadata else None
        
        # Create section
        section = SectionNode(
            title=title,
            level=header_level,
            bbox=header_block.bbox,
            page_number=page_number,
            metadata={
                'header_block': {
                    'content_type': header_block.content_type.value,
                    'confidence': header_block.confidence,
                    'font_info': self._extract_font_info(header_block)
                }
            }
        )
        
        return section
    
    def _determine_header_level(self, header_block: TextBlock) -> HeaderLevel:
        """Determine the header level from a header block.
        
        Args:
            header_block: TextBlock representing a header
            
        Returns:
            HeaderLevel for the header
        """
        # First try to get level from content type
        if hasattr(header_block.content_type, 'get_header_level'):
            level_num = header_block.content_type.get_header_level()
            if level_num:
                return HeaderLevel.from_int(level_num)
        
        # If auto-detection is enabled, try to infer from font size
        if self.auto_detect_headers and hasattr(header_block, 'font_info'):
            return self._infer_header_level_from_font(header_block)
        
        # Default to H1
        return HeaderLevel.H1
    
    def _infer_header_level_from_font(self, header_block: TextBlock) -> HeaderLevel:
        """Infer header level from font characteristics.
        
        This is a simple heuristic that can be improved with more sophisticated analysis.
        
        Args:
            header_block: TextBlock with font information
            
        Returns:
            Inferred HeaderLevel
        """
        if not hasattr(header_block, 'font_info') or not header_block.font_info:
            return HeaderLevel.H1
        
        font_info = header_block.font_info
        font_size = font_info.get('font_size', 12.0) if isinstance(font_info, dict) else getattr(font_info, 'font_size', 12.0)
        is_bold = font_info.get('is_bold', False) if isinstance(font_info, dict) else getattr(font_info, 'is_bold', False)
        
        # Simple heuristic based on font size and bold
        if font_size >= 18:
            return HeaderLevel.H1
        elif font_size >= 16:
            return HeaderLevel.H2
        elif font_size >= 14:
            return HeaderLevel.H3
        elif is_bold and font_size >= 12:
            return HeaderLevel.H4
        elif font_size >= 12:
            return HeaderLevel.H5
        else:
            return HeaderLevel.H6
    
    def _extract_font_info(self, block: TextBlock) -> Dict[str, Any]:
        """Extract font information from a text block for metadata.
        
        Args:
            block: TextBlock to extract font info from
            
        Returns:
            Dictionary with font information
        """
        if not hasattr(block, 'font_info') or not block.font_info:
            return {}
        
        font_info = block.font_info
        if isinstance(font_info, dict):
            return font_info.copy()
        else:
            # Assume it's a FontInfo object
            return {
                'font_name': getattr(font_info, 'font_name', ''),
                'font_size': getattr(font_info, 'font_size', 12.0),
                'is_bold': getattr(font_info, 'is_bold', False),
                'is_italic': getattr(font_info, 'is_italic', False),
                'flags': getattr(font_info, 'flags', 0),
                'color': getattr(font_info, 'color', 0)
            }
    
    def process_with_classifier(self, 
                              pages: List[PageContent],
                              classifier,
                              title: Optional[str] = None) -> DocumentStructure:
        """Process pages using a content classifier first, then build structure.
        
        This method integrates with the ContentClassifier from Task 4 to first
        classify content types, then build the hierarchical structure.
        
        Args:
            pages: List of PageContent objects
            classifier: ContentClassifier instance
            title: Optional document title
            
        Returns:
            DocumentStructure with nested sections and content
        """
        # First, classify content on each page
        for page in pages:
            classified_blocks = classifier.classify_page_content(page)
            # Replace the page's text_blocks with classified blocks
            page.text_blocks = classified_blocks
        
        # Then build the structure
        return self.build_structure(pages, title)
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information from the last processing run."""
        return self._debug_info.copy()
    
    def build_from_text_blocks(self, 
                             text_blocks: List[TextBlock],
                             title: Optional[str] = None) -> DocumentStructure:
        """Build structure directly from a list of text blocks.
        
        This is a convenience method for when you already have classified text blocks
        and don't need to process full PageContent objects.
        
        Args:
            text_blocks: List of classified TextBlock objects
            title: Optional document title
            
        Returns:
            DocumentStructure with nested sections and content
        """
        # Sort blocks by position if they have bbox information
        def get_sort_key(block):
            if hasattr(block, 'bbox') and block.bbox:
                return (block.bbox.y0, block.bbox.x0)
            return (0, 0)
        
        sorted_blocks = sorted(text_blocks, key=get_sort_key)
        
        # Initialize document and header stack
        doc = DocumentStructure(title=title, metadata={"processing_method": "StructureBuilder.build_from_text_blocks"})
        header_stack = HeaderStack()
        
        # Process each block
        for block in sorted_blocks:
            if self._is_header_block(block):
                section = self._create_section_from_header(block)
                header_stack.push(section)
                
                if section.level == HeaderLevel.H1:
                    doc.add_section(section)
            else:
                # Use enhanced content association logic
                self._associate_content_with_section(block, header_stack, doc)
        
        return doc