"""
Main PDF Structure Extractor class
"""

import time
from pathlib import Path
from typing import Dict, Any
import fitz  # PyMuPDF

from .models import (
    ExtractionConfig, ExtractionResult, PageContent, 
    ExtractionError, PasswordRequiredError, UnsupportedPDFError
)
from .page_processor import PageProcessor
from .logging_utils import get_logger, pdf_logger


class PDFStructureExtractor:
    """Main class for extracting structured content from PDF files."""
    
    def __init__(self, config: ExtractionConfig = None):
        """Initialize the extractor with configuration."""
        self.config = config or ExtractionConfig()
        self.page_processor = PageProcessor(
            debug=self.config.verbose,
            extract_images=self.config.extract_images
        )
    
    def extract(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract structured content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted content
            
        Raises:
            ExtractionError: If extraction fails
            PasswordRequiredError: If PDF requires password
            UnsupportedPDFError: If PDF format is not supported
        """
        logger = get_logger('pdf_extractor.extractor')
        start_time = time.time()
        
        # Log extraction start with configuration
        pdf_logger.log_extraction_start(
            pdf_path=str(pdf_path),
            config_info={
                'verbose': self.config.verbose,
                'extract_tables': self.config.extract_tables,
                'extract_images': self.config.extract_images,
                'preserve_layout': self.config.preserve_layout
            }
        )
        
        pdf_doc = None
        result = None
        
        try:
            # Try to open the PDF document
            try:
                pdf_doc = fitz.open(pdf_path)
                logger.debug(f"Successfully opened PDF: {pdf_path}")
            except fitz.FileNotFoundError:
                raise ExtractionError(f"PDF file not found: {pdf_path}")
            except fitz.PyMuPDFError as e:
                if "not supported" in str(e).lower():
                    raise UnsupportedPDFError(f"Unsupported PDF format: {pdf_path}")
                raise ExtractionError(f"PyMuPDF error opening {pdf_path}: {str(e)}")
            except Exception as e:
                raise ExtractionError(f"Unexpected error opening {pdf_path}: {str(e)}")
            
            # Handle password-protected PDFs
            if pdf_doc.needs_pass:
                if not self.config.password:
                    raise PasswordRequiredError(f"PDF requires password: {pdf_path}")
                
                try:
                    if not pdf_doc.authenticate(self.config.password):
                        raise PasswordRequiredError("Invalid password provided")
                    logger.debug("Successfully authenticated password-protected PDF")
                except Exception as e:
                    raise PasswordRequiredError(f"Authentication failed: {str(e)}")
            
            # Extract metadata safely
            try:
                metadata = self._extract_metadata(pdf_doc)
                logger.debug(f"Extracted metadata for {pdf_doc.page_count} page PDF")
            except Exception as e:
                logger.warning(f"Failed to extract metadata: {str(e)}")
                metadata = {}
            
            # Create basic extraction result
            result = ExtractionResult(
                file_path=str(pdf_path),
                pages=[],
                metadata=metadata,
                extraction_config=self.config,
                processing_time=0  # Will be updated at the end
            )
            
            # Process each page with error handling for individual pages
            pages_processed = 0
            for page_num in range(pdf_doc.page_count):
                try:
                    page = pdf_doc[page_num]
                    
                    # Use PageProcessor for detailed content extraction
                    page_content = self.page_processor.process_page(page, page_num + 1)
                    
                    # For backward compatibility, also create basic text blocks
                    # from the structured content
                    self._create_legacy_text_blocks(page_content)
                    
                    result.pages.append(page_content)
                    pages_processed += 1
                    
                    logger.debug(f"Successfully processed page {page_num + 1}/{pdf_doc.page_count}")
                    
                except Exception as e:
                    # Log page-specific error but continue processing
                    pdf_logger.log_page_processing_error(
                        pdf_path=str(pdf_path),
                        page_number=page_num + 1,
                        error=e
                    )
                    
                    # Add error to results but continue with next page
                    if not hasattr(result, 'errors'):
                        result.errors = []
                    result.errors.append(f"Page {page_num + 1}: {str(e)}")
                    continue
            
            # Calculate processing time
            processing_time = time.time() - start_time
            result.processing_time = processing_time
            
            # Log successful completion
            pdf_logger.log_extraction_complete(
                pdf_path=str(pdf_path),
                pages_processed=pages_processed,
                processing_time=processing_time
            )
            
            return result.to_dict()
            
        except (ExtractionError, PasswordRequiredError, UnsupportedPDFError) as e:
            # Log known extraction errors
            pdf_logger.log_extraction_error(
                pdf_path=str(pdf_path),
                error=e,
                stage="document_processing"
            )
            raise
            
        except Exception as e:
            # Log unexpected errors
            pdf_logger.log_extraction_error(
                pdf_path=str(pdf_path),
                error=e,
                stage="unexpected"
            )
            raise ExtractionError(f"Failed to extract from {pdf_path}: {str(e)}")
            
        finally:
            # Ensure PDF document is always closed
            if pdf_doc is not None:
                try:
                    pdf_doc.close()
                    logger.debug("PDF document closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing PDF document: {str(e)}")
    
    def get_pdf_info(self, pdf_path: Path) -> Dict[str, Any]:
        """Get basic information about a PDF file without full extraction.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing PDF information
        """
        logger = get_logger('pdf_extractor.extractor')
        pdf_doc = None
        
        try:
            # Try to open the PDF document
            try:
                pdf_doc = fitz.open(pdf_path)
                logger.debug(f"Successfully opened PDF for info: {pdf_path}")
            except fitz.FileNotFoundError:
                raise ExtractionError(f"PDF file not found: {pdf_path}")
            except fitz.PyMuPDFError as e:
                if "not supported" in str(e).lower():
                    raise UnsupportedPDFError(f"Unsupported PDF format: {pdf_path}")
                raise ExtractionError(f"PyMuPDF error opening {pdf_path}: {str(e)}")
            except Exception as e:
                raise ExtractionError(f"Unexpected error opening {pdf_path}: {str(e)}")
            
            # Extract basic information safely
            try:
                file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
            except Exception as e:
                logger.warning(f"Could not get file size: {str(e)}")
                file_size_mb = 0
            
            try:
                metadata = self._extract_metadata(pdf_doc)
            except Exception as e:
                logger.warning(f"Could not extract metadata: {str(e)}")
                metadata = {}
            
            info = {
                'page_count': pdf_doc.page_count,
                'file_size_mb': file_size_mb,
                'is_encrypted': bool(pdf_doc.needs_pass),
                'metadata': metadata
            }
            
            logger.info(f"Successfully extracted PDF info: {pdf_doc.page_count} pages, {file_size_mb:.2f}MB")
            return info
            
        except (ExtractionError, UnsupportedPDFError) as e:
            logger.error(f"Failed to get PDF info: {str(e)}")
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error getting PDF info: {str(e)}")
            raise ExtractionError(f"Failed to get info for {pdf_path}: {str(e)}")
            
        finally:
            # Ensure PDF document is always closed
            if pdf_doc is not None:
                try:
                    pdf_doc.close()
                    logger.debug("PDF document closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing PDF document: {str(e)}")
    
    def _extract_metadata(self, pdf_doc) -> Dict[str, Any]:
        """Extract metadata from PDF document with error handling."""
        logger = get_logger('pdf_extractor.extractor')
        
        try:
            metadata = pdf_doc.metadata
            return {
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'subject': metadata.get('subject', ''),
                'creator': metadata.get('creator', ''),
                'producer': metadata.get('producer', ''),
                'creation_date': metadata.get('creationDate', ''),
                'modification_date': metadata.get('modDate', ''),
                'keywords': metadata.get('keywords', ''),
                'format': metadata.get('format', ''),
                'encrypted': metadata.get('encryption', None) is not None
            }
        except Exception as e:
            logger.warning(f"Error extracting metadata: {str(e)}")
            # Return basic structure even if metadata extraction fails
            return {
                'title': '',
                'author': '',
                'subject': '',
                'creator': '',
                'producer': '',
                'creation_date': '',
                'modification_date': '',
                'keywords': '',
                'format': '',
                'encrypted': False
            }
    
    def _create_legacy_text_blocks(self, page_content: PageContent):
        """Create legacy TextBlock objects for backward compatibility.
        
        Args:
            page_content: PageContent with detailed content blocks
        """
        from .models import TextBlock, ContentType
        
        # Convert structured content blocks to simple text blocks
        for content_block in page_content.content_blocks:
            if content_block.is_text_block and content_block.text.strip():
                text_block = TextBlock(
                    text=content_block.text.strip(),
                    content_type=ContentType.TEXT,
                    bbox=content_block.bbox,
                    confidence=1.0
                )
                page_content.text_blocks.append(text_block)
