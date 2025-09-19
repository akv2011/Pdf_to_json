"""
Tests for Task 3: Page-Level Content Block and Layout Analysis
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from pdf_extractor.page_processor import PageProcessor
from pdf_extractor.models import PageContent


class TestPageProcessor:
    """Test cases for PageProcessor class."""
    
    def test_page_processor_initialization(self):
        """Test that PageProcessor initializes correctly."""
        processor = PageProcessor(debug=True)
        assert processor.debug is True
        
        processor_default = PageProcessor()
        assert processor_default.debug is False
    
    @patch('pdf_extractor.page_processor.fitz')
    def test_process_page_with_text_content(self, mock_fitz):
        """Test processing a page with text content blocks."""
        # Create mock page
        mock_page = Mock()
        mock_page.rect.width = 595.0
        mock_page.rect.height = 842.0
        mock_page.rotation = 0
        
        # Mock the get_text("dict", sort=True) response
        mock_text_dict = {
            'width': 595.0,
            'height': 842.0,
            'blocks': [
                {
                    'number': 0,
                    'type': 0,  # Text block
                    'bbox': (50, 50, 200, 80),
                    'lines': [
                        {
                            'wmode': 0,
                            'dir': (1, 0),
                            'bbox': (50, 50, 200, 80),
                            'spans': [
                                {
                                    'text': 'Sample Header Text',
                                    'bbox': (50, 50, 200, 80),
                                    'font': 'Arial-Bold',
                                    'size': 18.0,
                                    'flags': 16,  # Bold flag
                                    'color': 0,
                                    'origin': (50, 70)
                                }
                            ]
                        }
                    ]
                },
                {
                    'number': 1,
                    'type': 0,  # Text block
                    'bbox': (50, 100, 300, 150),
                    'lines': [
                        {
                            'wmode': 0,
                            'dir': (1, 0),
                            'bbox': (50, 100, 300, 150),
                            'spans': [
                                {
                                    'text': 'This is body text with normal formatting.',
                                    'bbox': (50, 100, 300, 150),
                                    'font': 'Arial',
                                    'size': 12.0,
                                    'flags': 0,  # No special formatting
                                    'color': 0,
                                    'origin': (50, 130)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        mock_page.get_text.return_value = mock_text_dict
        
        # Test page processing
        processor = PageProcessor()
        result = processor.process_page(mock_page, 1)
        
        # Verify basic page information
        assert isinstance(result, PageContent)
        assert result.page_number == 1
        assert result.page_width == 595.0
        assert result.page_height == 842.0
        assert result.rotation == 0
        
        # Verify content blocks were processed
        assert len(result.content_blocks) == 2
        
        # Check first block (header)
        header_block = result.content_blocks[0]
        assert header_block.block_number == 0
        assert header_block.is_text_block
        assert not header_block.is_image_block
        assert header_block.text == "Sample Header Text"
        assert len(header_block.lines) == 1
        
        # Check header font information
        header_span = header_block.lines[0].spans[0]
        assert header_span.text == "Sample Header Text"
        assert header_span.font_info.font_name == "Arial-Bold"
        assert header_span.font_info.font_size == 18.0
        assert header_span.font_info.is_bold is True
        assert header_span.font_info.is_italic is False
        
        # Check second block (body text)
        body_block = result.content_blocks[1]
        assert body_block.block_number == 1
        assert body_block.text == "This is body text with normal formatting."
        
        # Check body font information
        body_span = body_block.lines[0].spans[0]
        assert body_span.font_info.font_name == "Arial"
        assert body_span.font_info.font_size == 12.0
        assert body_span.font_info.is_bold is False
    
    @patch('pdf_extractor.page_processor.fitz')
    def test_process_page_with_image_block(self, mock_fitz):
        """Test processing a page with image blocks."""
        mock_page = Mock()
        mock_page.rect.width = 595.0
        mock_page.rect.height = 842.0
        mock_page.rotation = 0
        
        # Mock response with image block
        mock_text_dict = {
            'width': 595.0,
            'height': 842.0,
            'blocks': [
                {
                    'number': 0,
                    'type': 1,  # Image block
                    'bbox': (100, 100, 400, 300)
                    # Image blocks don't have 'lines'
                }
            ]
        }
        
        mock_page.get_text.return_value = mock_text_dict
        
        processor = PageProcessor()
        result = processor.process_page(mock_page, 1)
        
        # Verify image block processing
        assert len(result.content_blocks) == 1
        image_block = result.content_blocks[0]
        assert image_block.block_number == 0
        assert image_block.is_image_block
        assert not image_block.is_text_block
        assert len(image_block.lines) == 0  # Image blocks have no lines
    
    def test_get_page_statistics(self):
        """Test page statistics calculation."""
        # Create a mock page content with some data
        page_content = PageContent(page_number=1)
        
        # Add some mock content blocks
        from pdf_extractor.models import ContentBlock, TextLine, TextSpan, FontInfo, BoundingBox
        
        # Text block
        text_span = TextSpan(
            text="Test text",
            bbox=BoundingBox(0, 0, 100, 20),
            font_info=FontInfo(font_name="Arial", font_size=12.0)
        )
        text_line = TextLine(
            spans=[text_span],
            bbox=BoundingBox(0, 0, 100, 20)
        )
        text_block = ContentBlock(
            block_number=0,
            block_type=0,  # Text
            bbox=BoundingBox(0, 0, 100, 20),
            lines=[text_line]
        )
        
        # Image block
        image_block = ContentBlock(
            block_number=1,
            block_type=1,  # Image
            bbox=BoundingBox(0, 30, 100, 100)
        )
        
        page_content.content_blocks = [text_block, image_block]
        
        processor = PageProcessor()
        stats = processor.get_page_statistics(page_content)
        
        # Verify statistics
        assert stats['total_blocks'] == 2
        assert stats['text_blocks'] == 1
        assert stats['image_blocks'] == 1
        assert stats['total_lines'] == 1
        assert stats['total_spans'] == 1
        assert stats['unique_fonts'] == 1
        assert 'Arial' in stats['font_names']
        assert stats['avg_font_size'] == 12.0
    
    def test_extract_text_content(self):
        """Test text content extraction from processed page."""
        page_content = PageContent(page_number=1)
        
        from pdf_extractor.models import ContentBlock, TextLine, TextSpan, FontInfo, BoundingBox
        
        # Create two text blocks
        span1 = TextSpan(
            text="First paragraph.",
            bbox=BoundingBox(0, 0, 100, 20),
            font_info=FontInfo(font_name="Arial", font_size=12.0)
        )
        line1 = TextLine(spans=[span1], bbox=BoundingBox(0, 0, 100, 20))
        block1 = ContentBlock(
            block_number=0, block_type=0, bbox=BoundingBox(0, 0, 100, 20), lines=[line1]
        )
        
        span2 = TextSpan(
            text="Second paragraph.",
            bbox=BoundingBox(0, 30, 100, 50),
            font_info=FontInfo(font_name="Arial", font_size=12.0)
        )
        line2 = TextLine(spans=[span2], bbox=BoundingBox(0, 30, 100, 50))
        block2 = ContentBlock(
            block_number=1, block_type=0, bbox=BoundingBox(0, 30, 100, 50), lines=[line2]
        )
        
        page_content.content_blocks = [block1, block2]
        
        processor = PageProcessor()
        text = processor.extract_text_content(page_content)
        
        assert text == "First paragraph.\n\nSecond paragraph."
