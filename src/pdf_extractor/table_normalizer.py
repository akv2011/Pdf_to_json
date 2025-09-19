"""
Data normalization utilities for table extraction.

This module provides functions to normalize table data from different sources
into consistent formats for the PDF to JSON pipeline.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Union
from decimal import Decimal

import pandas as pd

logger = logging.getLogger(__name__)


class TableNormalizer:
    def __init__(self, 
                 strip_whitespace: bool = True,
                 normalize_spacing: bool = True,
                 handle_currency: bool = True,
                 detect_numbers: bool = True):
        self.strip_whitespace = strip_whitespace
        self.normalize_spacing = normalize_spacing
        self.handle_currency = handle_currency
        self.detect_numbers = detect_numbers
        

        self.currency_pattern = re.compile(r'[\$€£¥₹]')
        self.number_pattern = re.compile(r'^[\-+]?(\d{1,3}(,\d{3})*|\d+)(\.\d+)?$')
        self.percent_pattern = re.compile(r'^[\-+]?\d+(\.\d+)?%$')
    
    def normalize_table(self, table_data: Any, source: str = "unknown") -> List[List[str]]:
        try:
            if isinstance(table_data, pd.DataFrame):
                return self._normalize_dataframe(table_data)
            elif isinstance(table_data, list):
                return self._normalize_list_of_lists(table_data)
            elif hasattr(table_data, 'df'):
                return self._normalize_dataframe(table_data.df)
            else:
                logger.warning(f"Unknown table format from {source}: {type(table_data)}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to normalize table from {source}: {e}")
            return []
    
    def _normalize_dataframe(self, df: pd.DataFrame) -> List[List[str]]:

        df = df.reset_index(drop=True)
        

        header = [self._clean_cell_content(str(col)) for col in df.columns]
        table_data = [header]
        

        for _, row in df.iterrows():
            row_data = [
                self._clean_cell_content(str(cell)) if pd.notnull(cell) else ""
                for cell in row
            ]
            table_data.append(row_data)
        
        return table_data
    
    def _normalize_list_of_lists(self, table: List[List[Any]]) -> List[List[str]]:
        normalized_table = []
        
        for row in table:
            normalized_row = [
                self._clean_cell_content(str(cell)) if cell is not None else ""
                for cell in row
            ]
            normalized_table.append(normalized_row)
        
        return normalized_table
    
    def _clean_cell_content(self, content: str) -> str:
        if not content or content.lower() in ['nan', 'none', 'null']:
            return ""
        

        if self.strip_whitespace:
            content = content.strip()
        

        if self.normalize_spacing:
            content = re.sub(r'\s+', ' ', content)
        

        content = re.sub(r'[\r\n]+', ' ', content)
        
        return content
    
    def detect_data_type(self, content: str) -> Dict[str, Any]:
        if not content.strip():
            return {"type": "empty", "value": "", "raw": content}
        
        content = content.strip()
        

        if self.percent_pattern.match(content):
            try:
                value = float(content.rstrip('%'))
                return {
                    "type": "percentage", 
                    "value": value, 
                    "raw": content,
                    "formatted": f"{value}%"
                }
            except ValueError:
                pass
        

        if self.currency_pattern.search(content):
            currency_symbol = self.currency_pattern.search(content).group()
            numeric_part = self.currency_pattern.sub('', content).replace(',', '').strip()
            try:
                value = float(numeric_part)
                return {
                    "type": "currency",
                    "value": value,
                    "currency": currency_symbol,
                    "raw": content,
                    "formatted": f"{currency_symbol}{value:,.2f}"
                }
            except ValueError:
                pass
        

        clean_number = content.replace(',', '')
        if self.number_pattern.match(clean_number):
            try:
                if '.' in clean_number:
                    value = float(clean_number)
                    return {
                        "type": "float",
                        "value": value,
                        "raw": content,
                        "formatted": str(value)
                    }
                else:
                    value = int(clean_number)
                    return {
                        "type": "integer", 
                        "value": value,
                        "raw": content,
                        "formatted": str(value)
                    }
            except ValueError:
                pass
        

        return {"type": "text", "value": content, "raw": content}
    
    def normalize_tables_batch(self, tables: List[Any], source: str = "unknown") -> List[List[List[str]]]:
        normalized_tables = []
        
        for i, table in enumerate(tables):
            try:
                normalized = self.normalize_table(table, f"{source}[{i}]")
                if normalized and len(normalized) > 1:
                    normalized_tables.append(normalized)
            except Exception as e:
                logger.error(f"Failed to normalize table {i} from {source}: {e}")
                continue
        
        return normalized_tables
    
    def analyze_table_structure(self, table: List[List[str]]) -> Dict[str, Any]:
        if not table:
            return {"valid": False, "reason": "Empty table"}
        
        num_rows = len(table)
        if num_rows < 2:
            return {"valid": False, "reason": "Less than 2 rows"}
        

        col_counts = [len(row) for row in table]
        max_cols = max(col_counts)
        min_cols = min(col_counts)
        

        header = table[0]
        data_rows = table[1:]
        

        column_types = []
        for col_idx in range(max_cols):
            column_values = []
            for row in data_rows:
                if col_idx < len(row) and row[col_idx].strip():
                    column_values.append(row[col_idx])
            
            if column_values:

                type_counts = {}
                for value in column_values[:10]:
                    data_type = self.detect_data_type(value)["type"]
                    type_counts[data_type] = type_counts.get(data_type, 0) + 1
                
                predominant_type = max(type_counts, key=type_counts.get) if type_counts else "text"
                column_types.append(predominant_type)
            else:
                column_types.append("empty")
        

        total_cells = sum(len(row) for row in table)
        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        content_density = non_empty_cells / total_cells if total_cells > 0 else 0
        
        return {
            "valid": True,
            "num_rows": num_rows,
            "num_cols": max_cols,
            "min_cols": min_cols,
            "max_cols": max_cols,
            "column_consistency": min_cols / max_cols if max_cols > 0 else 0,
            "header": header,
            "column_types": column_types,
            "content_density": content_density,
            "has_numbers": any(t in ["integer", "float", "currency", "percentage"] for t in column_types),
            "estimated_quality": self._estimate_table_quality(num_rows, max_cols, content_density, min_cols/max_cols if max_cols > 0 else 0)
        }
    
    def _estimate_table_quality(self, num_rows: int, num_cols: int, density: float, consistency: float) -> float:
        structure_score = min(1.0, (num_rows - 1) * num_cols / 20)
        

        content_score = density * 0.8 + consistency * 0.2
        

        quality = (structure_score * 0.3 + content_score * 0.7)
        
        return max(0.0, min(1.0, quality))