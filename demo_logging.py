"""
Demo script to showcase the logging and error handling implementation.

This script demonstrates the structured logging system without requiring
PDF processing dependencies.
"""

import sys
from pathlib import Path
import json
import time

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pdf_extractor.logging_utils import configure_logging, get_logger, pdf_logger


def demo_structured_logging():
    """Demonstrate structured JSON logging."""
    print("\n🔍 Demonstrating Structured JSON Logging")
    print("-" * 40)
    
    # Configure JSON logging
    configure_logging(verbose=False, json_format=True)
    logger = get_logger('demo.json_logging')
    
    # Log various message types
    logger.info("Processing started", extra={
        'extra_data': {
            'file_path': '/path/to/document.pdf',
            'mode': 'standard',
            'pages': 25
        }
    })
    
    logger.warning("Non-critical issue encountered", extra={
        'extra_data': {
            'page_number': 5,
            'issue_type': 'table_extraction_failed',
            'fallback_used': True
        }
    })
    
    logger.error("Critical error occurred", extra={
        'extra_data': {
            'error_type': 'FileNotFoundError',
            'attempted_file': '/missing/file.pdf',
            'stage': 'document_loading'
        }
    })


def demo_verbose_logging():
    """Demonstrate verbose human-readable logging."""
    print("\n🔍 Demonstrating Verbose Human-Readable Logging")
    print("-" * 40)
    
    # Configure verbose logging
    configure_logging(verbose=True, json_format=False)
    logger = get_logger('demo.verbose_logging')
    
    # Log various message types
    logger.debug("Detailed debugging information")
    logger.info("Processing PDF document: example.pdf")
    logger.warning("Page 3 table extraction failed, using fallback method")
    logger.error("Failed to open PDF: File not found")


def demo_graceful_degradation():
    """Demonstrate graceful degradation logic."""
    print("\n🔍 Demonstrating Graceful Degradation Logic")
    print("-" * 40)
    
    configure_logging(verbose=True, json_format=False)
    logger = get_logger('demo.graceful_degradation')
    
    # Simulate processing multiple pages with some failures
    pages_to_process = [1, 2, 3, 4, 5]
    processed_pages = []
    errors = []
    
    for page_num in pages_to_process:
        try:
            # Simulate page processing
            logger.info(f"Processing page {page_num}")
            
            # Simulate some pages failing
            if page_num == 3:
                raise Exception("Simulated table extraction error")
            elif page_num == 5:
                raise Exception("Simulated image processing error")
            
            # Simulate successful processing
            time.sleep(0.1)
            processed_pages.append(page_num)
            logger.debug(f"Successfully processed page {page_num}")
            
        except Exception as e:
            # Log the error but continue processing
            pdf_logger.log_page_processing_error(
                pdf_path="demo.pdf",
                page_number=page_num,
                error=e
            )
            errors.append(f"Page {page_num}: {str(e)}")
            continue  # Continue with next page
    
    # Show final results
    logger.info(f"Processing completed: {len(processed_pages)}/{len(pages_to_process)} pages successful")
    if errors:
        logger.warning(f"Encountered {len(errors)} errors but continued processing")


def demo_extraction_logging():
    """Demonstrate extraction-specific logging methods."""
    print("\n🔍 Demonstrating Extraction-Specific Logging")
    print("-" * 40)
    
    configure_logging(verbose=True, json_format=False)
    
    # Simulate extraction workflow logging
    pdf_path = "example_document.pdf"
    config_info = {
        'mode': 'standard',
        'extract_tables': True,
        'extract_images': True,
        'verbose': True
    }
    
    # Log extraction start
    pdf_logger.log_extraction_start(pdf_path, config_info)
    
    # Simulate processing time
    time.sleep(0.5)
    
    # Log successful completion
    pdf_logger.log_extraction_complete(
        pdf_path=pdf_path,
        pages_processed=10,
        processing_time=2.5,
        output_path="example_document.structured.json"
    )


def demo_cli_integration():
    """Demonstrate CLI logging integration."""
    print("\n🔍 Demonstrating CLI Logging Integration")
    print("-" * 40)
    
    # Show how CLI would configure logging based on --verbose flag
    
    print("Without --verbose flag (JSON format):")
    configure_logging(verbose=False, json_format=True)
    logger = get_logger('cli.extract')
    logger.info("CLI extraction started", extra={
        'extra_data': {
            'input_path': 'document.pdf',
            'mode': 'standard',
            'format': 'hierarchical'
        }
    })
    
    print("\nWith --verbose flag (human-readable format):")
    configure_logging(verbose=True, json_format=False)
    logger = get_logger('cli.extract')
    logger.info("CLI extraction started with verbose logging enabled")
    logger.debug("Configuration details loaded successfully")


def main():
    """Run all logging demonstrations."""
    print("🚀 PDF Extractor Error Handling & Logging Demo")
    print("=" * 50)
    
    demo_structured_logging()
    demo_verbose_logging()
    demo_graceful_degradation()
    demo_extraction_logging()
    demo_cli_integration()
    
    print("\n" + "=" * 50)
    print("✅ All logging demonstrations completed!")
    print("\n📋 Implementation Summary:")
    print("  ✓ Structured JSON logging with timestamps and context")
    print("  ✓ Verbose human-readable logging option")
    print("  ✓ Graceful degradation - continue on individual failures")
    print("  ✓ CLI integration with --verbose flag support")
    print("  ✓ Extraction-specific logging methods")
    print("  ✓ Page-level error handling with continued processing")
    print("  ✓ Centralized logger configuration")
    print("  ✓ Error categorization and context preservation")


if __name__ == "__main__":
    main()