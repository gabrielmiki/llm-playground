import os
from pypdf import PdfReader

PDF_DIR = "."
OUTPUT_DIR = "docs/plan"


def extract_pdfs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for filename in os.listdir(PDF_DIR):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(PDF_DIR, filename)
            txt_filename = filename[:-4] + ".txt"
            txt_path = os.path.join(OUTPUT_DIR, txt_filename)

            reader = PdfReader(pdf_path)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            full_text = "\n".join(text_parts)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(full_text)

            print(f"Extracted: {filename} -> {txt_filename}")


if __name__ == "__main__":
    extract_pdfs()
