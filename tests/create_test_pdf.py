
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io


def create_simple_test_pdf(output_path):
    """Create a simple one-page PDF for testing."""
    c = canvas.Canvas(output_path, pagesize=letter)
    
    # Add some simple text content
    c.drawString(100, 750, "Test Document")
    c.drawString(100, 720, "This is a simple test PDF for MVP testing.")
    c.drawString(100, 690, "It contains basic text content.")
    c.drawString(100, 660, "Line 4 of test content.")
    
    # Add a simple table-like structure
    c.drawString(100, 600, "Name          Age     City")
    c.drawString(100, 580, "John Doe      25      New York")
    c.drawString(100, 560, "Jane Smith    30      Los Angeles")
    
    c.save()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Create test PDF
    test_pdf_path = Path(__file__).parent / "data" / "simple_test.pdf"
    test_pdf_path.parent.mkdir(exist_ok=True)
    
    try:
        create_simple_test_pdf(str(test_pdf_path))
        print(f"Created test PDF: {test_pdf_path}")
    except ImportError:
        print("  reportlab not available, creating minimal PDF manually")
        
        # Create a minimal PDF file manually
        minimal_pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""
        
        with open(test_pdf_path, 'wb') as f:
            f.write(minimal_pdf_content)
        
        print(f" Created minimal test PDF: {test_pdf_path}")