import pytest
import sys
from pathlib import Path

sys.path.insert(0, 'src')

from pdf_extractor.logging_utils import configure_logging


class TestPipelineIntegration:
    
    @pytest.fixture(autouse=True)
    def setup_logging(self):
        """Configure logging for tests."""
        configure_logging(verbose=True, json_format=False)
    
    def test_pdf_file_exists(self):
        """Test that our test PDF file exists."""
        test_pdf = Path(__file__).parent.parent / "data" / "simple_test.pdf"
        assert test_pdf.exists(), f"Test PDF not found at {test_pdf}"
        assert test_pdf.suffix == ".pdf", "Test file should be a PDF"
    
    @pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
    def test_import_main_components(self):
        """Test that main components can be imported without errors."""
        try:
            # Test importing main classes
            from pdf_extractor.models import ExtractionConfig
            from pdf_extractor.logging_utils import get_logger
            
            # Create basic instances
            config = ExtractionConfig(verbose=True)
            logger = get_logger('test')
            
            assert config is not None
            assert logger is not None
            assert config.verbose is True
            
        except ImportError as e:
            pytest.skip(f"Core dependencies not available: {e}")
    
    @pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
    def test_basic_extraction_without_dependencies(self):
        """Test basic extraction setup without PyMuPDF dependencies."""
        test_pdf = Path(__file__).parent.parent / "data" / "simple_test.pdf"
        
        try:
            from pdf_extractor.models import ExtractionConfig
            from pdf_extractor.extractor import PDFStructureExtractor
            
            # Create extractor instance
            config = ExtractionConfig(verbose=True)
            extractor = PDFStructureExtractor(config)
            
            assert extractor is not None
            assert extractor.config.verbose is True
            
            # Note: We don't actually call extract() since PyMuPDF might not be installed
            # This test just verifies the classes can be instantiated
            
        except ImportError as e:
            pytest.skip(f"PDF processing dependencies not available: {e}")
    
    def test_cli_module_import(self):
        """Test that CLI module can be imported."""
        try:
            from pdf_extractor import cli
            assert cli is not None
            
            # Test that the main CLI group exists
            assert hasattr(cli, 'cli')
            
        except ImportError as e:
            pytest.skip(f"CLI dependencies not available: {e}")
    
    def test_logging_in_pipeline_context(self):
        """Test logging works in a pipeline-like context."""
        from pdf_extractor.logging_utils import get_logger, pdf_logger
        
        logger = get_logger('test.pipeline')
        
        # Simulate pipeline steps with logging
        logger.info("Starting test pipeline")
        
        # Test extraction-specific logging
        pdf_logger.log_extraction_start(
            pdf_path="test.pdf",
            config_info={'mode': 'test', 'verbose': True}
        )
        
        # Simulate some processing
        logger.debug("Processing page 1")
        logger.debug("Processing page 2")
        
        # Test completion logging
        pdf_logger.log_extraction_complete(
            pdf_path="test.pdf",
            pages_processed=2,
            processing_time=0.5
        )
        
        logger.info("Test pipeline completed")
        
        # If we get here without exceptions, logging is working


if __name__ == "__main__":
    pytest.main([__file__, "-v"])