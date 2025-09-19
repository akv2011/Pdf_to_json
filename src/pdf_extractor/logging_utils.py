"""
Structured logging utility for PDF extractor.

This module provides centralized logging configuration with structured output
and support for different log levels based on verbosity settings.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
            
        return json.dumps(log_entry)


class PDFExtractorLogger:
    """Centralized logger configuration for PDF extractor."""
    
    _instance = None
    _configured = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def configure_logging(self, verbose: bool = False, json_format: bool = True):
        """Configure the root logger with appropriate settings.
        
        Args:
            verbose: If True, set log level to DEBUG, otherwise INFO
            json_format: If True, use JSON formatting, otherwise use standard format
        """
        if self._configured:
            return
            
        # Determine log level
        log_level = logging.DEBUG if verbose else logging.INFO
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Remove existing handlers to avoid duplication
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        # Set formatter based on json_format preference
        if json_format:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        self._configured = True
        
        # Log initial configuration
        logger = logging.getLogger(__name__)
        logger.info("Logging configured", extra={
            'extra_data': {
                'verbose': verbose,
                'json_format': json_format,
                'log_level': logging.getLevelName(log_level)
            }
        })
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for a specific module.
        
        Args:
            name: Name of the module/logger
            
        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)
    
    def log_extraction_start(self, pdf_path: str, config_info: Dict[str, Any]):
        """Log the start of PDF extraction process.
        
        Args:
            pdf_path: Path to the PDF file being processed
            config_info: Configuration information
        """
        logger = self.get_logger('pdf_extractor.extraction')
        logger.info("Starting PDF extraction", extra={
            'extra_data': {
                'pdf_path': pdf_path,
                'config': config_info
            }
        })
    
    def log_extraction_complete(self, pdf_path: str, pages_processed: int, 
                              processing_time: float, output_path: str = None):
        """Log successful completion of PDF extraction.
        
        Args:
            pdf_path: Path to the PDF file that was processed
            pages_processed: Number of pages processed
            processing_time: Time taken for processing in seconds
            output_path: Path where output was saved
        """
        logger = self.get_logger('pdf_extractor.extraction')
        logger.info("PDF extraction completed successfully", extra={
            'extra_data': {
                'pdf_path': pdf_path,
                'pages_processed': pages_processed,
                'processing_time_seconds': round(processing_time, 2),
                'output_path': output_path
            }
        })
    
    def log_extraction_error(self, pdf_path: str, error: Exception, 
                           stage: str = "unknown"):
        """Log extraction errors with context.
        
        Args:
            pdf_path: Path to the PDF file being processed
            error: The exception that occurred
            stage: Stage of processing where error occurred
        """
        logger = self.get_logger('pdf_extractor.extraction')
        logger.error("PDF extraction failed", extra={
            'extra_data': {
                'pdf_path': pdf_path,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'stage': stage
            }
        }, exc_info=True)
    
    def log_page_processing_error(self, pdf_path: str, page_number: int, 
                                error: Exception):
        """Log page-specific processing errors.
        
        Args:
            pdf_path: Path to the PDF file being processed
            page_number: Page number where error occurred
            error: The exception that occurred
        """
        logger = self.get_logger('pdf_extractor.page_processor')
        logger.warning("Page processing failed, continuing with next page", extra={
            'extra_data': {
                'pdf_path': pdf_path,
                'page_number': page_number,
                'error_type': type(error).__name__,
                'error_message': str(error)
            }
        })
    
    def log_table_extraction_error(self, pdf_path: str, page_number: int, 
                                 error: Exception):
        """Log table extraction errors.
        
        Args:
            pdf_path: Path to the PDF file being processed
            page_number: Page number where table extraction failed
            error: The exception that occurred
        """
        logger = self.get_logger('pdf_extractor.table_extractor')
        logger.warning("Table extraction failed for page, continuing", extra={
            'extra_data': {
                'pdf_path': pdf_path,
                'page_number': page_number,
                'error_type': type(error).__name__,
                'error_message': str(error)
            }
        })


# Global logger instance
pdf_logger = PDFExtractorLogger()


def configure_logging(verbose: bool = False, json_format: bool = True):
    """Convenience function to configure logging.
    
    Args:
        verbose: If True, enable DEBUG level logging
        json_format: If True, use JSON format for structured logs
    """
    pdf_logger.configure_logging(verbose=verbose, json_format=json_format)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.
    
    Args:
        name: Module name for the logger
        
    Returns:
        Configured logger instance
    """
    return pdf_logger.get_logger(name)