"""
Integration tests for PDF Structure Extractor
"""

import pytest
import json
from pathlib import Path

from pdf_extractor.extractor import PDFStructureExtractor
from pdf_extractor.models import ExtractionConfig


@pytest.fixture
def sample_pdf_path():
    """Return path to the sample PDF file in the project."""
    return Path("/home/arun/Desktop/Hack/Pdf_to_json/[Fund Factsheet - May]360ONE-MF-May 2025.pdf.pdf")


class TestRealPDFExtraction:
    """Integration tests with real PDF files."""

    def test_extract_real_pdf_basic(self, sample_pdf_path):
        """Test extraction with a real PDF file."""
        if not sample_pdf_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_pdf_path}")
        
        config = ExtractionConfig(verbose=False)
        extractor = PDFStructureExtractor(config)
        
        # Extract content
        result = extractor.extract(sample_pdf_path)
        
        # Basic validations
        assert isinstance(result, dict)
        assert 'file_path' in result
        assert 'pages' in result
        assert 'metadata' in result
        assert 'processing_time' in result
        
        # Check that we have pages
        assert len(result['pages']) > 0
        
        # Check page structure
        first_page = result['pages'][0]
        assert 'page_number' in first_page
        assert 'text_blocks' in first_page
        assert 'tables' in first_page
        assert 'images' in first_page
        
        # Check metadata
        metadata = result['metadata']
        assert isinstance(metadata, dict)
        assert 'creator' in metadata
        
        print(f"✅ Successfully extracted {len(result['pages'])} pages")
        print(f"📄 Processing time: {result['processing_time']:.3f} seconds")

    def test_get_pdf_info_real(self, sample_pdf_path):
        """Test PDF info extraction with real file."""
        if not sample_pdf_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_pdf_path}")
        
        extractor = PDFStructureExtractor()
        info = extractor.get_pdf_info(sample_pdf_path)
        
        # Validate info structure
        assert 'page_count' in info
        assert 'file_size_mb' in info
        assert 'is_encrypted' in info
        assert 'metadata' in info
        
        # Check that values make sense
        assert info['page_count'] > 0
        assert info['file_size_mb'] > 0
        assert isinstance(info['is_encrypted'], bool)
        
        print(f"📋 PDF Info: {info['page_count']} pages, {info['file_size_mb']:.2f} MB")

    def test_extract_to_json_file(self, sample_pdf_path, tmp_path):
        """Test extraction and saving to JSON file."""
        if not sample_pdf_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_pdf_path}")
        
        config = ExtractionConfig(verbose=False)
        extractor = PDFStructureExtractor(config)
        
        # Extract content
        result = extractor.extract(sample_pdf_path)
        
        # Save to temporary JSON file
        output_file = tmp_path / "test_output.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Verify file was created and has content
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        
        # Verify we can read it back
        with open(output_file, 'r', encoding='utf-8') as f:
            loaded_result = json.load(f)
        
        assert loaded_result == result
        print(f"💾 Successfully saved to JSON: {output_file.stat().st_size} bytes")
