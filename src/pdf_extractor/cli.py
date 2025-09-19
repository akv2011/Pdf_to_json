import click
from pathlib import Path
import json
import sys
from typing import Optional

from .extractor import PDFStructureExtractor
from .models import ExtractionConfig
from .json_builder import JSONBuilder
from .config import load_config_for_cli
from .logging_utils import configure_logging, get_logger


@click.group()
@click.version_option(version="1.0.0")
def cli():
    pass


@cli.command()
@click.option('--input', '-i', 'input_path', type=click.Path(exists=True, path_type=Path), 
              required=True, help='Input PDF file to process')
@click.option('--output', '-o', type=click.Path(path_type=Path), 
              help='Output JSON file path')
@click.option('--password', '-p', type=str, help='Password for encrypted PDF files')
@click.option('--mode', type=click.Choice(['standard', 'detailed', 'fast']), default='standard',
              help='Extraction mode')
@click.option('--format', type=click.Choice(['hierarchical', 'flat', 'raw']), default='hierarchical',
              help='Output format')
@click.option('--preserve-layout', is_flag=True, default=False, help='Preserve spatial layout')
@click.option('--extract-tables', is_flag=True, default=None, help='Extract tables')
@click.option('--extract-images', is_flag=True, default=None, help='Extract images')
@click.option('--validate-schema', is_flag=True, default=True, help='Validate output')
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path), help='Configuration file')
@click.option('--verbose', '-v', is_flag=True, default=False, help='Enable verbose output')
def extract(input_path: Path, output: Optional[Path], password: Optional[str], mode: str, 
           format: str, preserve_layout: bool, extract_tables: Optional[bool], 
           extract_images: Optional[bool], validate_schema: bool, 
           config: Optional[Path], verbose: bool):
    """Extract structure from a PDF file and save as JSON.
    
    This command processes PDF files and extracts their content in various structured formats.
    Use different modes for different levels of detail and processing speed.
    """
    # Configure logging based on verbosity level
    configure_logging(verbose=verbose, json_format=not verbose)  # Use JSON format unless verbose
    logger = get_logger('pdf_extractor.cli')
    
    if verbose:
        click.echo(f"Processing PDF: {input_path}")
        click.echo(f"Extraction mode: {mode}")
        click.echo(f"Output format: {format}")
    
    logger.info("CLI extraction started", extra={
        'extra_data': {
            'input_path': str(input_path),
            'mode': mode,
            'format': format,
            'verbose': verbose
        }
    })
    
    # Determine output path based on format
    if output is None:
        if format == 'hierarchical':
            output = input_path.with_suffix('').with_suffix('.structured.json')
        elif format == 'flat':
            output = input_path.with_suffix('').with_suffix('.flat.json')
        else:  # raw
            output = input_path.with_suffix('.json')
    
    if verbose:
        click.echo(f"Output will be saved to: {output}")
    
    try:
        # Load unified configuration with proper precedence
        extractor_config = load_config_for_cli(
            config_path=config,
            mode=mode,
            format=format,
            preserve_layout=preserve_layout,
            extract_tables=extract_tables,
            extract_images=extract_images,
            validate_schema=validate_schema,
            verbose=verbose,
            password=password,
            output_path=str(output) if output else None
        )
        
        if verbose:
            click.echo(f"Configuration loaded:")
            click.echo(f"  Mode: {extractor_config.mode}")
            click.echo(f"  Format: {extractor_config.format}")
            click.echo(f"  Table extraction: {extractor_config.get_effective_table_extraction()}")
            click.echo(f"  Image extraction: {extractor_config.get_effective_image_extraction()}")
            click.echo(f"  Layout preservation: {extractor_config.get_effective_layout_preservation()}")
            if extractor_config.password:
                click.echo(f"  Password: {'*' * len(extractor_config.password)}")
        
        # Create extraction configuration for the extractor
        extraction_config = ExtractionConfig(
            preserve_layout=extractor_config.get_effective_layout_preservation(),
            extract_tables=extractor_config.get_effective_table_extraction(),
            extract_images=extractor_config.get_effective_image_extraction(),
            verbose=extractor_config.verbose
        )
        
        # Initialize extractor
        extractor = PDFStructureExtractor(config=extraction_config)
        
        # Handle password-protected PDFs
        if extractor_config.password:
            if verbose:
                click.echo("Using provided password for PDF decryption")
            # Note: Password handling will be implemented in the extractor
            # For now, we'll pass it as part of the extraction call
        
        # Extract content
        if verbose:
            click.echo("Starting extraction...")
        
        try:
            result = extractor.extract(input_path)
        except Exception as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                if not extractor_config.password:
                    click.echo("❌ PDF appears to be password-protected. Use --password option.", err=True)
                else:
                    click.echo(f"❌ Invalid password or encryption error: {e}", err=True)
                sys.exit(1)
            else:
                raise  # Re-raise non-password related exceptions
        
        # Process output based on format
        if extractor_config.format == 'hierarchical':
            # Use structured JSON with schema validation
            if verbose:
                click.echo("Converting to hierarchical structured format...")
            
            builder = JSONBuilder(validate_schema=extractor_config.validate_schema, indent=2)
            
            # Convert to ExtractionResult object (as done before)
            from .models import ExtractionResult, PageContent, TextBlock, ContentType, BoundingBox, ImageInfo
            
            pages = []
            for page_data in result.get('pages', []):
                page = PageContent(
                    page_number=page_data['page_number'],
                    page_width=page_data.get('page_width'),
                    page_height=page_data.get('page_height'),
                    rotation=page_data.get('rotation', 0)
                )
                
                # Add text blocks
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
                file_path=str(input_path),
                pages=pages,
                metadata=result.get('metadata', {}),
                processing_time=result.get('processing_time'),
                errors=result.get('errors', []),
                warnings=result.get('warnings', [])
            )
            
            # Build structured JSON
            structured_result = builder.build_from_extraction_result(extraction_obj, extraction_config)
            
            # Save structured JSON
            builder.save_to_file(structured_result, output)
            
        elif extractor_config.format == 'flat':
            # Create a simplified, flat JSON structure
            if verbose:
                click.echo("Converting to flat JSON format...")
            
            flat_result = {
                "file_path": str(input_path),
                "extraction_mode": extractor_config.mode,
                "page_count": len(result.get('pages', [])),
                "processing_time": result.get('processing_time', 0),
                "content": []
            }
            
            # Flatten all content into a simple list
            for page_data in result.get('pages', []):
                page_number = page_data['page_number']
                
                # Add text content
                for block_data in page_data.get('content_blocks', []):
                    if block_data.get('is_text', False) and block_data.get('text', '').strip():
                        flat_result["content"].append({
                            "type": "text",
                            "page": page_number,
                            "content": block_data['text'],
                            "bbox": block_data.get('bbox')
                        })
                
                # Add images
                for img_data in page_data.get('images', []):
                    flat_result["content"].append({
                        "type": "image",
                        "page": page_number,
                        "image_id": img_data['image_id'],
                        "description": img_data.get('description'),
                        "bbox": img_data.get('bbox')
                    })
            
            # Save flat JSON
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(flat_result, f, indent=2, ensure_ascii=False)
            
        else:  # raw format
            # Save raw extraction result
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        
        click.echo(f"✅ Extraction complete! Saved to: {output}")
        
        # Log successful completion
        pages = len(result.get('pages', []))
        processing_time = result.get('processing_time', 0)
        logger.info("CLI extraction completed successfully", extra={
            'extra_data': {
                'input_path': str(input_path),
                'output_path': str(output),
                'pages_processed': pages,
                'processing_time_seconds': processing_time,
                'format': format,
                'mode': mode
            }
        })
        
        # Show summary
        if verbose:
            click.echo(f"📄 Processed {pages} pages in {processing_time:.2f}s")
            
            if extractor_config.format == 'hierarchical':
                # Show structured format summary
                try:
                    with open(output, 'r', encoding='utf-8') as f:
                        structured_data = json.load(f)
                    
                    doc = structured_data.get('document', {})
                    summary = doc.get('summary', {})
                    
                    click.echo("📊 Structured content summary:")
                    click.echo(f"   Document title: {doc.get('title', 'None')}")
                    click.echo(f"   Total sections: {summary.get('total_sections', 0)}")
                    click.echo(f"   Content types: {summary.get('content_types', {})}")
                    
                except Exception as e:
                    if verbose:
                        click.echo(f"⚠ Could not read structured summary: {e}")
            
            if extractor_config.validate_schema and extractor_config.format == 'hierarchical':
                click.echo("✅ Schema validation enabled")
            
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', type=click.Path(path_type=Path), default=Path("config.yaml"),
              help='Output path for configuration file (default: config.yaml)')
def init_config(output: Path):
    """Generate an example configuration file.
    
    Creates a sample config.yaml file with all available options and their defaults.
    This file can be customized and used with the --config option.
    """
    try:
        from .config import ConfigManager
        
        if output.exists():
            click.confirm(f"Configuration file '{output}' already exists. Overwrite?", abort=True)
        
        ConfigManager.save_example_config(output)
        click.echo(f"✅ Configuration file created: {output}")
        click.echo("\nYou can now:")
        click.echo(f"1. Edit {output} to customize default settings")
        click.echo(f"2. Use --config {output} with the extract command")
        click.echo("3. CLI options will override config file settings")
        
    except Exception as e:
        click.echo(f"❌ Error creating configuration file: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True, path_type=Path))
def info(pdf_path: Path):
    """Display information about a PDF file without extracting content."""
    try:
        config = ExtractionConfig(verbose=True)
        extractor = PDFStructureExtractor(config=config)
        
        info_data = extractor.get_pdf_info(pdf_path)
        
        click.echo("📋 PDF Information:")
        click.echo(f"  File: {pdf_path}")
        click.echo(f"  Pages: {info_data['page_count']}")
        click.echo(f"  File size: {info_data['file_size_mb']:.2f} MB")
        click.echo(f"  Password protected: {'Yes' if info_data['is_encrypted'] else 'No'}")
        
        if info_data.get('metadata'):
            click.echo("  Metadata:")
            for key, value in info_data['metadata'].items():
                if value:
                    click.echo(f"    {key}: {value}")
                    
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
