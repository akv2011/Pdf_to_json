"""
Command Line Interface for PDF Structure Extractor
"""

import click
from pathlib import Path
import json
import sys
from typing import Optional

from .extractor import PDFStructureExtractor
from .models import ExtractionConfig


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """PDF to JSON Structure Extractor
    
    Extract content from PDF files and convert to well-structured JSON format.
    """
    pass


@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True, path_type=Path))
@click.option('--output', '-o', type=click.Path(path_type=Path), 
              help='Output JSON file path (default: same name as PDF with .json extension)')
@click.option('--preserve-layout', is_flag=True, default=False,
              help='Preserve spatial layout information in output')
@click.option('--extract-tables', is_flag=True, default=True,
              help='Extract tables from PDF (default: enabled)')
@click.option('--extract-images', is_flag=True, default=False,
              help='Extract image metadata and descriptions (experimental)')
@click.option('--verbose', '-v', is_flag=True, default=False,
              help='Enable verbose output')
def extract(pdf_path: Path, output: Optional[Path], preserve_layout: bool, 
           extract_tables: bool, extract_images: bool, verbose: bool):
    """Extract structure from a PDF file and save as JSON.
    
    PDF_PATH: Path to the PDF file to extract from
    """
    if verbose:
        click.echo(f"Processing PDF: {pdf_path}")
    
    # Determine output path
    if output is None:
        output = pdf_path.with_suffix('.json')
    
    if verbose:
        click.echo(f"Output will be saved to: {output}")
    
    try:
        # Create extraction configuration
        config = ExtractionConfig(
            preserve_layout=preserve_layout,
            extract_tables=extract_tables,
            extract_images=extract_images,
            verbose=verbose
        )
        
        # Initialize extractor
        extractor = PDFStructureExtractor(config=config)
        
        # Extract content
        if verbose:
            click.echo("Starting extraction...")
        
        result = extractor.extract(pdf_path)
        
        # Save to JSON
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        click.echo(f"✅ Extraction complete! Saved to: {output}")
        
        # Show summary
        if verbose:
            pages = len(result.get('pages', []))
            click.echo(f"📄 Processed {pages} pages")
            
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
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
