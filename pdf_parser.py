from pypdf import PdfReader

def extract_pdf_text(source):
    reader = PdfReader(source)
    chunks = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()
