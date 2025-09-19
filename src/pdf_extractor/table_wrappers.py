import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import pdfplumber
import camelot
import tabula
import pandas as pd

logger = logging.getLogger(__name__)


class PdfplumberWrapper:
    def __init__(self, filepath: str):
        """Initialize the wrapper with a PDF file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
    
    def extract_tables_from_page(self, page_num: int, **kwargs) -> List[List[List[str]]]:
        try:
            with pdfplumber.open(str(self.filepath)) as pdf:
                if page_num >= len(pdf.pages):
                    logger.warning(f"Page {page_num} does not exist in PDF")
                    return []
                
                page = pdf.pages[page_num]
                

                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines", 
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "edge_min_length": 3,
                    "min_words_vertical": 3,
                    "min_words_horizontal": 1,
                    **kwargs
                }
                

                raw_tables = page.extract_tables(table_settings=table_settings)
                
                if not raw_tables:
                    logger.debug(f"No tables found on page {page_num} using pdfplumber")
                    return []
                

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
        return self.extract_tables_from_page(page_num, **table_settings)
    
    def validate_table(self, table: List[List[str]]) -> bool:
        if not table or len(table) < 2:
            return False
        

        if not table[0] or len(table[0]) < 2:
            return False
        

        col_counts = [len(row) for row in table]
        max_cols = max(col_counts)
        min_cols = min(col_counts)
        

        if min_cols < max_cols * 0.5:
            return False
        

        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        total_cells = sum(len(row) for row in table)
        
        if total_cells == 0 or non_empty_cells / total_cells < 0.1:
            return False
        
        return True


class CamelotWrapper:
    def __init__(self, filepath: str):
        """Initialize the wrapper with a PDF file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
    
    def extract_tables_from_page(self, page_num: int, flavor: str = "lattice", **kwargs) -> List[List[List[str]]]:
        try:

            page_str = str(page_num + 1)
            

            if flavor == "lattice":
                default_params = {
                    "line_scale": 15,
                    "copy_text": None,
                    "shift_text": [""],
                    "line_tol": 2,
                    "joint_tol": 2,
                }
            else:
                default_params = {
                    "row_tol": 2,
                    "column_tol": 0,
                }
            

            params = {**default_params, **kwargs}
            

            tables = camelot.read_pdf(
                str(self.filepath),
                pages=page_str,
                flavor=flavor,
                **params
            )
            
            if not tables or tables.n == 0:
                logger.debug(f"No tables found on page {page_num} using camelot ({flavor})")
                return []
            

            normalized_tables = []
            for table in tables:

                df = table.df
                

                table_data = []
                

                header = [str(col) for col in df.columns]
                table_data.append(header)
                

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
        try:
            page_str = str(page_num + 1)
            tables = camelot.read_pdf(str(self.filepath), pages=page_str, flavor=flavor)
            
            return [table.accuracy for table in tables] if tables else []
            
        except Exception as e:
            logger.error(f"Failed to get quality scores for page {page_num}: {e}")
            return []
    
    def validate_table(self, table: List[List[str]]) -> bool:
        if not table or len(table) < 2:
            return False
        

        if not table[0] or len(table[0]) < 2:
            return False
        

        col_counts = [len(row) for row in table]
        if len(set(col_counts)) > 2:
            return False
        

        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        total_cells = sum(len(row) for row in table)
        
        if total_cells == 0 or non_empty_cells / total_cells < 0.2:
            return False
        
        return True


class TabulaWrapper:
    def __init__(self, filepath: str):
        """Initialize the wrapper with a PDF file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
    
    def extract_tables_from_page(self, page_num: int, **kwargs) -> List[List[List[str]]]:
        try:

            page_str = str(page_num + 1)
            

            default_params = {
                "guess": True,
                "multiple_tables": True,
                "pandas_options": {"header": None},
                "silent": True
            }
            

            params = {**default_params, **kwargs}
            

            dfs = tabula.read_pdf(
                str(self.filepath),
                pages=page_str,
                **params
            )
            
            if not dfs:
                logger.debug(f"No tables found on page {page_num} using tabula")
                return []
            

            normalized_tables = []
            for df in dfs:

                df = df.reset_index(drop=True)
                

                table_data = []
                for _, row in df.iterrows():
                    row_data = [str(cell).strip() if pd.notnull(cell) else "" for cell in row]
                    table_data.append(row_data)
                

                if table_data and len(table_data) > 1:
                    normalized_tables.append(table_data)
            
            logger.info(f"Extracted {len(normalized_tables)} tables from page {page_num} using tabula")
            return normalized_tables
            
        except Exception as e:
            logger.error(f"Tabula extraction failed for page {page_num}: {e}")
            return []
    
    def extract_with_area(self, page_num: int, area: List[float], **kwargs) -> List[List[List[str]]]:
        kwargs["area"] = area
        return self.extract_tables_from_page(page_num, **kwargs)
    
    def extract_with_columns(self, page_num: int, columns: List[float], **kwargs) -> List[List[List[str]]]:
    
        kwargs["columns"] = columns
        kwargs["guess"] = False
        return self.extract_tables_from_page(page_num, **kwargs)
    
    def validate_table(self, table: List[List[str]]) -> bool:
        if not table or len(table) < 2:
            return False
        

        if not table[0] or len(table[0]) < 2:
            return False
        

        col_counts = [len(row) for row in table]
        max_cols = max(col_counts)
        

        acceptable_rows = sum(1 for count in col_counts if count >= max_cols * 0.3)
        if acceptable_rows < len(table) * 0.5:
            return False
        

        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        total_cells = sum(len(row) for row in table)
        
        if total_cells == 0 or non_empty_cells / total_cells < 0.05:
            return False
        
        return True