"""
Iterates through PDF files in the directory to extract artwork metadata.
"""

from pathlib import Path
import json
import re
import os
# Using the pymupdf import as per the latest documentation
import pymupdf
import base64
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

# Configuration
PDF_DIR = Path("src/state_db/art_pdf")
PDF_GLOB = "*.pdf"
OUTPUT_DIR = Path("src/state_db/art_json")
SAVE_IMAGES = True
IMAGE_OUTPUT_DIR = Path("src/state_db/art_images")

# Create output directories if they don't exist
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
if SAVE_IMAGES:
    IMAGE_OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


@dataclass
class Artwork:
    """Data structure to hold artwork information"""
    title: str = ""
    artist: str = ""
    year: str = ""
    dimensions: str = ""
    medium: str = ""
    price: Optional[str] = None
    image_path: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded image for JSON output
    page_number: int = 0
    confidence_score: float = 0.0  # How confident we are in the extraction


class PDFArtworkExtractor:
    """Extract artwork information from gallery PDFs"""
    
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.doc = pymupdf.open(pdf_path)
        self.artworks: List[Artwork] = []
        
        # Common patterns for artwork information
        self.year_pattern = re.compile(r'\b(19|20)\d{2}\b')
        self.dimensions_pattern = re.compile(r'\b\d+(\.\d+)?\s*[x×]\s*\d+(\.\d+)?(\s*[x×]\s*\d+(\.\d+)?)?\s*(cm|in|inches|mm)\b', re.IGNORECASE)
        self.price_pattern = re.compile(r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:USD|EUR|GBP)', re.IGNORECASE)
        
        # Common separators
        self.separators = [',', '|', '  ', '\n']
        
    def extract_all(self) -> List[Artwork]:
        """Process all pages in the PDF and extract artwork information"""
        for page_num, page in enumerate(self.doc):
            artworks = self.process_page(page, page_num)
            self.artworks.extend(artworks)
            
        return self.artworks
    
    def process_page(self, page, page_num: int) -> List[Artwork]:
        """Process a single page to extract artwork information"""
        # Skip pages that appear to be artist bio pages (typically have less images and more text)
        text = page.get_text()
        images = self.extract_images(page)
        
        # Skip pages that don't have images or have too much text
        if not images or len(text) > 2000 and len(images) < 2:
            print(f"Skipping page {page_num+1} - likely a bio page or text-only page")
            return []
            
        artworks = []
        # If there's only one main image on the page, it's likely a single artwork
        if len(images) == 1 or (len(images) > 0 and self.is_main_artwork_page(page, text)):
            artwork = self.extract_artwork_info(page, page_num, images[0] if images else None)
            if artwork:
                artworks.append(artwork)
        # If there are multiple images, try to associate each with nearby text
        elif len(images) > 1:
            # This is more complex and would require spatial analysis of the page
            # For now, we'll create a simple implementation that extracts what it can
            sections = self.split_page_into_sections(page, images)
            for section_text, image in sections:
                artwork = self.extract_artwork_info_from_text(section_text, page_num, image)
                if artwork:
                    artworks.append(artwork)
                    
        return artworks
    
    def is_main_artwork_page(self, page, text: str) -> bool:
        """Determine if a page is a main artwork page vs a bio or other page"""
        # Check for typical artwork information patterns
        has_dimensions = bool(self.dimensions_pattern.search(text))
        has_year = bool(self.year_pattern.search(text))
        has_price = bool(self.price_pattern.search(text))
        
        # A main artwork page likely has dimensions and a year
        return has_dimensions and has_year
    
    def extract_images(self, page) -> List[Dict[str, Any]]:
        """Extract images from a page"""
        images = []
        image_list = page.get_images(full=True)
        
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            base_image = self.doc.extract_image(xref)
            if base_image:
                image_data = {
                    "xref": xref,
                    "width": base_image["width"],
                    "height": base_image["height"],
                    "image_bytes": base_image["image"],
                    "extension": base_image["ext"]
                }
                
                # Only keep reasonably sized images (filter out icons, etc.)
                if image_data["width"] > 100 and image_data["height"] > 100:
                    images.append(image_data)
        
        # Sort by size, largest first (likely the artwork)
        images.sort(key=lambda x: x["width"] * x["height"], reverse=True)
        return images
    
    def split_page_into_sections(self, page, images) -> List[tuple]:
        """Split a page into sections based on image positions"""
        # This is a simplified approach - a more robust solution would require
        # analyzing the page layout more carefully
        page_text = page.get_text()
        if not images:
            return [(page_text, None)]
            
        # Simple case: just associate each image with the full page text
        # In a real implementation, you'd want to extract text regions near each image
        return [(page_text, image) for image in images[:1]]  # Just use the first/largest image for now
    
    def extract_artwork_info(self, page, page_num: int, image: Optional[Dict] = None) -> Optional[Artwork]:
        """Extract artwork information from a page"""
        text = page.get_text()
        return self.extract_artwork_info_from_text(text, page_num, image)
    
    def extract_artwork_info_from_text(self, text: str, page_num: int, image: Optional[Dict] = None) -> Optional[Artwork]:
        """Extract artwork information from text"""
        artwork = Artwork(page_number=page_num+1)
        
        # Try different strategies to parse the text
        if self.parse_artwork_linebreak_format(text, artwork) or self.parse_artwork_inline_format(text, artwork):
            # Process and save image if available
            if image and SAVE_IMAGES:
                img_ext = image["extension"]
                # Use a simpler filename format to avoid encoding issues
                img_filename = f"{self.pdf_path.stem}_page{page_num+1}_artwork{len(self.artworks)+1}.{img_ext}"
                img_filename = self.sanitize_filename(img_filename)
                img_path = IMAGE_OUTPUT_DIR / img_filename
                
                with open(img_path, "wb") as img_file:
                    img_file.write(image["image_bytes"])
                artwork.image_path = str(img_path)
                
                # Also encode as base64 for JSON output
                img_b64 = base64.b64encode(image["image_bytes"]).decode('utf-8')
                artwork.image_data = f"data:image/{img_ext};base64,{img_b64}"
            
            return artwork
        
        return None
    
    def parse_artwork_linebreak_format(self, text: str, artwork: Artwork) -> bool:
        """Parse text that has artwork info with line breaks between fields"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Find title and artist - usually the first few lines
        found_title = False
        found_artist = False
        
        # Try to identify title and artist from the first few lines
        for i, line in enumerate(lines[:5]):
            # Skip very short lines or lines that look like page numbers
            if len(line) < 3 or line.isdigit():
                continue
                
            # First substantial line is often the artist name
            if not found_artist and not self.is_likely_metadata(line):
                artwork.artist = line
                found_artist = True
                continue
                
            # Next substantial line is often the title
            if found_artist and not found_title and not self.is_likely_metadata(line):
                artwork.title = line
                found_title = True
                continue
                
            # If we found both, break
            if found_artist and found_title:
                break
        
        # Look for year, dimensions, medium in the remaining lines
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Extract year
            if not artwork.year:
                year_match = self.year_pattern.search(line)
                if year_match:
                    artwork.year = year_match.group(0)
            
            # Extract dimensions
            if not artwork.dimensions:
                dim_match = self.dimensions_pattern.search(line)
                if dim_match:
                    artwork.dimensions = dim_match.group(0)
            
            # Extract price
            if not artwork.price:
                price_match = self.price_pattern.search(line)
                if price_match:
                    artwork.price = price_match.group(0)
            
            # Medium is often a line that doesn't match the other patterns
            # and contains materials like "oil on canvas", "acrylic", etc.
            if not artwork.medium and not self.is_likely_metadata(line) and len(line) > 5:
                if not self.year_pattern.search(line) and not self.dimensions_pattern.search(line) and not self.price_pattern.search(line):
                    if line != artwork.artist and line != artwork.title:
                        artwork.medium = line
        
        # Calculate confidence score based on how many fields we found
        fields_found = sum(1 for f in [artwork.title, artwork.artist, artwork.year, 
                                       artwork.dimensions, artwork.medium] if f)
        artwork.confidence_score = fields_found / 5.0
        
        return artwork.confidence_score > 0.6  # Return True if we found at least 60% of fields
    
    def parse_artwork_inline_format(self, text: str, artwork: Artwork) -> bool:
        """Parse text that has artwork info in a single line with separators"""
        # Try different separators
        for separator in self.separators:
            parts = [p.strip() for p in text.split(separator) if p.strip()]
            
            # Need at least 3 parts for artist, title, and some metadata
            if len(parts) >= 3:
                # Assume first part is artist, second is title
                if not artwork.artist:
                    artwork.artist = parts[0]
                if not artwork.title:
                    artwork.title = parts[1]
                
                # Look for year, dimensions, medium in the remaining parts
                for part in parts[2:]:
                    # Extract year
                    if not artwork.year:
                        year_match = self.year_pattern.search(part)
                        if year_match:
                            artwork.year = year_match.group(0)
                    
                    # Extract dimensions
                    if not artwork.dimensions:
                        dim_match = self.dimensions_pattern.search(part)
                        if dim_match:
                            artwork.dimensions = dim_match.group(0)
                    
                    # Extract price
                    if not artwork.price:
                        price_match = self.price_pattern.search(part)
                        if price_match:
                            artwork.price = price_match.group(0)
                    
                    # Medium is often a part that doesn't match the other patterns
                    if not artwork.medium and not self.is_likely_metadata(part) and len(part) > 5:
                        if not self.year_pattern.search(part) and not self.dimensions_pattern.search(part) and not self.price_pattern.search(part):
                            artwork.medium = part
                
                # Calculate confidence score based on how many fields we found
                fields_found = sum(1 for f in [artwork.title, artwork.artist, artwork.year, 
                                             artwork.dimensions, artwork.medium] if f)
                artwork.confidence_score = fields_found / 5.0
                
                if artwork.confidence_score > 0.6:  # If we found at least 60% of fields
                    return True
        
        return False
    
    def is_likely_metadata(self, text: str) -> bool:
        """Check if a text line is likely metadata rather than artwork info"""
        metadata_indicators = ['page', 'copyright', '©', 'all rights', 'gallery', 
                              'contact', 'email', 'phone', 'website', 'www']
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in metadata_indicators)
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be filesystem safe"""
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Replace non-ASCII characters with underscore
        filename = ''.join(c if c.isascii() and c.isprintable() else '_' for c in filename)
        
        # Truncate if too long (max 200 chars)
        if len(filename) > 200:
            base, ext = os.path.splitext(filename)
            filename = base[:196] + ext
            
        return filename


def process_pdf_files():
    """Process all PDF files in the directory"""
    file_list = list(PDF_DIR.glob(PDF_GLOB))
    print(f"Found {len(file_list)} PDF files to process")
    
    all_artworks = []
    
    for file_path in file_list:
        print(f"\nProcessing {file_path.name}...")
        extractor = PDFArtworkExtractor(file_path)
        artworks = extractor.extract_all()
        
        print(f"  Extracted {len(artworks)} artworks")
        
        # Save as JSON
        output_file = OUTPUT_DIR / f"{file_path.stem}_artworks.json"
        with open(output_file, 'w') as f:
            # Convert dataclass objects to dictionaries
            artwork_dicts = [asdict(a) for a in artworks]
            # Remove binary image data if present to avoid giant JSON files
            for artwork in artwork_dicts:
                # Keep only the first 100 chars of image_data if present (for preview)
                if artwork['image_data'] and len(artwork['image_data']) > 100:
                    artwork['image_data'] = artwork['image_data'][:100] + '...'
            
            json.dump(artwork_dicts, f, indent=2)
        
        print(f"  Saved to {output_file}")
        all_artworks.extend(artworks)
    
    # Create a summary file with all artworks
    if all_artworks:
        summary_file = OUTPUT_DIR / "all_artworks.json"
        with open(summary_file, 'w') as f:
            artwork_dicts = [asdict(a) for a in all_artworks]
            # Remove binary image data to avoid giant JSON files
            for artwork in artwork_dicts:
                if artwork['image_data'] and len(artwork['image_data']) > 100:
                    artwork['image_data'] = artwork['image_data'][:100] + '...'
            
            json.dump(artwork_dicts, f, indent=2)
        
        print(f"\nSaved summary to {summary_file}")
    
    return all_artworks


if __name__ == "__main__":
    artworks = process_pdf_files()
    print(f"\nExtracted a total of {len(artworks)} artworks from all PDFs")
