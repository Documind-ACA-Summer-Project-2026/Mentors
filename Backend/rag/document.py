from dataclasses import dataclass, field
from typing import Dict
import uuid

from pypdf import PdfReader


@dataclass
class Document:
    id: str
    text: str
    metadata: Dict = field(default_factory=dict)


class PDFLoader:

    def load(self, pdf_path: str) -> Document:

        reader = PdfReader(pdf_path)

        pages = []

        for page_num, page in enumerate(reader.pages):

            text = page.extract_text()

            if text:
                pages.append(text)

        full_text = "\n".join(pages)

        return Document(
            id=str(uuid.uuid4()),
            text=full_text,
            metadata={
                "filename": pdf_path,
                "pages": len(reader.pages)
            }
        )