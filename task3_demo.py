#!/usr/bin/env python3
"""
Task 3 Demonstration: Page-Level Content Block and Layout Analysis

This script demonstrates the enhanced page processing capabilities implemented
for Task 3, showing detailed content extraction with bounding boxes, font
information, and reading order analysis.
"""

import json
import sys
from pathlib import Path
from pdf_extractor.extractor import PDFStructureExtractor
from pdf_extractor.models import ExtractionConfig


def analyze_page_structure(pdf_path: str, page_number: int = 1):
    """Analyze and display detailed page structure for demonstration."""
    
    print(f"🔍 Task 3 Demo: Analyzing page {page_number} of {pdf_path}")
    print("=" * 80)
    
    try:
        # Initialize extractor with verbose mode
        config = ExtractionConfig(verbose=True)
        extractor = PDFStructureExtractor(config)
        
        # Extract content
        result = extractor.extract(Path(pdf_path))
        
        if page_number > len(result['pages']):
            print(f"❌ Page {page_number} not found. Document has {len(result['pages'])} pages.")
            return
        
        page_data = result['pages'][page_number - 1]
        
        # Display page overview
        print(f"📄 Page {page_data['page_number']} Overview:")
        print(f"   Dimensions: {page_data['page_width']:.1f} x {page_data['page_height']:.1f}")
        print(f"   Rotation: {page_data['rotation']}°")
        print(f"   Content Blocks: {len(page_data['content_blocks'])}")
        print()
        
        # Analyze content blocks
        text_blocks = 0
        image_blocks = 0
        total_lines = 0
        total_spans = 0
        font_sizes = []
        font_names = set()
        
        print("📋 Content Block Analysis:")
        print("-" * 40)
        
        for i, block in enumerate(page_data['content_blocks']):
            block_type = "TEXT" if block['is_text'] else "IMAGE"
            print(f"Block {block['block_number']:2d} [{block_type:5s}]: {block['bbox']['width']:.1f}x{block['bbox']['height']:.1f} at ({block['bbox']['x0']:.1f}, {block['bbox']['y0']:.1f})")
            
            if block['is_text']:
                text_blocks += 1
                total_lines += len(block['lines'])
                
                # Show text preview
                text_preview = block['text'][:50] + "..." if len(block['text']) > 50 else block['text']
                text_preview = text_preview.replace('\n', ' ').strip()
                print(f"         Text: \"{text_preview}\"")
                
                # Analyze font information
                for line in block['lines']:
                    total_spans += len(line['spans'])
                    for span in line['spans']:
                        font_sizes.append(span['font']['size'])
                        font_names.add(span['font']['name'])
                        
                        # Show interesting spans (headers, bold text, etc.)
                        if span['font']['is_bold'] or span['font']['size'] > 14:
                            format_info = []
                            if span['font']['is_bold']:
                                format_info.append("BOLD")
                            if span['font']['is_italic']:
                                format_info.append("ITALIC")
                            format_str = f" [{', '.join(format_info)}]" if format_info else ""
                            
                            span_text = span['text'][:30] + "..." if len(span['text']) > 30 else span['text']
                            span_text = span_text.replace('\n', ' ').strip()
                            print(f"         → {span['font']['name']}, {span['font']['size']:.1f}pt{format_str}: \"{span_text}\"")
            else:
                image_blocks += 1
            
            print()
        
        # Display statistics
        print("📊 Page Statistics:")
        print("-" * 40)
        print(f"Text Blocks:     {text_blocks}")
        print(f"Image Blocks:    {image_blocks}")
        print(f"Total Lines:     {total_lines}")
        print(f"Total Spans:     {total_spans}")
        print(f"Unique Fonts:    {len(font_names)}")
        if font_sizes:
            print(f"Font Size Range: {min(font_sizes):.1f} - {max(font_sizes):.1f}pt")
            print(f"Average Font:    {sum(font_sizes)/len(font_sizes):.1f}pt")
        print()
        
        # Display font usage
        if font_names:
            print("🔤 Font Usage:")
            print("-" * 40)
            for font in sorted(font_names):
                print(f"   • {font}")
            print()
        
        # Show reading order analysis
        print("📖 Reading Order Analysis:")
        print("-" * 40)
        text_content_blocks = [b for b in page_data['content_blocks'] if b['is_text'] and b['text'].strip()]
        
        for i, block in enumerate(text_content_blocks[:5]):  # Show first 5 blocks
            text_preview = block['text'][:60] + "..." if len(block['text']) > 60 else block['text']
            text_preview = text_preview.replace('\n', ' ').strip()
            y_pos = block['bbox']['y0']
            print(f"   {i+1:2d}. (y={y_pos:.1f}) \"{text_preview}\"")
        
        if len(text_content_blocks) > 5:
            print(f"   ... and {len(text_content_blocks) - 5} more text blocks")
        
        print()
        print("✅ Task 3 Analysis Complete!")
        print(f"   Detailed content structure extracted with {total_spans} text spans")
        print(f"   Font information preserved for {len(font_names)} different fonts")
        print(f"   Spatial layout captured with precise bounding boxes")
        
    except Exception as e:
        print(f"❌ Error analyzing page structure: {e}")
        return False
    
    return True


def main():
    """Main demonstration function."""
    if len(sys.argv) < 2:
        print("Usage: python task3_demo.py <pdf_path> [page_number]")
        print("Example: python task3_demo.py 'document.pdf' 1")
        return
    
    pdf_path = sys.argv[1]
    page_number = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    if not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return
    
    analyze_page_structure(pdf_path, page_number)


if __name__ == "__main__":
    main()
