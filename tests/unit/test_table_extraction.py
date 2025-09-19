"""
Tests for table extraction functionality.

Tests the table wrappers, normalizer, and main TableExtractor class.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pandas as pd

from src.pdf_extractor.table_wrappers import PdfplumberWrapper, CamelotWrapper, TabulaWrapper
from src.pdf_extractor.table_normalizer import TableNormalizer
from src.pdf_extractor.table_extractor import TableExtractor


class TestTableNormalizer:
    """Test the TableNormalizer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.normalizer = TableNormalizer()
    
    def test_normalize_dataframe(self):
        """Test DataFrame normalization."""
        # Create test DataFrame
        df = pd.DataFrame({
            'Name': ['Alice', 'Bob', 'Charlie'],
            'Age': [25, 30, 35],
            'City': ['New York', 'London', 'Paris']
        })
        
        result = self.normalizer.normalize_table(df, "test")
        
        # Check structure
        assert len(result) == 4  # header + 3 data rows
        assert len(result[0]) == 3  # 3 columns
        
        # Check header
        assert result[0] == ['Name', 'Age', 'City']
        
        # Check data
        assert result[1] == ['Alice', '25', 'New York']
        assert result[2] == ['Bob', '30', 'London']
        assert result[3] == ['Charlie', '35', 'Paris']
    
    def test_normalize_list_of_lists(self):
        """Test list of lists normalization."""
        table = [
            ['Product', 'Price', 'Stock'],
            ['Laptop', 999.99, 50],
            ['Mouse', None, 100],
            ['Keyboard', 79.99, None]
        ]
        
        result = self.normalizer.normalize_table(table, "test")
        
        assert len(result) == 4
        assert result[0] == ['Product', 'Price', 'Stock']
        assert result[1] == ['Laptop', '999.99', '50']
        assert result[2] == ['Mouse', '', '100']
        assert result[3] == ['Keyboard', '79.99', '']
    
    def test_data_type_detection(self):
        """Test data type detection functionality."""
        # Test integer
        result = self.normalizer.detect_data_type("123")
        assert result["type"] == "integer"
        assert result["value"] == 123
        
        # Test float
        result = self.normalizer.detect_data_type("123.45")
        assert result["type"] == "float"
        assert result["value"] == 123.45
        
        # Test percentage
        result = self.normalizer.detect_data_type("45.5%")
        assert result["type"] == "percentage"
        assert result["value"] == 45.5
        
        # Test currency
        result = self.normalizer.detect_data_type("$1,234.56")
        assert result["type"] == "currency"
        assert result["value"] == 1234.56
        assert result["currency"] == "$"
        
        # Test text
        result = self.normalizer.detect_data_type("Hello World")
        assert result["type"] == "text"
        assert result["value"] == "Hello World"
    
    def test_table_structure_analysis(self):
        """Test table structure analysis."""
        # Good table
        good_table = [
            ['Name', 'Age', 'City'],
            ['Alice', '25', 'New York'],
            ['Bob', '30', 'London'],
            ['Charlie', '35', 'Paris']
        ]
        
        analysis = self.normalizer.analyze_table_structure(good_table)
        assert analysis["valid"] is True
        assert analysis["num_rows"] == 4
        assert analysis["num_cols"] == 3
        assert analysis["content_density"] > 0.8
        
        # Bad table (empty)
        bad_table = []
        analysis = self.normalizer.analyze_table_structure(bad_table)
        assert analysis["valid"] is False
        
        # Bad table (single row)
        single_row = [['Header1', 'Header2']]
        analysis = self.normalizer.analyze_table_structure(single_row)
        assert analysis["valid"] is False


class TestTableWrappers:
    """Test the table wrapper classes."""
    
    @patch('src.pdf_extractor.table_wrappers.pdfplumber.open')
    def test_pdfplumber_wrapper_basic(self, mock_open):
        """Test basic PdfplumberWrapper functionality."""
        # Mock the pdfplumber objects
        mock_table = [
            ['Header1', 'Header2'],
            ['Value1', 'Value2'],
            ['Value3', None]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [mock_table]
        
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)
        
        mock_open.return_value = mock_pdf
        
        # Test extraction
        with patch('pathlib.Path.exists', return_value=True):
            wrapper = PdfplumberWrapper("/fake/path.pdf")
            result = wrapper.extract_tables_from_page(0)
        
        assert len(result) == 1
        assert len(result[0]) == 3  # 3 rows
        assert result[0][0] == ['Header1', 'Header2']
        assert result[0][2] == ['Value3', '']  # None converted to empty string
    
    def test_table_validation(self):
        """Test table validation logic."""
        with patch('pathlib.Path.exists', return_value=True):
            wrapper = PdfplumberWrapper("/fake/path.pdf")
        
        # Valid table
        valid_table = [
            ['A', 'B', 'C'],
            ['1', '2', '3'],
            ['4', '5', '6']
        ]
        assert wrapper.validate_table(valid_table) is True
        
        # Invalid table (empty)
        assert wrapper.validate_table([]) is False
        
        # Invalid table (single row)
        assert wrapper.validate_table([['A', 'B']]) is False
        
        # Invalid table (single column)
        assert wrapper.validate_table([['A'], ['B'], ['C']]) is False
        
        # Invalid table (inconsistent columns)
        inconsistent = [
            ['A', 'B', 'C'],
            ['1'],  # Too few columns
            ['4', '5', '6']
        ]
        assert wrapper.validate_table(inconsistent) is False


@patch('src.pdf_extractor.table_extractor.fitz.open')
class TestTableExtractor:
    """Test the main TableExtractor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('pathlib.Path.exists', return_value=True):
            self.extractor = TableExtractor("/fake/path.pdf")
    
    def test_page_analysis(self, mock_fitz_open):
        """Test page structure analysis."""
        # Mock PyMuPDF document and page
        mock_page = Mock()
        mock_page.get_drawings.return_value = [
            {"items": [["l", 0, 0, 100, 0]]},  # Line drawing
            {"items": [["l", 0, 0, 0, 100]]},  # Another line
        ]
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {"spans": [{"bbox": [10, 10, 50, 20]}]},
                        {"spans": [{"bbox": [10, 30, 50, 40]}]}
                    ]
                }
            ]
        }
        
        mock_doc = Mock()
        mock_doc.__enter__ = Mock(return_value=mock_doc)
        mock_doc.__exit__ = Mock(return_value=None)
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_doc.pages = [mock_page]
        
        mock_fitz_open.return_value = mock_doc
        
        analysis = self.extractor._analyze_page_structure(0)
        
        assert analysis.page_num == 0
        assert analysis.line_count == 2
        assert analysis.recommended_strategy in ["ruled", "unruled"]
        assert 0 <= analysis.confidence <= 1
    
    @patch('src.pdf_extractor.table_extractor.TableExtractor._extract_ruled_tables')
    def test_extract_tables_from_page_success(self, mock_extract_ruled, mock_fitz_open):
        """Test successful table extraction from a page."""
        # Mock page analysis
        mock_analysis = Mock()
        mock_analysis.recommended_strategy = "ruled"
        mock_analysis.confidence = 0.8
        
        # Mock table extraction
        mock_table = [
            ['Name', 'Age'],
            ['Alice', '25'],
            ['Bob', '30']
        ]
        mock_extract_ruled.return_value = (True, [mock_table], "pdfplumber")
        
        # Mock PyMuPDF for analysis
        mock_doc = Mock()
        mock_doc.__enter__ = Mock(return_value=mock_doc)
        mock_doc.__exit__ = Mock(return_value=None)
        mock_fitz_open.return_value = mock_doc
        
        with patch.object(self.extractor, '_analyze_page_structure', return_value=mock_analysis):
            result = self.extractor.extract_tables_from_page(0)
        
        assert result.success is True
        assert len(result.tables) == 1
        assert result.method_used == "pdfplumber"
        assert len(result.quality_scores) == 1
        assert result.extraction_time > 0
    
    @patch('src.pdf_extractor.table_extractor.TableExtractor._extract_ruled_tables')
    @patch('src.pdf_extractor.table_extractor.TableExtractor._extract_unruled_tables')
    def test_extract_tables_fallback(self, mock_extract_unruled, mock_extract_ruled, mock_fitz_open):
        """Test fallback behavior when primary method fails."""
        # Mock page analysis
        mock_analysis = Mock()
        mock_analysis.recommended_strategy = "ruled"
        
        # Mock primary method failure and fallback success
        mock_extract_ruled.return_value = (False, [], "none")
        mock_table = [['A', 'B'], ['1', '2']]
        mock_extract_unruled.return_value = (True, [mock_table], "camelot-stream")
        
        # Mock PyMuPDF
        mock_doc = Mock()
        mock_doc.__enter__ = Mock(return_value=mock_doc)
        mock_doc.__exit__ = Mock(return_value=None)
        mock_fitz_open.return_value = mock_doc
        
        with patch.object(self.extractor, '_analyze_page_structure', return_value=mock_analysis):
            result = self.extractor.extract_tables_from_page(0)
        
        assert result.success is True
        assert result.method_used == "fallback-camelot-stream"
    
    def test_extraction_statistics(self, mock_fitz_open):
        """Test extraction statistics generation."""
        # Mock results
        results = [
            Mock(success=True, tables=[[], []], method_used="pdfplumber", 
                 quality_scores=[0.8, 0.9], extraction_time=1.0),
            Mock(success=False, tables=[], method_used="", 
                 quality_scores=[], extraction_time=0.5),
            Mock(success=True, tables=[[]], method_used="camelot-lattice", 
                 quality_scores=[0.7], extraction_time=2.0)
        ]
        
        stats = self.extractor.get_extraction_statistics(results)
        
        assert stats["total_pages"] == 3
        assert stats["successful_pages"] == 2
        assert stats["success_rate"] == 2/3
        assert stats["total_tables"] == 3
        assert "pdfplumber" in stats["method_usage"]
        assert "camelot-lattice" in stats["method_usage"]
        assert stats["quality_stats"]["average"] == (0.8 + 0.9 + 0.7) / 3
        assert stats["timing"]["total_time"] == 3.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])