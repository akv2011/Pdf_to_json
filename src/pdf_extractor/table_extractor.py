"""
Multi-library table extraction with intelligent cascading strategy.

This module implements the main TableExtractor class that coordinates
pdfplumber, camelot-py, and tabula-py libraries to extract tables from PDFs
with maximum accuracy and reliability.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

import fitz  # PyMuPDF for page analysis

from .table_wrappers import PdfplumberWrapper, CamelotWrapper, TabulaWrapper
from .table_normalizer import TableNormalizer
from .logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class TableExtractionResult:
    """Result of table extraction from a single page."""
    page_num: int
    tables: List[List[List[str]]] = field(default_factory=list)
    method_used: str = ""
    quality_scores: List[float] = field(default_factory=list)
    extraction_time: float = 0.0
    success: bool = False
    error_message: str = ""
    table_areas: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class PageAnalysis:
    """Analysis of page structure for choosing extraction strategy."""
    page_num: int
    has_lines: bool = False
    line_count: int = 0
    has_text_columns: bool = False
    text_blocks: int = 0
    recommended_strategy: str = "ruled"  # "ruled" or "unruled"
    confidence: float = 0.0


class TableExtractor:
    """
    Multi-library table extraction with intelligent cascading strategy.
    
    Features:
    - Pre-analysis using PyMuPDF to choose optimal extraction method
    - Cascading extraction: pdfplumber -> camelot -> tabula
    - Quality validation and scoring
    - Consistent output normalization
    - Comprehensive error handling and logging
    """
    
    def __init__(self, 
                 filepath: str,
                 min_quality_score: float = 0.3,
                 enable_pre_analysis: bool = True,
                 fallback_on_failure: bool = True):
        """
        Initialize the table extractor.
        
        Args:
            filepath: Path to the PDF file
            min_quality_score: Minimum quality score to accept a table (0-1)
            enable_pre_analysis: Use PyMuPDF to analyze page before extraction
            fallback_on_failure: Try other methods if primary method fails
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
        
        self.min_quality_score = min_quality_score
        self.enable_pre_analysis = enable_pre_analysis
        self.fallback_on_failure = fallback_on_failure
        
        # Initialize wrappers
        self.pdfplumber_wrapper = PdfplumberWrapper(str(filepath))
        self.camelot_wrapper = CamelotWrapper(str(filepath))
        self.tabula_wrapper = TabulaWrapper(str(filepath))
        
        # Initialize normalizer
        self.normalizer = TableNormalizer()
        
        # Cache for page analysis
        self._page_analysis_cache: Dict[int, PageAnalysis] = {}
    
    def extract_tables_from_page(self, page_num: int) -> TableExtractionResult:
        """
        Extract tables from a single page using intelligent cascading strategy.
        
        Args:
            page_num: Zero-based page number
            
        Returns:
            TableExtractionResult with extracted tables and metadata
        """
        import time
        start_time = time.time()
        
        result = TableExtractionResult(page_num=page_num)
        
        try:
            # Step 1: Analyze page structure if enabled
            if self.enable_pre_analysis:
                try:
                    analysis = self._analyze_page_structure(page_num)
                    logger.debug(f"Page {page_num} analysis: {analysis.recommended_strategy} "
                               f"(confidence: {analysis.confidence:.2f})")
                except Exception as e:
                    logger.warning(f"Page structure analysis failed for page {page_num}: {str(e)}")
                    analysis = PageAnalysis(page_num=page_num, recommended_strategy="ruled")
            else:
                analysis = PageAnalysis(page_num=page_num, recommended_strategy="ruled")
            
            # Step 2: Choose extraction strategy based on analysis
            success = False
            tables = []
            method = "none"
            
            try:
                if analysis.recommended_strategy == "ruled":
                    success, tables, method = self._extract_ruled_tables(page_num)
                else:
                    success, tables, method = self._extract_unruled_tables(page_num)
            except Exception as e:
                logger.warning(f"Primary table extraction strategy failed for page {page_num}: {str(e)}")
                success = False
            
            # Step 3: If primary strategy fails and fallback is enabled, try alternative
            if not success and self.fallback_on_failure:
                try:
                    logger.debug(f"Primary strategy failed for page {page_num}, trying fallback")
                    if analysis.recommended_strategy == "ruled":
                        success, tables, method = self._extract_unruled_tables(page_num)
                    else:
                        success, tables, method = self._extract_ruled_tables(page_num)
                    method = f"fallback-{method}"
                except Exception as e:
                    logger.warning(f"Fallback table extraction failed for page {page_num}: {str(e)}")
                    success = False
            
            # Step 4: Validate and score the results
            if success and tables:
                try:
                    validated_tables = []
                    quality_scores = []
                    
                    for table_idx, table in enumerate(tables):
                        try:
                            analysis_result = self.normalizer.analyze_table_structure(table)
                            quality_score = analysis_result.get("estimated_quality", 0.0)
                            
                            if analysis_result["valid"] and quality_score >= self.min_quality_score:
                                validated_tables.append(table)
                                quality_scores.append(quality_score)
                            else:
                                logger.debug(f"Table {table_idx} rejected: quality={quality_score:.2f}, "
                                           f"reason={analysis_result.get('reason', 'low quality')}")
                        except Exception as e:
                            logger.warning(f"Table validation failed for table {table_idx} on page {page_num}: {str(e)}")
                            continue
                    
                    result.tables = validated_tables
                    result.quality_scores = quality_scores
                    result.method_used = method
                    result.success = len(validated_tables) > 0
                    
                    if result.success:
                        logger.debug(f"Successfully extracted {len(validated_tables)} tables from page {page_num}")
                    else:
                        logger.debug(f"No valid tables found on page {page_num} after validation")
                        
                except Exception as e:
                    logger.warning(f"Table validation process failed for page {page_num}: {str(e)}")
                    result.success = False
                    result.error_message = f"Validation failed: {str(e)}"
                result.success = len(validated_tables) > 0
                
                if result.success:
                    logger.info(f"Successfully extracted {len(validated_tables)} tables "
                               f"from page {page_num} using {method}")
                else:
                    logger.warning(f"No valid tables found on page {page_num}")
            else:
                result.success = False
                result.error_message = f"No tables extracted using any method"
                logger.warning(f"Failed to extract tables from page {page_num}")
        
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            logger.error(f"Table extraction failed for page {page_num}: {e}")
        
        finally:
            result.extraction_time = time.time() - start_time
        
        return result
    
    def extract_tables_from_pdf(self) -> List[TableExtractionResult]:
        """
        Extract tables from all pages in the PDF.
        
        Returns:
            List of TableExtractionResult for each page
        """
        results = []
        
        # Get total number of pages
        with fitz.open(str(self.filepath)) as doc:
            total_pages = len(doc)
        
        logger.info(f"Starting table extraction from {total_pages} pages")
        
        for page_num in range(total_pages):
            result = self.extract_tables_from_page(page_num)
            results.append(result)
        
        # Summary statistics
        successful_pages = sum(1 for r in results if r.success)
        total_tables = sum(len(r.tables) for r in results)
        avg_quality = sum(sum(r.quality_scores) for r in results) / max(1, total_tables)
        
        logger.info(f"Extraction complete: {successful_pages}/{total_pages} pages successful, "
                   f"{total_tables} tables extracted, avg quality: {avg_quality:.2f}")
        
        return results
    
    def _analyze_page_structure(self, page_num: int) -> PageAnalysis:
        """
        Analyze page structure using PyMuPDF to determine optimal extraction strategy.
        
        Args:
            page_num: Zero-based page number
            
        Returns:
            PageAnalysis with recommended strategy
        """
        if page_num in self._page_analysis_cache:
            return self._page_analysis_cache[page_num]
        
        analysis = PageAnalysis(page_num=page_num)
        
        try:
            with fitz.open(str(self.filepath)) as doc:
                if page_num >= len(doc):
                    return analysis
                
                page = doc[page_num]
                
                # Analyze vector graphics (lines/shapes)
                drawings = page.get_drawings()
                line_segments = []
                
                for drawing in drawings:
                    for item in drawing.get("items", []):
                        if item[0] in ["l", "re"]:  # line or rectangle
                            line_segments.append(item)
                
                analysis.line_count = len(line_segments)
                analysis.has_lines = analysis.line_count > 10  # Threshold for ruled tables
                
                # Analyze text structure
                text_dict = page.get_text("dict")
                text_blocks = []
                
                for block in text_dict.get("blocks", []):
                    if "lines" in block:  # Text block
                        text_blocks.append(block)
                
                analysis.text_blocks = len(text_blocks)
                
                # Check for column-like text alignment
                if text_blocks:
                    x_positions = []
                    for block in text_blocks:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                x_positions.append(span["bbox"][0])  # x0 coordinate
                    
                    # Look for repeated x-coordinates (column alignment)
                    if x_positions:
                        from collections import Counter
                        x_counts = Counter(round(x, -1) for x in x_positions)  # Round to nearest 10
                        common_x = [x for x, count in x_counts.items() if count > 2]
                        analysis.has_text_columns = len(common_x) >= 2
                
                # Determine strategy based on analysis
                if analysis.has_lines:
                    analysis.recommended_strategy = "ruled"
                    analysis.confidence = min(0.9, analysis.line_count / 50)  # More lines = higher confidence
                elif analysis.has_text_columns:
                    analysis.recommended_strategy = "unruled"
                    analysis.confidence = 0.7
                else:
                    # Default to ruled with low confidence
                    analysis.recommended_strategy = "ruled"
                    analysis.confidence = 0.3
                
        except Exception as e:
            logger.error(f"Page analysis failed for page {page_num}: {e}")
            # Default strategy
            analysis.recommended_strategy = "ruled"
            analysis.confidence = 0.1
        
        # Cache the result
        self._page_analysis_cache[page_num] = analysis
        return analysis
    
    def _extract_ruled_tables(self, page_num: int) -> Tuple[bool, List[List[List[str]]], str]:
        """
        Extract tables using ruled table strategy (pdfplumber -> camelot lattice).
        
        Returns:
            (success, tables, method_used)
        """
        # Try pdfplumber first (fastest for ruled tables)
        try:
            tables = self.pdfplumber_wrapper.extract_tables_from_page(page_num)
            if tables and any(self.pdfplumber_wrapper.validate_table(t) for t in tables):
                valid_tables = [t for t in tables if self.pdfplumber_wrapper.validate_table(t)]
                return True, valid_tables, "pdfplumber"
        except Exception as e:
            logger.debug(f"pdfplumber failed for page {page_num}: {e}")
        
        # Try camelot lattice (best for complex ruled tables)
        try:
            tables = self.camelot_wrapper.extract_lattice(page_num)
            if tables and any(self.camelot_wrapper.validate_table(t) for t in tables):
                valid_tables = [t for t in tables if self.camelot_wrapper.validate_table(t)]
                return True, valid_tables, "camelot-lattice"
        except Exception as e:
            logger.debug(f"camelot-lattice failed for page {page_num}: {e}")
        
        return False, [], "none"
    
    def _extract_unruled_tables(self, page_num: int) -> Tuple[bool, List[List[List[str]]], str]:
        """
        Extract tables using unruled table strategy (camelot stream -> tabula).
        
        Returns:
            (success, tables, method_used)
        """
        # Try camelot stream (best for unruled tables)
        try:
            tables = self.camelot_wrapper.extract_stream(page_num)
            if tables and any(self.camelot_wrapper.validate_table(t) for t in tables):
                valid_tables = [t for t in tables if self.camelot_wrapper.validate_table(t)]
                return True, valid_tables, "camelot-stream"
        except Exception as e:
            logger.debug(f"camelot-stream failed for page {page_num}: {e}")
        
        # Try tabula (reliable fallback)
        try:
            tables = self.tabula_wrapper.extract_tables_from_page(page_num)
            if tables and any(self.tabula_wrapper.validate_table(t) for t in tables):
                valid_tables = [t for t in tables if self.tabula_wrapper.validate_table(t)]
                return True, valid_tables, "tabula"
        except Exception as e:
            logger.debug(f"tabula failed for page {page_num}: {e}")
        
        return False, [], "none"
    
    def get_extraction_statistics(self, results: List[TableExtractionResult]) -> Dict[str, Any]:
        """
        Generate statistics about the extraction process.
        
        Args:
            results: List of extraction results
            
        Returns:
            Dictionary with extraction statistics
        """
        if not results:
            return {}
        
        total_pages = len(results)
        successful_pages = sum(1 for r in results if r.success)
        total_tables = sum(len(r.tables) for r in results)
        
        # Method usage statistics
        method_counts = {}
        for result in results:
            if result.success:
                method = result.method_used
                method_counts[method] = method_counts.get(method, 0) + 1
        
        # Quality statistics
        all_scores = []
        for result in results:
            all_scores.extend(result.quality_scores)
        
        avg_quality = sum(all_scores) / len(all_scores) if all_scores else 0
        min_quality = min(all_scores) if all_scores else 0
        max_quality = max(all_scores) if all_scores else 0
        
        # Timing statistics
        total_time = sum(r.extraction_time for r in results)
        avg_time_per_page = total_time / total_pages if total_pages > 0 else 0
        
        return {
            "total_pages": total_pages,
            "successful_pages": successful_pages,
            "success_rate": successful_pages / total_pages if total_pages > 0 else 0,
            "total_tables": total_tables,
            "avg_tables_per_page": total_tables / successful_pages if successful_pages > 0 else 0,
            "method_usage": method_counts,
            "quality_stats": {
                "average": avg_quality,
                "minimum": min_quality,
                "maximum": max_quality,
                "count": len(all_scores)
            },
            "timing": {
                "total_time": total_time,
                "avg_time_per_page": avg_time_per_page
            }
        }