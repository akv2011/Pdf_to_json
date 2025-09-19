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
        start_time = time.time()
        
        try:
            # Basic implementation for now - will be expanded in later tasks
            pdf_doc = fitz.open(pdf_path)
            
            if pdf_doc.needs_pass and not self.config.password:
                raise PasswordRequiredError(f"PDF requires password: {pdf_path}")
            
            if self.config.password:
                if not pdf_doc.authenticate(self.config.password):
                    raise PasswordRequiredError("Invalid password provided")
            
            # Create basic extraction result
            result = ExtractionResult(
                file_path=str(pdf_path),
                pages=[],
                metadata=self._extract_metadata(pdf_doc),
                extraction_config=self.config,
                processing_time=time.time() - start_time
            )
            
            # Process each page with detailed structure analysis (Task 3)
            for page_num in range(pdf_doc.page_count):
                page = pdf_doc[page_num]
                
                # Use PageProcessor for detailed content extraction
                page_content = self.page_processor.process_page(page, page_num + 1)
                
                # For backward compatibility, also create basic text blocks
                # from the structured content
                self._create_legacy_text_blocks(page_content)
                
                result.pages.append(page_content)
            
            pdf_doc.close()
            result.processing_time = time.time() - start_time
            
            return result.to_dict()
            
        except Exception as e:
            if isinstance(e, (ExtractionError, PasswordRequiredError, UnsupportedPDFError)):
                raise
            raise ExtractionError(f"Failed to extract from {pdf_path}: {str(e)}")
    
    def get_pdf_info(self, pdf_path: Path) -> Dict[str, Any]:
        """Get basic information about a PDF file without full extraction.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing PDF information
        """
        try:
            pdf_doc = fitz.open(pdf_path)
            
            info = {
                'page_count': pdf_doc.page_count,
                'file_size_mb': pdf_path.stat().st_size / (1024 * 1024),
                'is_encrypted': bool(pdf_doc.needs_pass),
                'metadata': self._extract_metadata(pdf_doc)
            }
            
            pdf_doc.close()
            return info
            
        except Exception as e:
            raise ExtractionError(f"Failed to get info for {pdf_path}: {str(e)}")
    
    def _extract_metadata(self, pdf_doc) -> Dict[str, Any]:
        """Extract metadata from PDF document."""
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
