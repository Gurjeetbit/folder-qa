"""Read text out of common file types. Read-only: never writes to the source files."""
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".py", ".sql",
            ".yaml", ".yml", ".html", ".htm", ".xml", ".log", ".rtf", ".java", ".js", ".ts"}
DOC_EXT = {".pdf", ".docx", ".pptx", ".xlsx"}
SUPPORTED = TEXT_EXT | DOC_EXT


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            return path.read_text(errors="ignore")
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n\n".join(
                f"[page {i + 1}]\n{(page.extract_text() or '').strip()}"
                for i, page in enumerate(reader.pages)
            )
        if ext == ".docx":
            import docx
            d = docx.Document(str(path))
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            return "\n".join(parts)
        if ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(path))
            out = []
            for i, slide in enumerate(prs.slides, 1):
                texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
                out.append(f"[slide {i}]\n" + "\n".join(texts))
            return "\n\n".join(out)
        if ext == ".xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(str(path), read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                out.append(f"[sheet {ws.title}]")
                for row in ws.iter_rows(values_only=True, max_row=2000):
                    vals = [str(v) for v in row if v is not None]
                    if vals:
                        out.append(" | ".join(vals))
            return "\n".join(out)
    except Exception as exc:  # unreadable/corrupt/password-protected files are skipped
        return f""
    return ""


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Split on paragraph boundaries into ~size-character chunks with overlap."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}" if buf else p
            continue
        if buf:
            chunks.append(buf)
            buf = buf[-overlap:] + "\n\n" + p if overlap else p
        else:
            buf = p
        while len(buf) > size:  # very long paragraph: hard split
            chunks.append(buf[:size])
            buf = buf[size - overlap:]
    if buf.strip():
        chunks.append(buf)
    return chunks
