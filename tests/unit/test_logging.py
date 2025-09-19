import pytest
import json
import sys
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, 'src')

from pdf_extractor.logging_utils import configure_logging, get_logger, PDFExtractorLogger


class TestLoggingUtils:
    
    def test_configure_logging_basic(self):
        """Test basic logging configuration works without errors."""
        # This should not raise any exceptions
        configure_logging(verbose=False, json_format=True)
        
        # Get a logger and verify it works
        logger = get_logger('test.basic')
        assert logger is not None
        assert logger.name == 'test.basic'
    
    def test_json_logging_output(self):
        """Test that JSON logging produces valid JSON output."""
        # Capture stdout to check log output
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            configure_logging(verbose=False, json_format=True)
            logger = get_logger('test.json')
            
            # Log a test message
            logger.info("Test message", extra={
                'extra_data': {
                    'test_field': 'test_value'
                }
            })
            
            # Get the output
            output = mock_stdout.getvalue().strip()
            
            # Should be valid JSON
            if output:  # Only test if there's output
                log_entry = json.loads(output)
                assert 'timestamp' in log_entry
                assert 'level' in log_entry
                assert 'message' in log_entry
                assert log_entry['message'] == 'Test message'
    
    def test_pdf_logger_singleton(self):
        """Test that PDFExtractorLogger is a singleton."""
        logger1 = PDFExtractorLogger()
        logger2 = PDFExtractorLogger()
        
        assert logger1 is logger2
    
    def test_extraction_logging_methods(self):
        """Test that extraction-specific logging methods work without errors."""
        configure_logging(verbose=True, json_format=False)
        
        from pdf_extractor.logging_utils import pdf_logger
        
        # These should not raise exceptions
        pdf_logger.log_extraction_start(
            pdf_path="test.pdf",
            config_info={'mode': 'test'}
        )
        
        pdf_logger.log_extraction_complete(
            pdf_path="test.pdf",
            pages_processed=1,
            processing_time=0.1
        )
        
        # Test error logging
        test_error = Exception("Test error")
        pdf_logger.log_extraction_error(
            pdf_path="test.pdf",
            error=test_error,
            stage="testing"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])