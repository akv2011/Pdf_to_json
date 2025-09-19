"""
Basic tests for the PDF Structure Extractor
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile

from pdf_extractor.extractor import PDFStructureExtractor
from pdf_extractor.models import ExtractionConfig, ExtractionError


class TestPDFStructureExtractor:
    """Test cases for PDFStructureExtractor class."""

    def test_extractor_initialization(self):
        """Test that the extractor initializes correctly."""
        config = ExtractionConfig(verbose=True)
        extractor = PDFStructureExtractor(config)
        
        assert extractor.config == config
        assert extractor.config.verbose is True

    def test_extractor_initialization_with_defaults(self):
        """Test that the extractor initializes with default config."""
        extractor = PDFStructureExtractor()
        
        assert extractor.config is not None
        assert isinstance(extractor.config, ExtractionConfig)
        assert extractor.config.extract_tables is True

    @patch('pdf_extractor.extractor.fitz')
    def test_extract_basic_pdf(self, mock_fitz):
        """Test basic PDF extraction functionality."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.needs_pass = False
        mock_doc.page_count = 2
        mock_doc.metadata = {
            'title': 'Test Document',
            'author': 'Test Author',
            'creator': 'Test Creator'
        }
        
        mock_page1 = Mock()
        mock_page1.get_text.return_value = "Test content page 1"
        mock_page1.rect.width = 595.0
        mock_page1.rect.height = 842.0
        mock_page1.rotation = 0
        
        mock_page2 = Mock()
        mock_page2.get_text.return_value = "Test content page 2"
        mock_page2.rect.width = 595.0
        mock_page2.rect.height = 842.0
        mock_page2.rotation = 0
        
        mock_doc.__getitem__.side_effect = [mock_page1, mock_page2]
        mock_fitz.open.return_value = mock_doc
        
        # Test extraction
        extractor = PDFStructureExtractor()
        result = extractor.extract(Path("test.pdf"))
        
        # Verify results
        assert result['file_path'] == "test.pdf"
        assert result['page_count'] == 2
        assert len(result['pages']) == 2
        assert result['pages'][0]['page_number'] == 1
        assert result['pages'][1]['page_number'] == 2
        assert 'Test content page 1' in result['pages'][0]['text_blocks'][0]['text']
        assert 'Test content page 2' in result['pages'][1]['text_blocks'][0]['text']

    @patch('pdf_extractor.extractor.fitz')
    def test_get_pdf_info(self, mock_fitz):
        """Test PDF info extraction."""
        # Setup mock
        mock_doc = Mock()
        mock_doc.needs_pass = False
        mock_doc.page_count = 5
        mock_doc.metadata = {
            'title': 'Test Document',
            'author': 'Test Author'
        }
        mock_fitz.open.return_value = mock_doc
        
        # Create a temporary file for size calculation
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test content")
            tmp_path = Path(tmp_file.name)
        
        try:
            extractor = PDFStructureExtractor()
            info = extractor.get_pdf_info(tmp_path)
            
            assert info['page_count'] == 5
            assert info['is_encrypted'] is False
            assert 'file_size_mb' in info
            assert info['metadata']['title'] == 'Test Document'
            assert info['metadata']['author'] == 'Test Author'
        finally:
            tmp_path.unlink()  # Clean up

    def test_extract_with_nonexistent_file(self):
        """Test extraction with non-existent file."""
        extractor = PDFStructureExtractor()
        
        with pytest.raises(ExtractionError):
            extractor.extract(Path("nonexistent.pdf"))

    @patch('pdf_extractor.extractor.fitz')
    def test_extract_password_protected_pdf(self, mock_fitz):
        """Test extraction with password-protected PDF."""
        # Setup mock for password-protected PDF
        mock_doc = Mock()
        mock_doc.needs_pass = True
        mock_fitz.open.return_value = mock_doc
        
        extractor = PDFStructureExtractor()
        
        # Should raise PasswordRequiredError
        with pytest.raises(Exception) as exc_info:
            extractor.extract(Path("protected.pdf"))
        
        assert "password" in str(exc_info.value).lower()


class TestExtractionConfig:
    """Test cases for ExtractionConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ExtractionConfig()
        
        assert config.preserve_layout is False
        assert config.extract_tables is True
        assert config.extract_images is False
        assert config.verbose is False
        assert config.min_table_rows == 2
        assert config.min_table_cols == 2
        assert config.text_extraction_method == "pymupdf"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ExtractionConfig(
            preserve_layout=True,
            extract_images=True,
            verbose=True,
            min_table_rows=3
        )
        
        assert config.preserve_layout is True
        assert config.extract_images is True
        assert config.verbose is True
        assert config.min_table_rows == 3
