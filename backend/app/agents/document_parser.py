from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


def parse_document(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
    elif suffix == ".pdf":
        reader = PdfReader(str(path))
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix == ".docx":
        doc = DocxDocument(str(path))
        raw_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    else:
        raw_text = path.read_text(encoding="utf-8", errors="ignore")

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    parsed_json = {
        "file_name": path.name,
        "file_type": suffix.replace(".", "") or "unknown",
        "line_count": len(lines),
        "keywords": _extract_keywords(raw_text),
        "preview": raw_text[:500],
    }
    return {"raw_text": raw_text, "parsed_json": parsed_json}


def _extract_keywords(text: str) -> list[str]:
    candidates = ["劳动合同", "工资", "加班", "解除", "微信", "考勤", "赔偿金", "劳动关系", "仲裁"]
    return [item for item in candidates if item in text]
