import base64
from typing import List, Dict, Any, Optional, Tuple
import fitz
import logging

from .models import (
    ImageInfo, BoundingBox, TextBlock, ContentType, FontInfo
)


class ChartExtractor:
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(__name__)
    
    def extract_images_from_page(
        self, 
        page: fitz.Page, 
        page_number: int,
        text_blocks: List[TextBlock] = None
    ) -> List[ImageInfo]:
        images = []
        

        image_list = page.get_images(full=True)
        
        if self.debug:
            self.logger.debug(f"Found {len(image_list)} images on page {page_number}")
        
        for img_index, img in enumerate(image_list):
            try:

                image_info = self._extract_image_metadata(
                    page, img, page_number, img_index
                )
                if text_blocks and image_info.bbox:
                    caption = self._find_image_caption(image_info.bbox, text_blocks)
                    if caption:
                        image_info.description = caption
                
                images.append(image_info)
                
            except Exception as e:
                self.logger.warning(
                    f"Failed to extract image {img_index} on page {page_number}: {e}"
                )
                continue
        
        return images
    
    def _extract_image_metadata(
        self, 
        page: fitz.Page, 
        img: tuple, 
        page_number: int, 
        img_index: int
    ) -> ImageInfo:

        xref = img[0]
        smask = img[1] 
        width = img[2]
        height = img[3]
        bpc = img[4]
        colorspace = img[5]
        alt_colorspace = img[6]
        name = img[7]
        img_filter = img[8]

        image_id = f"page_{page_number}_img_{img_index}_{xref}"
        
        bbox = self._get_image_bbox(page, xref)

        img_format, size_bytes = self._get_image_format_and_size(page.parent, xref)

        metadata = {
            "xref": xref,
            "smask": smask,
            "bpc": bpc,
            "colorspace": colorspace,
            "alt_colorspace": alt_colorspace,
            "name": name,
            "filter": img_filter,
            "page_number": page_number,
            "index_on_page": img_index
        }
        
        if self.debug:
            metadata["debug_info"] = {
                "raw_image_tuple": img,
                "extraction_method": "pymupdf_get_images"
            }
        
        return ImageInfo(
            image_id=image_id,
            bbox=bbox,
            width=width,
            height=height,
            format=img_format,
            size_bytes=size_bytes,
            description=None, 
        )
    
    def _get_image_bbox(self, page: fitz.Page, xref: int) -> Optional[BoundingBox]:
        try:
            img_rects = page.get_image_rects(xref)
            
            if img_rects:

                rect = img_rects[0]
                return BoundingBox(
                    x0=rect.x0,
                    y0=rect.y0,
                    x1=rect.x1,
                    y1=rect.y1
                )
        except Exception as e:
            self.logger.warning(f"Failed to get bbox for image xref {xref}: {e}")
        
        return None
    
    def _get_image_format_and_size(
        self, 
        doc: fitz.Document, 
        xref: int
    ) -> Tuple[Optional[str], Optional[int]]:
        try:

            img_data = doc.extract_image(xref)
            
            if img_data:
                return img_data.get("ext"), len(img_data.get("image", b""))
                
        except Exception as e:
            self.logger.warning(f"Failed to get format/size for image xref {xref}: {e}")
        
        return None, None
    
    def _find_image_caption(
        self, 
        image_bbox: BoundingBox, 
        text_blocks: List[TextBlock]
    ) -> Optional[str]:
        candidate_captions = []
        
        search_margin = 50 
        max_caption_length = 500  
        
        search_y_min = image_bbox.y1 
        search_y_max = image_bbox.y1 + search_margin
        
        for block in text_blocks:
            if not block.bbox or not block.text.strip():
                continue
            
            block_y_center = (block.bbox.y0 + block.bbox.y1) / 2
            
            if (search_y_min <= block_y_center <= search_y_max and
                len(block.text.strip()) <= max_caption_length):
                

                caption_score = self._calculate_caption_score(
                    block, image_bbox, text_blocks
                )
                
                if caption_score > 0:
                    candidate_captions.append((block.text.strip(), caption_score))
        

        if candidate_captions:
            candidate_captions.sort(key=lambda x: x[1], reverse=True)
            return candidate_captions[0][0]
        
        return None
    
    def _calculate_caption_score(
        self, 
        text_block: TextBlock, 
        image_bbox: BoundingBox,
        all_text_blocks: List[TextBlock]
    ) -> float:

        score = 0.0
        text = text_block.text.strip()
        

        if len(text) < 3:
            return 0.0
        

        

        caption_prefixes = [
            "figure", "fig.", "chart", "graph", "image", "table", "tab.",
            "diagram", "illustration", "photo", "picture"
        ]
        
        if any(text.lower().startswith(prefix) for prefix in caption_prefixes):
            score += 2.0
        
        if any(char.isdigit() for char in text[:20]):
            score += 1.0
        

        if text.endswith('.'):
            score += 0.5
        

        if 10 <= len(text) <= 200:
            score += 1.0
        elif 5 <= len(text) < 10:
            score += 0.5
        

        if text_block.font_info:
            font_data = text_block.font_info
            

            if isinstance(font_data, dict):
                if font_data.get('is_italic', False):
                    score += 1.5
                

                font_size = font_data.get('font_size', 0)
                if font_size > 0:

                    avg_font_size = self._get_average_font_size(all_text_blocks)
                    if avg_font_size > 0 and font_size < avg_font_size * 0.9:
                        score += 1.0
        

        if text_block.bbox:
            text_center_x = (text_block.bbox.x0 + text_block.bbox.x1) / 2
            image_center_x = (image_bbox.x0 + image_bbox.x1) / 2
            
            x_offset = abs(text_center_x - image_center_x)
            image_width = image_bbox.width or 1
            

            if x_offset < image_width * 0.25:
                score += 1.0
        

        

        if len(text) > 300:
            score -= 1.0
        

        non_caption_indicators = [
            "continued on next page", "see page", "http://", "www.",
            "email", "@", "copyright", "©"
        ]
        
        if any(indicator in text.lower() for indicator in non_caption_indicators):
            score -= 2.0
        
        return max(0.0, score)
    
    def _get_average_font_size(self, text_blocks: List[TextBlock]) -> float:
        
        font_sizes = []
        
        for block in text_blocks:
            if block.font_info and isinstance(block.font_info, dict):
                font_size = block.font_info.get('font_size')
                if font_size and font_size > 0:
                    font_sizes.append(font_size)
        
        return sum(font_sizes) / len(font_sizes) if font_sizes else 0.0
    
    def extract_image_data(
        self, 
        doc: fitz.Document, 
        image_info: ImageInfo,
        as_base64: bool = False
    ) -> Optional[bytes]:
        try:

            xref = None
            

            if '_' in image_info.image_id:
                parts = image_info.image_id.split('_')
                if len(parts) >= 4:
                    try:
                        xref = int(parts[-1])
                    except ValueError:
                        pass
            
            if xref is None:
                self.logger.warning(f"Could not determine xref for image {image_info.image_id}")
                return None
            

            img_data = doc.extract_image(xref)
            
            if img_data and 'image' in img_data:
                raw_data = img_data['image']
                
                if as_base64:
                    return base64.b64encode(raw_data).decode('utf-8')
                else:
                    return raw_data
                    
        except Exception as e:
            self.logger.error(f"Failed to extract image data for {image_info.image_id}: {e}")
        
        return None