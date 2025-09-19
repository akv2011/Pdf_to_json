"""
Text Processing and Cleaning Module

This module implements logic to clean extracted text by removing common PDF artifacts 
like page numbers, running headers/footers, and normalizing whitespace.
"""

import re
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict, Counter

from .models import PageContent, ContentBlock, TextSpan, BoundingBox


class TextArtifact:
    """Represents a detected text artifact (header/footer/page number)."""
    
    def __init__(self, text: str, bbox: BoundingBox, pages: Set[int]):
        self.text = text
        self.bbox = bbox
        self.pages = pages
        self.frequency = len(pages)
    
    def __repr__(self):
        return f"TextArtifact(text='{self.text[:20]}...', frequency={self.frequency})"


class TextCleaner:
    """Handles text cleaning and artifact removal from extracted PDF content."""
    
    def __init__(self, artifact_threshold: float = 0.5, position_tolerance: float = 5.0):
        """Initialize the text cleaner.
        
        Args:
            artifact_threshold: Minimum frequency (0.0-1.0) for a text block to be 
                               considered an artifact. Default 0.5 means text appearing 
                               on >50% of pages is flagged as artifact.
            position_tolerance: Maximum pixel difference for position matching
        """
        self.artifact_threshold = artifact_threshold
        self.position_tolerance = position_tolerance
        
        # Common ligature mappings for normalization
        self.ligature_map = {
            'ﬁ': 'fi',
            'ﬂ': 'fl',
            'ﬀ': 'ff',
            'ﬃ': 'ffi',
            'ﬄ': 'ffl',
            'ﬆ': 'st',
            'œ': 'oe',
            'æ': 'ae',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '–': '-',
            '—': '--',
            '…': '...',
        }
        
        # Regex patterns for common PDF artifacts
        self.page_number_patterns = [
            r'^\s*\d+\s*$',  # Simple page numbers
            r'^\s*Page\s+\d+\s*$',  # "Page N"
            r'^\s*\d+\s*/\s*\d+\s*$',  # "N/M" format
            r'^\s*-\s*\d+\s*-\s*$',  # "-N-" format
        ]
        
        # Patterns for detecting headers/footers content
        self.artifact_patterns = [
            r'^[A-Z\s]{10,}$',  # ALL CAPS headers (at least 10 chars)
            r'^\d{1,2}/\d{1,2}/\d{2,4}$',  # Dates
            r'^www\.',  # URLs
            r'@',  # Email addresses
            r'©',  # Copyright symbols
        ]
    
    def clean_pages(self, pages: List[PageContent]) -> List[PageContent]:
        """Clean all pages by removing artifacts and normalizing text.
        
        Args:
            pages: List of PageContent objects to clean
            
        Returns:
            List of cleaned PageContent objects
        """
        if not pages:
            return pages
        
        # Step 1: Detect artifacts across all pages
        artifacts = self._detect_artifacts(pages)
        
        # Step 2: Clean each page
        cleaned_pages = []
        for page in pages:
            cleaned_page = self._clean_page(page, artifacts)
            cleaned_pages.append(cleaned_page)
        
        return cleaned_pages
    
    def _detect_artifacts(self, pages: List[PageContent]) -> List[TextArtifact]:
        """Detect recurring text artifacts across multiple pages.
        
        Args:
            pages: List of PageContent objects to analyze
            
        Returns:
            List of detected TextArtifact objects
        """
        # Group similar text blocks by position and content
        position_groups = defaultdict(list)  # position_key -> [(text, page_num, bbox)]
        text_frequency = Counter()  # text -> count
        
        total_pages = len(pages)
        artifact_threshold_count = max(1, int(total_pages * self.artifact_threshold))
        
        for page in pages:
            page_texts = self._extract_page_texts(page)
            
            for text, bbox in page_texts:
                # Skip empty or very short text
                if len(text.strip()) < 2:
                    continue
                
                # Create position key for grouping
                pos_key = self._get_position_key(bbox)
                position_groups[pos_key].append((text, page.page_number, bbox))
                text_frequency[text.strip()] += 1
        
        # Identify artifacts
        artifacts = []
        
        # Method 1: Text appearing frequently across pages
        for text, count in text_frequency.items():
            if count >= artifact_threshold_count:
                # Find all pages and positions for this text
                pages_with_text = set()
                representative_bbox = None
                
                for pos_key, entries in position_groups.items():
                    for entry_text, page_num, bbox in entries:
                        if entry_text.strip() == text:
                            pages_with_text.add(page_num)
                            if representative_bbox is None:
                                representative_bbox = bbox
                
                if self._is_likely_artifact(text):
                    artifact = TextArtifact(text, representative_bbox, pages_with_text)
                    artifacts.append(artifact)
        
        # Method 2: Text in consistent positions (headers/footers)
        for pos_key, entries in position_groups.items():
            if len(entries) >= artifact_threshold_count:
                # Check if these are in header/footer positions
                sample_bbox = entries[0][2]
                if self._is_header_footer_position(sample_bbox, pages[0]):
                    # Group by text content
                    text_groups = defaultdict(list)
                    for text, page_num, bbox in entries:
                        text_groups[text.strip()].append((page_num, bbox))
                    
                    for text, page_entries in text_groups.items():
                        if len(page_entries) >= artifact_threshold_count:
                            pages_set = {page_num for page_num, _ in page_entries}
                            artifact = TextArtifact(text, page_entries[0][1], pages_set)
                            artifacts.append(artifact)
        
        return artifacts
    
    def _extract_page_texts(self, page: PageContent) -> List[Tuple[str, BoundingBox]]:
        """Extract all text strings and their bounding boxes from a page.
        
        Args:
            page: PageContent object to extract from
            
        Returns:
            List of (text, bbox) tuples
        """
        texts = []
        
        # Extract from content blocks
        for block in page.content_blocks:
            if block.is_text_block and block.text.strip():
                texts.append((block.text.strip(), block.bbox))
        
        # Also extract from individual spans for more granular detection
        for block in page.content_blocks:
            for line in block.lines:
                for span in line.spans:
                    if span.text.strip():
                        texts.append((span.text.strip(), span.bbox))
        
        return texts
    
    def _get_position_key(self, bbox: BoundingBox) -> str:
        """Create a position key for grouping similar positions.
        
        Args:
            bbox: BoundingBox to create key for
            
        Returns:
            String key representing the position
        """
        # Round coordinates to tolerance level
        x0 = round(bbox.x0 / self.position_tolerance) * self.position_tolerance
        y0 = round(bbox.y0 / self.position_tolerance) * self.position_tolerance
        return f"{x0:.1f},{y0:.1f}"
    
    def _is_likely_artifact(self, text: str) -> bool:
        """Check if text content is likely to be an artifact.
        
        Args:
            text: Text content to check
            
        Returns:
            True if likely artifact, False otherwise
        """
        text = text.strip()
        
        # Check against page number patterns
        for pattern in self.page_number_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        # Check against artifact patterns
        for i, pattern in enumerate(self.artifact_patterns):
            # Special handling for ALL CAPS pattern (don't use IGNORECASE)
            if i == 0:  # ALL CAPS pattern
                if re.search(pattern, text):
                    return True
            else:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
        
        # Check for very short repeated text
        if len(text) <= 3 and not text.isalpha():
            return True
        
        # Check for all numbers or symbols
        if re.match(r'^[\d\s\-\./]+$', text):
            return True
        
        return False
    
    def _is_header_footer_position(self, bbox: BoundingBox, sample_page: PageContent) -> bool:
        """Check if a bounding box is in a typical header or footer position.
        
        Args:
            bbox: BoundingBox to check
            sample_page: Sample page for page dimensions
            
        Returns:
            True if in header/footer position, False otherwise
        """
        page_height = sample_page.page_height
        header_threshold = page_height * 0.1  # Top 10%
        footer_threshold = page_height * 0.9   # Bottom 10%
        
        return bbox.y0 < header_threshold or bbox.y0 > footer_threshold
    
    def _clean_page(self, page: PageContent, artifacts: List[TextArtifact]) -> PageContent:
        """Clean a single page by removing artifacts and normalizing text.
        
        Args:
            page: PageContent object to clean
            artifacts: List of detected artifacts to remove
            
        Returns:
            Cleaned PageContent object
        """
        # Create a copy of the page to avoid modifying the original
        cleaned_page = PageContent(
            page_number=page.page_number,
            page_width=page.page_width,
            page_height=page.page_height,
            rotation=page.rotation
        )
        
        # Track artifact texts to remove
        artifact_texts = {artifact.text for artifact in artifacts 
                         if page.page_number in artifact.pages}
        
        # Process content blocks
        for block in page.content_blocks:
            if not block.is_text_block:
                # Keep non-text blocks as-is
                cleaned_page.content_blocks.append(block)
                continue
            
            # Check if this block is an artifact
            if block.text.strip() in artifact_texts:
                continue  # Skip artifacts
            
            # Clean the text content
            cleaned_text = self.normalize_text(block.text)
            
            # Only keep blocks with meaningful content
            if cleaned_text.strip():
                # Create cleaned block
                cleaned_block = ContentBlock(
                    block_number=block.block_number,
                    block_type=block.block_type,
                    bbox=block.bbox,
                    lines=self._clean_text_lines(block.lines)
                )
                cleaned_page.content_blocks.append(cleaned_block)
        
        # Also clean legacy text blocks if they exist
        for text_block in page.text_blocks:
            if text_block.text.strip() not in artifact_texts:
                cleaned_text = self.normalize_text(text_block.text)
                if cleaned_text.strip():
                    from .models import TextBlock
                    cleaned_block = TextBlock(
                        text=cleaned_text,
                        content_type=text_block.content_type,
                        bbox=text_block.bbox,
                        confidence=text_block.confidence
                    )
                    cleaned_page.text_blocks.append(cleaned_block)
        
        return cleaned_page
    
    def _clean_text_lines(self, text_lines: List) -> List:
        """Clean text lines by normalizing spans.
        
        Args:
            text_lines: List of TextLine objects
            
        Returns:
            List of cleaned TextLine objects
        """
        from .models import TextLine, TextSpan
        
        cleaned_lines = []
        for line in text_lines:
            cleaned_spans = []
            for span in line.spans:
                cleaned_text = self.normalize_text(span.text)
                if cleaned_text.strip():  # Only keep spans with content
                    cleaned_span = TextSpan(
                        text=cleaned_text,
                        bbox=span.bbox,
                        font_info=span.font_info,
                        origin=span.origin
                    )
                    cleaned_spans.append(cleaned_span)
            
            if cleaned_spans:  # Only keep lines with spans
                cleaned_line = TextLine(
                    spans=cleaned_spans,
                    bbox=line.bbox,
                    wmode=line.wmode,
                    direction=line.direction
                )
                cleaned_lines.append(cleaned_line)
        
        return cleaned_lines
    
    def normalize_text(self, text: str) -> str:
        """Normalize text by fixing ligatures, whitespace, and encoding issues.
        
        Args:
            text: Raw text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return text
        
        # Step 1: Fix ligatures
        normalized = text
        for ligature, replacement in self.ligature_map.items():
            normalized = normalized.replace(ligature, replacement)
        
        # Step 2: Normalize line endings first
        normalized = re.sub(r'\r\n|\r', '\n', normalized)
        
        # Step 3: Process lines individually to preserve indentation
        lines = normalized.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Only trim trailing spaces, preserve leading spaces for indentation
            cleaned_line = line.rstrip()
            # Only collapse multiple spaces within the line content (not leading)
            if cleaned_line.lstrip():  # If line has content
                leading_spaces = len(cleaned_line) - len(cleaned_line.lstrip())
                content = cleaned_line.lstrip()
                # Collapse multiple spaces within content
                content = re.sub(r' +', ' ', content)
                cleaned_line = ' ' * leading_spaces + content
            cleaned_lines.append(cleaned_line)
        
        # Step 4: Remove excessive blank lines (more than 2 consecutive)
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        # Step 5: Replace tabs with spaces
        result = result.replace('\t', ' ')
        
        return result
    
    def remove_page_numbers(self, text: str) -> str:
        """Remove standalone page numbers from text.
        
        Args:
            text: Text to clean
            
        Returns:
            Text with page numbers removed
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            is_page_number = False
            
            # Check against page number patterns
            for pattern in self.page_number_patterns:
                if re.match(pattern, stripped, re.IGNORECASE):
                    is_page_number = True
                    break
            
            if not is_page_number:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def get_artifact_report(self, pages: List[PageContent]) -> Dict[str, Any]:
        """Generate a report of detected artifacts for analysis.
        
        Args:
            pages: List of PageContent objects to analyze
            
        Returns:
            Dictionary containing artifact analysis report
        """
        artifacts = self._detect_artifacts(pages)
        
        report = {
            'total_pages': len(pages),
            'artifacts_detected': len(artifacts),
            'artifact_threshold': self.artifact_threshold,
            'artifacts': []
        }
        
        for artifact in artifacts:
            artifact_info = {
                'text': artifact.text,
                'frequency': artifact.frequency,
                'pages': sorted(list(artifact.pages)),
                'coverage_percentage': (artifact.frequency / len(pages)) * 100,
                'bbox': {
                    'x0': artifact.bbox.x0,
                    'y0': artifact.bbox.y0,
                    'x1': artifact.bbox.x1,
                    'y1': artifact.bbox.y1
                }
            }
            report['artifacts'].append(artifact_info)
        
        # Sort by frequency (most common first)
        report['artifacts'].sort(key=lambda x: x['frequency'], reverse=True)
        
        return report