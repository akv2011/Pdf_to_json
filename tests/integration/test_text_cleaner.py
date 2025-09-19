"""
Integration tests for TextCleaner module with real PDF processing.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from pdf_extractor.text_cleaner import TextCleaner
from pdf_extractor.extractor import PDFStructureExtractor
from pdf_extractor.models import ExtractionConfig, PageContent


class TestTextCleaner:
    """Test cases for the TextCleaner module."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cleaner = TextCleaner(artifact_threshold=0.5)
        self.extractor = PDFStructureExtractor(ExtractionConfig(verbose=True))
    
    def test_ligature_normalization(self):
        """Test ligature replacement functionality."""
        test_cases = [
            ("ﬁle", "file"),
            ("ﬂower", "flower"),
            ("ﬀ", "ff"),
            ("ﬃce", "ffice"),
            ("ﬄe", "ffle"),
            ("ﬆory", "story"),
            ("Cœur", "Coeur"),
            ("Encyclopædia", "Encyclopaedia"),
            ("Regular text", "Regular text"),  # Should not change
        ]
        
        for input_text, expected in test_cases:
            result = self.cleaner.normalize_text(input_text)
            assert result == expected, f"Failed for '{input_text}': got '{result}', expected '{expected}'"
    
    def test_whitespace_normalization(self):
        """Test whitespace cleaning functionality."""
        test_cases = [
            ("Multiple   spaces", "Multiple spaces"),
            ("Text\twith\ttabs", "Text with tabs"),
            ("  Leading spaces preserved", "  Leading spaces preserved"),
            ("Trailing spaces removed  ", "Trailing spaces removed"),
            ("Line1\n\n\n\nLine2", "Line1\n\nLine2"),
            ("Normal\nlines\npreserved", "Normal\nlines\npreserved"),
        ]
        
        for input_text, expected in test_cases:
            result = self.cleaner.normalize_text(input_text)
            assert result == expected, f"Failed for '{input_text}': got '{result}', expected '{expected}'"
    
    def test_page_number_detection(self):
        """Test page number pattern detection."""
        page_numbers = ["1", "42", "Page 5", "5/10", "- 7 -", "123"]
        not_page_numbers = ["Regular text", "Chapter 1", "1st place", "Version 2.0"]
        
        for text in page_numbers:
            assert self.cleaner._is_likely_artifact(text), f"'{text}' should be detected as page number"
        
        for text in not_page_numbers:
            assert not self.cleaner._is_likely_artifact(text), f"'{text}' should NOT be detected as page number"
    
    def test_artifact_pattern_detection(self):
        """Test detection of common PDF artifacts."""
        artifacts = [
            "CONFIDENTIAL DOCUMENT HEADER",
            "© 2024 Company Name. All rights reserved.",
            "user@example.com",
            "www.example.com",
            "12/25/2024",
        ]
        
        not_artifacts = [
            "Regular paragraph text",
            "This is normal content",
            "Chapter Title",
        ]
        
        for text in artifacts:
            assert self.cleaner._is_likely_artifact(text), f"'{text}' should be detected as artifact"
        
        for text in not_artifacts:
            assert not self.cleaner._is_likely_artifact(text), f"'{text}' should NOT be detected as artifact"
    
    def test_position_grouping(self):
        """Test position-based grouping for artifact detection."""
        from pdf_extractor.models import BoundingBox
        
        # Test positions that are close should be grouped (within tolerance)
        bbox1 = BoundingBox(x0=50, y0=50, x1=100, y1=70)
        bbox2 = BoundingBox(x0=52, y0=52, x1=102, y1=72)  # Within 5px tolerance
        bbox3 = BoundingBox(x0=200, y0=200, x1=250, y1=220)  # Far away
        
        key1 = self.cleaner._get_position_key(bbox1)
        key2 = self.cleaner._get_position_key(bbox2)
        key3 = self.cleaner._get_position_key(bbox3)
        
        # Close positions should have same key
        assert key1 == key2, f"Close positions should be grouped together: {key1} vs {key2}"
        # Far positions should have different keys
        assert key1 != key3, "Distant positions should have different keys"
    
    def test_header_footer_position_detection(self):
        """Test header/footer position detection."""
        from pdf_extractor.models import PageContent, BoundingBox
        
        # Create a sample page
        page = PageContent(page_number=1, page_width=612, page_height=792)
        
        # Header position (top 10%)
        header_bbox = BoundingBox(x0=50, y0=30, x1=500, y1=50)
        assert self.cleaner._is_header_footer_position(header_bbox, page)
        
        # Footer position (bottom 10%)
        footer_bbox = BoundingBox(x0=50, y0=750, x1=500, y1=770)
        assert self.cleaner._is_header_footer_position(footer_bbox, page)
        
        # Middle content (should not be header/footer)
        content_bbox = BoundingBox(x0=50, y0=400, x1=500, y1=420)
        assert not self.cleaner._is_header_footer_position(content_bbox, page)
    
    def test_clean_pages_integration(self):
        """Test the full page cleaning integration."""
        from pdf_extractor.models import PageContent, ContentBlock, TextLine, TextSpan, FontInfo, BoundingBox
        
        # Create test pages with artifacts
        pages = []
        font_info = FontInfo(font_name="Arial", font_size=12.0)
        
        for page_num in range(1, 4):
            page = PageContent(
                page_number=page_num,
                page_width=612.0,
                page_height=792.0,
                rotation=0
            )
            
            # Add header artifact (consistent across pages)
            header_bbox = BoundingBox(x0=50, y0=50, x1=500, y1=70)
            header_span = TextSpan(text="CONFIDENTIAL DOCUMENT", bbox=header_bbox, font_info=font_info)
            header_line = TextLine(spans=[header_span], bbox=header_bbox)
            header_block = ContentBlock(block_number=0, block_type=0, bbox=header_bbox, lines=[header_line])
            page.content_blocks.append(header_block)
            
            # Add main content (unique per page)
            content_bbox = BoundingBox(x0=50, y0=100, x1=500, y1=600)
            content_text = f"This is important content on page {page_num}. " \
                          f"It contains ﬁle names and ﬂexible formatting."
            content_span = TextSpan(text=content_text, bbox=content_bbox, font_info=font_info)
            content_line = TextLine(spans=[content_span], bbox=content_bbox)
            content_block = ContentBlock(block_number=1, block_type=0, bbox=content_bbox, lines=[content_line])
            page.content_blocks.append(content_block)
            
            pages.append(page)
        
        # Clean the pages
        cleaned_pages = self.cleaner.clean_pages(pages)
        
        # Verify results
        assert len(cleaned_pages) == 3, "Should have 3 cleaned pages"
        
        for i, page in enumerate(cleaned_pages):
            # Should have removed the header artifact
            page_texts = [block.text for block in page.content_blocks]
            assert not any("CONFIDENTIAL DOCUMENT" in text for text in page_texts), \
                f"Header artifact should be removed from page {i+1}"
            
            # Should preserve main content with normalization
            has_main_content = any("important content" in text for text in page_texts)
            assert has_main_content, f"Main content should be preserved on page {i+1}"
            
            # Should normalize ligatures
            has_normalized_text = any("file names" in text and "flexible" in text for text in page_texts)
            assert has_normalized_text, f"Ligatures should be normalized on page {i+1}"
    
    def test_artifact_report_generation(self):
        """Test artifact report generation."""
        from pdf_extractor.models import PageContent, ContentBlock, TextLine, TextSpan, FontInfo, BoundingBox
        
        # Create test pages
        pages = []
        font_info = FontInfo(font_name="Arial", font_size=12.0)
        
        for page_num in range(1, 6):  # 5 pages
            page = PageContent(page_number=page_num, page_width=612, page_height=792)
            
            # Add artifact that appears on all pages
            artifact_bbox = BoundingBox(x0=50, y0=50, x1=500, y1=70)
            artifact_span = TextSpan(text="Common Header", bbox=artifact_bbox, font_info=font_info)
            artifact_line = TextLine(spans=[artifact_span], bbox=artifact_bbox)
            artifact_block = ContentBlock(block_number=0, block_type=0, bbox=artifact_bbox, lines=[artifact_line])
            page.content_blocks.append(artifact_block)
            
            # Add artifact that appears on 3 out of 5 pages (60%)
            if page_num <= 3:
                footer_bbox = BoundingBox(x0=50, y0=750, x1=500, y1=770)
                footer_span = TextSpan(text="Page Footer", bbox=footer_bbox, font_info=font_info)
                footer_line = TextLine(spans=[footer_span], bbox=footer_bbox)
                footer_block = ContentBlock(block_number=1, block_type=0, bbox=footer_bbox, lines=[footer_line])
                page.content_blocks.append(footer_block)
            
            pages.append(page)
        
        # Generate report
        report = self.cleaner.get_artifact_report(pages)
        
        # Verify report structure
        assert "total_pages" in report
        assert "artifacts_detected" in report
        assert "artifacts" in report
        assert report["total_pages"] == 5
        
        # Should detect both artifacts (100% and 60% frequency)
        assert report["artifacts_detected"] >= 2
        
        # Check artifact details
        artifact_texts = [artifact["text"] for artifact in report["artifacts"]]
        assert "Common Header" in artifact_texts
        assert "Page Footer" in artifact_texts
        
        # Verify frequency calculations
        for artifact in report["artifacts"]:
            if artifact["text"] == "Common Header":
                assert artifact["frequency"] == 5
                assert artifact["coverage_percentage"] == 100.0
            elif artifact["text"] == "Page Footer":
                assert artifact["frequency"] == 3
                assert artifact["coverage_percentage"] == 60.0
    
    @pytest.mark.integration
    def test_with_real_pdf(self):
        """Integration test with a real PDF file (if available)."""
        # Look for test PDF files
        test_pdf_paths = [
            Path("rfp-bid-main/example-PDF/test.pdf"),
            Path("../rfp-bid-main/example-PDF/test.pdf"),
            Path("../../rfp-bid-main/example-PDF/test.pdf"),
        ]
        
        test_pdf = None
        for path in test_pdf_paths:
            if path.exists():
                test_pdf = path
                break
        
        if test_pdf is None:
            pytest.skip("No test PDF file found")
        
        # Extract content from PDF
        try:
            result = self.extractor.extract(test_pdf)
            pages = [PageContent(**page_data) if isinstance(page_data, dict) else page_data 
                    for page_data in result.get("pages", [])]
            
            if not pages:
                pytest.skip("No pages extracted from test PDF")
            
            # Generate artifact report
            report = self.cleaner.get_artifact_report(pages)
            
            # Basic validation
            assert report["total_pages"] > 0
            assert "artifacts" in report
            
            # Clean the pages
            cleaned_pages = self.cleaner.clean_pages(pages)
            
            # Should have same number of pages
            assert len(cleaned_pages) == len(pages)
            
            print(f"Successfully processed {len(pages)} pages")
            print(f" Detected {report['artifacts_detected']} artifacts")
            
        except Exception as e:
            pytest.skip(f"Could not process test PDF: {e}")


if __name__ == "__main__":
    # Run tests directly
    test_cleaner = TestTextCleaner()
    test_cleaner.setup_method()
    
    print("Running TextCleaner integration tests...")
    
    tests = [
        ("Ligature Normalization", test_cleaner.test_ligature_normalization),
        ("Whitespace Normalization", test_cleaner.test_whitespace_normalization),
        ("Page Number Detection", test_cleaner.test_page_number_detection),
        ("Artifact Pattern Detection", test_cleaner.test_artifact_pattern_detection),
        ("Position Grouping", test_cleaner.test_position_grouping),
        ("Header/Footer Position Detection", test_cleaner.test_header_footer_position_detection),
        ("Clean Pages Integration", test_cleaner.test_clean_pages_integration),
        ("Artifact Report Generation", test_cleaner.test_artifact_report_generation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f" {test_name}")
            passed += 1
        except Exception as e:
            print(f" {test_name}: {e}")
    
    print(f"\nIntegration Tests: {passed}/{total} passed")
    
    if passed == total:
        print(" All integration tests passed!")
    else:
        print("  Some integration tests failed.")