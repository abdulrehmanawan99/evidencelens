"""Standalone resource-bounded parser. Invoked with -I -B and a secret-free environment."""
import json
import logging
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    memory_limit = resource.RLIMIT_DATA if sys.platform == "darwin" else resource.RLIMIT_AS
    resource.setrlimit(memory_limit, (512 * 1024 * 1024, 512 * 1024 * 1024))
    logging.disable(logging.CRITICAL)
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(sys.argv[1], strict=True)
        if reader.is_encrypted:
            raise ValueError("encrypted_pdf")
        if not 0 < len(reader.pages) <= int(sys.argv[2]):
            raise ValueError("pdf_page_limit")
        pages, warnings, characters = [], [], 0
        for number, page in enumerate(reader.pages, 1):
            content = page.get_contents()
            if content is not None and len(content.get_data()) > 8 * 1024 * 1024:
                raise ValueError("parser_decoded_limit")
            text = page.extract_text() or ""
            characters += len(text)
            if characters > int(sys.argv[3]):
                raise ValueError("text_limit")
            if not text.strip():
                warnings.append({"page": number, "code": "ocr_required", "message": "No extractable text on this page. Scans and image-only pages are not analyzed."})
            pages.append({"number": number, "text": text})
        if not any(page["text"].strip() for page in pages):
            raise ValueError("ocr_required")
        return {"pages": pages, "warnings": warnings, "extraction_version": "pypdf-text-v1"}
    except ValueError as exc:
        code = str(exc) if str(exc) in {"encrypted_pdf", "pdf_page_limit", "parser_decoded_limit", "text_limit", "ocr_required"} else "malformed_pdf"
        return {"error": code}
    except MemoryError:
        return {"error": "parser_memory_limit"}
    except (PdfReadError, Exception):
        return {"error": "malformed_pdf"}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
