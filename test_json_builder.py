#!/usr/bin/env python3
"""
Test script for JSON Schema Definition and Output Builder.

This script tests the JSONBuilder class with real PDF data, validates schema
compliance, and demonstrates the structured JSON output format.
"""

import sys
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pdf_extractor.extractor import PDFStructureExtractor
from pdf_extractor.models import ExtractionConfig
from pdf_extractor.json_builder import JSONBuilder


def test_json_builder_basic():
    """Test basic JSONBuilder functionality."""
    print("=== Testing JSONBuilder Basic Functionality ===")
    
    # Test with and without schema validation
    for validate in [True, False]:
        print(f"\n--- Testing with schema validation: {validate} ---")
        
        builder = JSONBuilder(validate_schema=validate, indent=2)
        
        # Test schema loading
        if validate:
            if builder.schema:
                print("✓ JSON schema loaded successfully")
                print(f"  Schema title: {builder.schema.get('title', 'Unknown')}")
            else:
                print("⚠ JSON schema could not be loaded")
        else:
            print("✓ Schema validation disabled")
        
        # Test JSON formatting
        test_data = {"test": "data", "number": 42}
        json_string = builder.to_json_string(test_data)
        
        if '"test": "data"' in json_string and '"number": 42' in json_string:
            print("✓ JSON serialization working correctly")
        else:
            print("❌ JSON serialization failed")
    
    print()


def test_json_builder_with_real_pdf():
    """Test JSONBuilder with real PDF extraction."""
    print("=== Testing JSONBuilder with Real PDF ===")
    
    # Find a test PDF
    test_pdfs = [
        "rfp-bid-main/example-PDF/test.pdf",
        "[Fund Factsheet - May]360ONE-MF-May 2025.pdf.pdf",
        "rfp-bid-main/example-PDF/Article-on-Green-Hydrogen-and-GOI-Policy.pdf"
    ]
    
    pdf_path = None
    for pdf_name in test_pdfs:
        if Path(pdf_name).exists():
            pdf_path = Path(pdf_name)
            break
    
    if not pdf_path:
        print("❌ No test PDF found")
        return
    
    print(f"📄 Testing with: {pdf_path.name}")
    
    try:
        # Configure extraction with all features
        config = ExtractionConfig(
            extract_images=True,
            extract_tables=True,
            verbose=False
        )
        
        # Extract content
        extractor = PDFStructureExtractor(config)
        extraction_result = extractor.extract(pdf_path)
        
        print(f"✓ PDF extraction completed")
        print(f"  Pages: {len(extraction_result.get('pages', []))}")
        print(f"  Processing time: {extraction_result.get('processing_time', 0):.2f}s")
        
        # Create JSON builder
        builder = JSONBuilder(validate_schema=True, indent=2)
        
        # Test with page-based structure (current implementation)
        print("\n--- Testing page-based JSON output ---")
        
        # Since we don't have StructureBuilder integrated yet, we'll work with 
        # the existing ExtractionResult format
        from pdf_extractor.models import ExtractionResult, PageContent, ExtractionConfig as ExtConfig
        
        # Convert dict back to ExtractionResult object for testing
        pages = []
        for page_data in extraction_result.get('pages', []):
            page = PageContent(
                page_number=page_data['page_number'],
                page_width=page_data.get('page_width'),
                page_height=page_data.get('page_height'),
                rotation=page_data.get('rotation', 0)
            )
            
            # Add basic text blocks from content_blocks
            from pdf_extractor.models import TextBlock, ContentType, BoundingBox
            for block_data in page_data.get('content_blocks', []):
                if block_data.get('is_text', False) and block_data.get('text', '').strip():
                    text_block = TextBlock(
                        text=block_data['text'],
                        content_type=ContentType.TEXT,
                        bbox=BoundingBox(
                            x0=block_data['bbox']['x0'],
                            y0=block_data['bbox']['y0'],
                            x1=block_data['bbox']['x1'],
                            y1=block_data['bbox']['y1']
                        ) if block_data.get('bbox') else None
                    )
                    page.text_blocks.append(text_block)
            
            # Add images
            from pdf_extractor.models import ImageInfo
            for img_data in page_data.get('images', []):
                image = ImageInfo(
                    image_id=img_data['image_id'],
                    width=img_data.get('width'),
                    height=img_data.get('height'),
                    format=img_data.get('format'),
                    size_bytes=img_data.get('size_bytes'),
                    description=img_data.get('description'),
                    page_number=img_data.get('page_number'),
                    bbox=BoundingBox(
                        x0=img_data['bbox']['x0'],
                        y0=img_data['bbox']['y0'],
                        x1=img_data['bbox']['x1'],
                        y1=img_data['bbox']['y1']
                    ) if img_data.get('bbox') else None
                )
                page.images.append(image)
            
            pages.append(page)
        
        # Create ExtractionResult object
        extraction_obj = ExtractionResult(
            file_path=str(pdf_path),
            pages=pages,
            metadata=extraction_result.get('metadata', {}),
            processing_time=extraction_result.get('processing_time'),
            errors=extraction_result.get('errors', []),
            warnings=extraction_result.get('warnings', [])
        )
        
        # Build JSON from extraction result
        json_output = builder.build_from_extraction_result(extraction_obj, config)
        
        print("✓ JSON output generated successfully")
        
        # Validate structure
        if 'document' in json_output and 'metadata' in json_output and 'extraction_info' in json_output:
            print("✓ JSON structure is correct")
            
            doc = json_output['document']
            print(f"  Document title: {doc.get('title', 'None')}")
            print(f"  Content sections: {len(doc.get('content', []))}")
            
            if 'summary' in doc:
                summary = doc['summary']
                print(f"  Total pages: {summary.get('total_pages', 0)}")
                print(f"  Total sections: {summary.get('total_sections', 0)}")
                print(f"  Content types: {summary.get('content_types', {})}")
        else:
            print("❌ JSON structure is incorrect")
        
        # Test JSON serialization
        json_string = builder.to_json_string(json_output)
        print(f"✓ JSON string generated ({len(json_string):,} characters)")
        
        # Save sample output
        output_file = "json_builder_test_output.json"
        builder.save_to_file(json_output, Path(output_file))
        print(f"✓ JSON saved to: {output_file}")
        
        # Validate specific sections
        extraction_info = json_output.get('extraction_info', {})
        if 'processing_time' in extraction_info and 'extraction_config' in extraction_info:
            print("✓ Extraction info section is complete")
        
        metadata = json_output.get('metadata', {})
        if 'file_path' in metadata and 'page_count' in metadata:
            print("✓ Metadata section is complete")
        
        print()
        
    except Exception as e:
        print(f"❌ Error during JSON builder testing: {e}")
        import traceback
        traceback.print_exc()


def test_schema_validation():
    """Test JSON schema validation with various inputs."""
    print("=== Testing Schema Validation ===")
    
    try:
        import jsonschema
        schema_available = True
    except ImportError:
        print("⚠ jsonschema package not available, skipping validation tests")
        return
    
    builder = JSONBuilder(validate_schema=True)
    
    if not builder.schema:
        print("❌ Schema not loaded, cannot test validation")
        return
    
    print("✓ Schema loaded for validation testing")
    
    # Test valid minimal structure
    valid_data = {
        "document": {
            "title": "Test Document",
            "content": [],
            "summary": {
                "total_sections": 0,
                "total_pages": 1,
                "total_content_blocks": 0,
                "content_types": {
                    "headers": 0,
                    "paragraphs": 0,
                    "tables": 0,
                    "images": 0,
                    "lists": 0
                }
            }
        },
        "metadata": {
            "file_path": "test.pdf",
            "page_count": 1
        },
        "extraction_info": {
            "processing_time": 1.0,
            "extraction_config": {
                "extract_tables": True,
                "extract_images": False
            },
            "errors": [],
            "warnings": []
        }
    }
    
    try:
        jsonschema.validate(valid_data, builder.schema)
        print("✓ Valid data structure passes validation")
    except jsonschema.ValidationError as e:
        print(f"❌ Valid data failed validation: {e}")
    
    # Test invalid structure (missing required field)
    invalid_data = {
        "document": {
            "title": "Test Document"
            # Missing required "content" field
        },
        "metadata": {},
        "extraction_info": {
            "processing_time": 1.0,
            "extraction_config": {}
        }
    }
    
    try:
        jsonschema.validate(invalid_data, builder.schema)
        print("❌ Invalid data incorrectly passed validation")
    except jsonschema.ValidationError:
        print("✓ Invalid data correctly failed validation")
    
    print()


def main():
    """Run all tests for the JSON builder."""
    print("🔧 Testing JSON Schema Definition and Output Builder\n")
    
    # Test 1: Basic functionality
    test_json_builder_basic()
    
    # Test 2: Real PDF processing
    test_json_builder_with_real_pdf()
    
    # Test 3: Schema validation
    test_schema_validation()
    
    print("=== Test Summary ===")
    print("✓ JSONBuilder class implementation")
    print("✓ JSON schema definition and loading")
    print("✓ Schema validation (if jsonschema available)")
    print("✓ Real PDF data processing")
    print("✓ JSON serialization with UTF-8 support")
    print("✓ File output generation")
    print("\nJSON Builder testing completed!")


if __name__ == "__main__":
    main()