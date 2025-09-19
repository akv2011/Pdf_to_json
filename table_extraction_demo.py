#!/usr/bin/env python3
"""
Demo script for testing table extraction functionality.

This script demonstrates the table extraction capabilities on a real PDF file.
"""

import sys
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.pdf_extractor.table_extractor import TableExtractor
from src.pdf_extractor.table_normalizer import TableNormalizer


def main():
    """Main demo function."""
    # Look for a PDF file in the project
    pdf_path = None
    
    # Check for existing PDFs
    for pdf_file in project_root.glob("*.pdf"):
        pdf_path = pdf_file
        break
    
    # Check in rfp-bid-main directory
    if not pdf_path:
        rfp_dir = project_root / "rfp-bid-main" / "example-PDF"
        if rfp_dir.exists():
            for pdf_file in rfp_dir.glob("*.pdf"):
                pdf_path = pdf_file
                break
    
    if not pdf_path:
        print("No PDF file found for testing. Please place a PDF file in the project root.")
        return
    
    print(f"Testing table extraction on: {pdf_path}")
    print("=" * 60)
    
    try:
        # Initialize table extractor
        extractor = TableExtractor(
            str(pdf_path),
            min_quality_score=0.2,  # Lower threshold for demo
            enable_pre_analysis=True,
            fallback_on_failure=True
        )
        
        # Extract tables from first few pages
        max_pages = 3
        results = []
        
        print(f"Extracting tables from first {max_pages} pages...\n")
        
        for page_num in range(max_pages):
            print(f"Processing page {page_num + 1}...")
            result = extractor.extract_tables_from_page(page_num)
            results.append(result)
            
            if result.success:
                print(f"  ✓ Found {len(result.tables)} table(s) using {result.method_used}")
                print(f"  ✓ Quality scores: {[f'{q:.2f}' for q in result.quality_scores]}")
                print(f"  ✓ Extraction time: {result.extraction_time:.2f}s")
                
                # Show first table structure
                if result.tables:
                    table = result.tables[0]
                    print(f"  ✓ First table: {len(table)} rows × {len(table[0]) if table else 0} columns")
                    
                    # Show first few rows
                    for i, row in enumerate(table[:3]):
                        print(f"    Row {i}: {row}")
                    if len(table) > 3:
                        print(f"    ... ({len(table) - 3} more rows)")
            else:
                print(f"  ✗ No tables found - {result.error_message}")
            
            print()
        
        # Generate statistics
        stats = extractor.get_extraction_statistics(results)
        
        print("Extraction Statistics:")
        print("-" * 30)
        print(f"Pages processed: {stats['total_pages']}")
        print(f"Successful pages: {stats['successful_pages']}")
        print(f"Success rate: {stats['success_rate']:.1%}")
        print(f"Total tables: {stats['total_tables']}")
        print(f"Average quality: {stats['quality_stats']['average']:.2f}")
        print(f"Total time: {stats['timing']['total_time']:.2f}s")
        print(f"Methods used: {stats['method_usage']}")
        
        # Save results to JSON
        output_file = project_root / "table_extraction_demo_results.json"
        
        # Convert results to serializable format
        results_data = []
        for result in results:
            results_data.append({
                "page_num": result.page_num,
                "success": result.success,
                "method_used": result.method_used,
                "num_tables": len(result.tables),
                "quality_scores": result.quality_scores,
                "extraction_time": result.extraction_time,
                "error_message": result.error_message,
                "tables": result.tables  # Include actual table data
            })
        
        output_data = {
            "pdf_file": str(pdf_path.name),
            "extraction_results": results_data,
            "statistics": stats
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Error during table extraction: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()