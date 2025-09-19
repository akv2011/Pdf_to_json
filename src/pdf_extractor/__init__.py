"""
PDF to JSON Structure Extractor

A comprehensive Python application that extracts content from PDF files 
and converts it into well-structured JSON format.
"""

__version__ = "1.0.0"
__author__ = "Development Team"
__email__ = "dev@example.com"

from .extractor import PDFStructureExtractor
from .models import ExtractionConfig
from .content_classifier import ContentClassifier
from .text_cleaner import TextCleaner

__all__ = ["PDFStructureExtractor", "ExtractionConfig", "ContentClassifier", "TextCleaner"]
