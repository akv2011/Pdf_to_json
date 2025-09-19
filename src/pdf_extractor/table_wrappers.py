"""
Table extraction wrappers for different PDF processing libraries.

This module provides consistent interfaces for pdfplumber, camelot-py, and tabula-py
to enable intelligent cascading table extraction strategies.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import pdfplumber
import camelot
import tabula
import pandas as pd

logger = logging.getLogger(__name__)


class PdfplumberWrapper:
    """
    Wrapper for pdfplumber table extraction.
    
    Strengths:
    - Fast and lightweight (pure Python)
    - Excellent for ruled tables with clear line separators
    - Direct integration with existing pdfplumber-based code
    
    Weaknesses:
    - Struggles with unruled/whitespace-separated tables
    - Limited merged cell support
    - Cannot process scanned PDFs
    """
    
    def __init__(self, filepath: str):
        """Initialize the wrapper with a PDF file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
    
    def extract_tables_from_page(self, page_num: int, **kwargs) -> List[List[List[str]]]:
        """
        Extract tables from a specific page using pdfplumber.
        
        Args:
            page_num: Zero-based page number
            **kwargs: Additional arguments for table extraction settings
            
        Returns:
            List of tables, where each table is a list of rows,
            and each row is a list of cell values as strings
        """
        try:
            with pdfplumber.open(str(self.filepath)) as pdf:
                if page_num >= len(pdf.pages):
                    logger.warning(f"Page {page_num} does not exist in PDF")
                    return []
                
                page = pdf.pages[page_num]
                
                # Use default settings optimized for ruled tables
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines", 
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "edge_min_length": 3,
                    "min_words_vertical": 3,
                    "min_words_horizontal": 1,
                    **kwargs  # Allow overrides
                }
                
                # Extract tables using the settings
                raw_tables = page.extract_tables(table_settings=table_settings)
                
                if not raw_tables:
                    logger.debug(f"No tables found on page {page_num} using pdfplumber")
                    return []
                
                # Normalize the data - convert None values to empty strings
                normalized_tables = []
                for table in raw_tables:
                    normalized_table = []
                    for row in table:
                        normalized_row = [
                            str(cell).strip() if cell is not None else ""
                            for cell in row
                        ]
                        normalized_table.append(normalized_row)
                    normalized_tables.append(normalized_table)
                
                logger.info(f"Extracted {len(normalized_tables)} tables from page {page_num} using pdfplumber")
                return normalized_tables
                
        except Exception as e:
            logger.error(f"pdfplumber extraction failed for page {page_num}: {e}")
            return []
    
    def find_table_areas(self, page_num: int) -> List[Dict[str, float]]:
        """
        Find potential table areas on a page without extracting content.
        
        Args:
            page_num: Zero-based page number
            
        Returns:
            List of bounding box dictionaries with keys: x0, y0, x1, y1
        """
        try:
            with pdfplumber.open(str(self.filepath)) as pdf:
                if page_num >= len(pdf.pages):
                    return []
                
                page = pdf.pages[page_num]
                tables = page.find_tables()
                
                return [
                    {
                        "x0": table.bbox[0],
                        "y0": table.bbox[1], 
                        "x1": table.bbox[2],
                        "y1": table.bbox[3]
                    }
                    for table in tables
                ]
                
        except Exception as e:
            logger.error(f"Failed to find table areas on page {page_num}: {e}")
            return []
    
    def extract_with_settings(self, page_num: int, table_settings: Dict[str, Any]) -> List[List[List[str]]]:
        """
        Extract tables with custom settings for fine-tuning.
        
        Args:
            page_num: Zero-based page number
            table_settings: Dictionary of pdfplumber table extraction settings
            
        Returns:
            List of normalized tables
        """
        return self.extract_tables_from_page(page_num, **table_settings)
    
    def validate_table(self, table: List[List[str]]) -> bool:
        """
        Validate that a table has reasonable structure.
        
        Args:
            table: A table represented as list of rows
            
        Returns:
            True if table appears valid, False otherwise
        """
        if not table or len(table) < 2:
            return False
        
        # Check that we have at least 2 columns
        if not table[0] or len(table[0]) < 2:
            return False
        
        # Check for consistent column counts (allowing some variance)
        col_counts = [len(row) for row in table]
        max_cols = max(col_counts)
        min_cols = min(col_counts)
        
        # Allow up to 50% variance in column counts for ragged tables
        if min_cols < max_cols * 0.5:
            return False
        
        # Check that we have some non-empty content
        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        total_cells = sum(len(row) for row in table)
        
        if total_cells == 0 or non_empty_cells / total_cells < 0.1:
            return False
        
        return True


class CamelotWrapper:
    """
    Wrapper for camelot-py table extraction.
    
    Strengths:
    - Excellent accuracy for complex layouts
    - Two specialized flavors: 'lattice' for ruled tables, 'stream' for unruled
    - Superior merged cell support 
    - Visual debugging capabilities
    
    Weaknesses:
    - Requires OpenCV and Ghostscript dependencies
    - Slower due to image processing
    - Complex parameter tuning
    """
    
    def __init__(self, filepath: str):
        """Initialize the wrapper with a PDF file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
    
    def extract_tables_from_page(self, page_num: int, flavor: str = "lattice", **kwargs) -> List[List[List[str]]]:
        """
        Extract tables from a specific page using camelot.
        
        Args:
            page_num: Zero-based page number  
            flavor: 'lattice' for ruled tables, 'stream' for unruled tables
            **kwargs: Additional camelot extraction parameters
            
        Returns:
            List of tables, where each table is a list of rows,
            and each row is a list of cell values as strings
        """
        try:
            # Camelot uses 1-based page numbering
            page_str = str(page_num + 1)
            
            # Default parameters for each flavor
            if flavor == "lattice":
                default_params = {
                    "line_scale": 15,
                    "copy_text": None,
                    "shift_text": [""],
                    "line_tol": 2,
                    "joint_tol": 2,
                }
            else:  # stream
                default_params = {
                    "row_tol": 2,
                    "column_tol": 0,
                }
            
            # Merge with user-provided kwargs
            params = {**default_params, **kwargs}
            
            # Extract tables
            tables = camelot.read_pdf(
                str(self.filepath),
                pages=page_str,
                flavor=flavor,
                **params
            )
            
            if not tables or tables.n == 0:
                logger.debug(f"No tables found on page {page_num} using camelot ({flavor})")
                return []
            
            # Convert DataFrames to list of lists
            normalized_tables = []
            for table in tables:
                # Get the DataFrame
                df = table.df
                
                # Convert to list of lists with header
                table_data = []
                
                # Add header row (column names)
                header = [str(col) for col in df.columns]
                table_data.append(header)
                
                # Add data rows
                for _, row in df.iterrows():
                    row_data = [str(cell).strip() if pd.notnull(cell) else "" for cell in row]
                    table_data.append(row_data)
                
                normalized_tables.append(table_data)
            
            logger.info(f"Extracted {len(normalized_tables)} tables from page {page_num} using camelot ({flavor})")
            return normalized_tables
            
        except Exception as e:
            logger.error(f"Camelot ({flavor}) extraction failed for page {page_num}: {e}")
            return []
    
    def extract_lattice(self, page_num: int, **kwargs) -> List[List[List[str]]]:
        """Extract tables using lattice flavor (for ruled tables)."""
        return self.extract_tables_from_page(page_num, flavor="lattice", **kwargs)
    
    def extract_stream(self, page_num: int, **kwargs) -> List[List[List[str]]]:
        """Extract tables using stream flavor (for unruled tables).""" 
        return self.extract_tables_from_page(page_num, flavor="stream", **kwargs)
    
    def get_table_quality_scores(self, page_num: int, flavor: str = "lattice") -> List[float]:
        """
        Get quality scores for extracted tables.
        
        Args:
            page_num: Zero-based page number
            flavor: 'lattice' or 'stream'
            
        Returns:
            List of accuracy scores (0-100) for each table
        """
        try:
            page_str = str(page_num + 1)
            tables = camelot.read_pdf(str(self.filepath), pages=page_str, flavor=flavor)
            
            return [table.accuracy for table in tables] if tables else []
            
        except Exception as e:
            logger.error(f"Failed to get quality scores for page {page_num}: {e}")
            return []
    
    def validate_table(self, table: List[List[str]]) -> bool:
        """
        Validate that a table has reasonable structure.
        
        Args:
            table: A table represented as list of rows
            
        Returns:
            True if table appears valid, False otherwise
        """
        if not table or len(table) < 2:
            return False
        
        # Check that we have at least 2 columns
        if not table[0] or len(table[0]) < 2:
            return False
        
        # For camelot, we expect more consistent column counts
        col_counts = [len(row) for row in table]
        if len(set(col_counts)) > 2:  # Allow at most 2 different column counts
            return False
        
        # Check for reasonable content density
        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        total_cells = sum(len(row) for row in table)
        
        if total_cells == 0 or non_empty_cells / total_cells < 0.2:
            return False
        
        return True


class TabulaWrapper:
    """
    Wrapper for tabula-py table extraction.
    
    Strengths:
    - Robust and mature Java-based engine
    - Good for scanned documents (with OCR layer)
    - Simple API
    - Reliable fallback option
    
    Weaknesses:
    - Requires Java dependency
    - Slower due to JVM startup overhead
    - Less accurate on complex layouts compared to camelot
    """
    
    def __init__(self, filepath: str):
        """Initialize the wrapper with a PDF file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
    
    def extract_tables_from_page(self, page_num: int, **kwargs) -> List[List[List[str]]]:
        """
        Extract tables from a specific page using tabula.
        
        Args:
            page_num: Zero-based page number
            **kwargs: Additional tabula extraction parameters
            
        Returns:
            List of tables, where each table is a list of rows,
            and each row is a list of cell values as strings
        """
        try:
            # Tabula uses 1-based page numbering
            page_str = str(page_num + 1)
            
            # Default parameters
            default_params = {
                "guess": True,
                "multiple_tables": True,
                "pandas_options": {"header": None},  # Don't assume first row is header
                "silent": True  # Suppress Java output
            }
            
            # Merge with user-provided kwargs
            params = {**default_params, **kwargs}
            
            # Extract tables - returns list of DataFrames
            dfs = tabula.read_pdf(
                str(self.filepath),
                pages=page_str,
                **params
            )
            
            if not dfs:
                logger.debug(f"No tables found on page {page_num} using tabula")
                return []
            
            # Convert DataFrames to list of lists
            normalized_tables = []
            for df in dfs:
                # Reset index to ensure we get all data
                df = df.reset_index(drop=True)
                
                # Convert to list of lists
                table_data = []
                for _, row in df.iterrows():
                    row_data = [str(cell).strip() if pd.notnull(cell) else "" for cell in row]
                    table_data.append(row_data)
                
                # Only add if we have meaningful content
                if table_data and len(table_data) > 1:
                    normalized_tables.append(table_data)
            
            logger.info(f"Extracted {len(normalized_tables)} tables from page {page_num} using tabula")
            return normalized_tables
            
        except Exception as e:
            logger.error(f"Tabula extraction failed for page {page_num}: {e}")
            return []
    
    def extract_with_area(self, page_num: int, area: List[float], **kwargs) -> List[List[List[str]]]:
        """
        Extract tables from a specific area on the page.
        
        Args:
            page_num: Zero-based page number
            area: [top, left, bottom, right] coordinates in points
            **kwargs: Additional tabula parameters
            
        Returns:
            List of normalized tables
        """
        kwargs["area"] = area
        return self.extract_tables_from_page(page_num, **kwargs)
    
    def extract_with_columns(self, page_num: int, columns: List[float], **kwargs) -> List[List[List[str]]]:
        """
        Extract tables with specified column boundaries.
        
        Args:
            page_num: Zero-based page number  
            columns: List of x-coordinates for column boundaries
            **kwargs: Additional tabula parameters
            
        Returns:
            List of normalized tables
        """
        kwargs["columns"] = columns
        kwargs["guess"] = False  # Don't auto-detect when columns are specified
        return self.extract_tables_from_page(page_num, **kwargs)
    
    def validate_table(self, table: List[List[str]]) -> bool:
        """
        Validate that a table has reasonable structure.
        
        Args:
            table: A table represented as list of rows
            
        Returns:
            True if table appears valid, False otherwise
        """
        if not table or len(table) < 2:
            return False
        
        # Check that we have at least 2 columns
        if not table[0] or len(table[0]) < 2:
            return False
        
        # Tabula can produce very ragged tables, so be more lenient
        col_counts = [len(row) for row in table]
        max_cols = max(col_counts)
        
        # Check that most rows have reasonable column counts
        acceptable_rows = sum(1 for count in col_counts if count >= max_cols * 0.3)
        if acceptable_rows < len(table) * 0.5:
            return False
        
        # Check for some non-empty content
        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        total_cells = sum(len(row) for row in table)
        
        if total_cells == 0 or non_empty_cells / total_cells < 0.05:  # Very lenient
            return False
        
        return True