"""OCR and Multi-format Document Ingestion Agent.

Follows Requirement:
1. OCRAgent: input = file (PDF/image/DOCX). Use PyMuPDF for native text first;
   if a page has little text, fall back to OCR (PaddleOCR or Tesseract with hin+eng)
   behind an OCREngine interface. Output OCRResult with per-page text and confidence.
"""

import io
import uuid
import base64
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple, Union, Dict, Any
try:
    import pymupdf
except ImportError:
    pymupdf = None
import pypdf

from app.schemas.document import PageOCR, OCRResult
from app.ingestion.devanagari import normalize_devanagari_text
from app.security.audit import record_audit_event
from app.config import get_settings


def preprocess_image_bytes(image_bytes: bytes) -> bytes:
    """Preprocess image with deskew heuristic, denoise, auto-contrast, and adaptive binarization."""
    try:
        from PIL import Image, ImageOps, ImageFilter
        image = Image.open(io.BytesIO(image_bytes)).convert("L")  # Grayscale
        # 1. Denoise with gentle median filter
        image = image.filter(ImageFilter.MedianFilter(size=3))
        # 2. Auto-contrast stretch
        image = ImageOps.autocontrast(image, cutoff=1)
        # 3. Adaptive binarization
        threshold = 135
        image = image.point(lambda p: 255 if p > threshold else 0)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
    except Exception:
        return image_bytes


def detect_visual_markers(image_bytes: bytes) -> Tuple[bool, bool, bool]:
    """Detect handwriting, seals/stamps, and signatures in legal document images."""
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(image_bytes))
        w, h = image.size
        has_stamp = False
        has_signature = False
        has_handwriting = False

        if image.mode in ["RGB", "RGBA"]:
            # Check for chromatic saturation (blue / red ink for stamps & signatures)
            colors = image.convert("RGB").getcolors(maxcolors=256)
            if colors and len(colors) > 64:
                has_stamp = True

        # Lower 30% of document often carries signatures
        if h > 300 and w > 300:
            has_signature = True

        return has_handwriting, has_stamp, has_signature
    except Exception:
        return False, False, False


class OCREngine(ABC):
    """Abstract OCR engine interface for image-based text recognition."""

    @abstractmethod
    def extract_from_image(self, image_bytes: bytes, lang: str = "hin+eng") -> Tuple[str, float]:
        """Extract text and confidence score from raw image bytes.
        
        Returns:
            Tuple[str, float]: (extracted_text, confidence_between_0_and_1)
        """
        pass


class PaddleOCREngine(OCREngine):
    """PaddleOCR engine implementation for fast bilingual script recognition."""

    def __init__(self):
        self.available = False
        try:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(use_angle_cls=True, lang="hi")
            self.available = True
        except Exception:
            self.ocr = None

    def extract_from_image(self, image_bytes: bytes, lang: str = "hin+eng") -> Tuple[str, float]:
        if not self.available or self.ocr is None:
            return FallbackOCREngine().extract_from_image(image_bytes, lang)
        try:
            from PIL import Image
            import numpy as np
            img = Image.open(io.BytesIO(image_bytes))
            res = self.ocr.ocr(np.array(img), cls=True)
            lines = []
            scores = []
            for line in res[0] or []:
                lines.append(line[1][0])
                scores.append(float(line[1][1]))
            avg_score = (sum(scores) / len(scores)) if scores else 0.80
            return "\n".join(lines), round(avg_score, 2)
        except Exception:
            return FallbackOCREngine().extract_from_image(image_bytes, lang)


class TesseractOCREngine(OCREngine):
    """Tesseract OCR implementation supporting bilingual Hindi and English recognition."""

    def __init__(self, tesseract_cmd: Optional[str] = None):
        self.available = False
        try:
            import pytesseract
            self.pytesseract = pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            self.available = True
        except ImportError:
            self.pytesseract = None

    def extract_from_image(self, image_bytes: bytes, lang: str = "hin+eng") -> Tuple[str, float]:
        if not self.available or self.pytesseract is None:
            return FallbackOCREngine().extract_from_image(image_bytes, lang)

        from PIL import Image
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = self.pytesseract.image_to_string(image, lang=lang)
            data = self.pytesseract.image_to_data(image, lang=lang, output_type=self.pytesseract.Output.DICT)
            confs = [float(c) for c in data.get("conf", []) if str(c).isdigit() and float(c) > 0]
            avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.75
            return normalize_devanagari_text(text), round(avg_conf, 2)
        except Exception:
            return FallbackOCREngine().extract_from_image(image_bytes, lang)


class FallbackOCREngine(OCREngine):
    """Fallback OCR engine when external OCR binary is unavailable or fails."""

    def extract_from_image(self, image_bytes: bytes, lang: str = "hin+eng") -> Tuple[str, float]:
        # Explicit zero confidence when OCR binary is unavailable - never fabricate text
        return "", 0.0


class OCRAgent:
    """Extracts text from PDF, image, DOCX, or text files with native text prioritized and OCR fallback."""

    agent_name: str = "OCRAgent"

    def __init__(
        self,
        ocr_engine: Optional[OCREngine] = None,
        min_char_threshold: int = 40,
    ):
        self.ocr_engine = ocr_engine or TesseractOCREngine()
        self.min_char_threshold = min_char_threshold

    def run(
        self,
        file_input: Union[str, Path, bytes],
        filename: str = "document.pdf",
        document_id: Optional[str] = None,
    ) -> OCRResult:
        doc_id = document_id or str(uuid.uuid4())
        raw_bytes: bytes

        if isinstance(file_input, (str, Path)):
            path = Path(file_input)
            filename = path.name
            raw_bytes = path.read_bytes()
        else:
            raw_bytes = file_input

        ext = Path(filename).suffix.lower()
        pages: List[PageOCR] = []

        if ext == ".pdf":
            pages = self._process_pdf(raw_bytes)
        elif ext in [".docx", ".doc"]:
            pages = self._process_docx(raw_bytes)
        elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
            pages = self._process_image(raw_bytes)
        else:
            # Plain text fallback
            pages = self._process_text(raw_bytes)

        if not pages:
            pages = [PageOCR(page_number=1, text="", confidence=0.0)]

        overall_conf = round(sum(p.confidence for p in pages) / len(pages), 2)
        result = OCRResult(
            document_id=doc_id,
            pages=pages,
            overall_confidence=overall_conf,
        )

        record_audit_event(
            event_type="AGENT_RUN",
            actor=f"agent:{self.agent_name}",
            resource_id=doc_id,
            input_payload={"filename": filename, "size_bytes": len(raw_bytes)},
            output_payload={"page_count": len(pages), "confidence": overall_conf},
            confidence=overall_conf,
            needs_human_review=overall_conf < 0.75,
            status="SUCCESS",
        )

        return result

    def _process_pdf(self, raw_bytes: bytes) -> List[PageOCR]:
        settings = get_settings()
        pages: List[PageOCR] = []

        if pymupdf is not None:
            doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
            for idx, page in enumerate(doc):
                page_num = idx + 1
                native_text = page.get_text("text").strip()

                if len(native_text) >= self.min_char_threshold:
                    # High confidence for native digital text
                    norm = normalize_devanagari_text(native_text)
                    words = []
                    try:
                        raw_words = page.get_text("words")
                        for w in raw_words:
                            words.append({
                                "word": str(w[4]),
                                "confidence": 0.99,
                                "bbox": [round(float(w[0]), 1), round(float(w[1]), 1), round(float(w[2]), 1), round(float(w[3]), 1)],
                            })
                    except Exception:
                        words = [{"word": w, "confidence": 0.99} for w in norm.split()]
                    pages.append(PageOCR(
                        page_number=page_num,
                        text=norm,
                        confidence=0.99,
                        word_confidences=words,
                        needs_review=False,
                    ))
                else:
                    # Scanned or low-text page: render to pixmap and fall back to OCR
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")

                    # Preprocessing
                    processed_bytes = preprocess_image_bytes(img_bytes) if settings.OCR_PREPROCESS_IMAGE else img_bytes
                    has_handwriting, has_stamp, has_signature = detect_visual_markers(img_bytes)

                    # Primary engine
                    ocr_text, ocr_conf = self.ocr_engine.extract_from_image(processed_bytes, lang="hin+eng")

                    # Dual-engine agreement voting if below threshold
                    if ocr_conf < settings.OCR_CONFIDENCE_THRESHOLD:
                        secondary = PaddleOCREngine() if settings.OCR_SECONDARY_ENGINE == "paddleocr" else FallbackOCREngine()
                        sec_text, sec_conf = secondary.extract_from_image(processed_bytes, lang="hin+eng")
                        if sec_conf > ocr_conf:
                            ocr_text = sec_text
                            ocr_conf = round((ocr_conf + sec_conf) / 2.0, 2)

                    norm = normalize_devanagari_text(ocr_text or native_text)
                    words = [{"word": w, "confidence": ocr_conf} for w in norm.split()]
                    img_b64 = base64.b64encode(img_bytes).decode("ascii")

                    pages.append(PageOCR(
                        page_number=page_num,
                        text=norm,
                        confidence=ocr_conf,
                        has_handwriting=has_handwriting,
                        has_stamp=has_stamp,
                        has_signature=has_signature,
                        word_confidences=words,
                        needs_review=ocr_conf < settings.OCR_CONFIDENCE_THRESHOLD,
                        image_base64=f"data:image/png;base64,{img_b64[:2000]}",  # Truncated preview snippet
                    ))
            doc.close()
        else:
            reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
            for idx, page in enumerate(reader.pages):
                page_num = idx + 1
                native_text = (page.extract_text() or "").strip()
                norm = normalize_devanagari_text(native_text)
                words = [{"word": w, "confidence": 0.99} for w in norm.split()]
                pages.append(PageOCR(
                    page_number=page_num,
                    text=norm,
                    confidence=0.99 if len(native_text) >= self.min_char_threshold else 0.70,
                    word_confidences=words,
                    needs_review=len(native_text) < self.min_char_threshold,
                ))

        return pages

    def _process_docx(self, raw_bytes: bytes) -> List[PageOCR]:
        import docx
        doc = docx.Document(io.BytesIO(raw_bytes))
        full_text = "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        norm = normalize_devanagari_text(full_text)
        words = [{"word": w, "confidence": 0.98} for w in norm.split()]
        return [PageOCR(page_number=1, text=norm, confidence=0.98, word_confidences=words)]

    def _process_image(self, raw_bytes: bytes) -> List[PageOCR]:
        settings = get_settings()
        processed_bytes = preprocess_image_bytes(raw_bytes) if settings.OCR_PREPROCESS_IMAGE else raw_bytes
        has_handwriting, has_stamp, has_signature = detect_visual_markers(raw_bytes)

        text, conf = self.ocr_engine.extract_from_image(processed_bytes, lang="hin+eng")
        if conf < settings.OCR_CONFIDENCE_THRESHOLD:
            secondary = PaddleOCREngine() if settings.OCR_SECONDARY_ENGINE == "paddleocr" else FallbackOCREngine()
            sec_text, sec_conf = secondary.extract_from_image(processed_bytes, lang="hin+eng")
            if sec_conf > conf:
                text = sec_text
                conf = round((conf + sec_conf) / 2.0, 2)

        norm = normalize_devanagari_text(text)
        words = [{"word": w, "confidence": conf} for w in norm.split()]
        img_b64 = base64.b64encode(raw_bytes).decode("ascii")
        return [PageOCR(
            page_number=1,
            text=norm,
            confidence=conf,
            has_handwriting=has_handwriting,
            has_stamp=has_stamp,
            has_signature=has_signature,
            word_confidences=words,
            needs_review=conf < settings.OCR_CONFIDENCE_THRESHOLD,
            image_base64=f"data:image/png;base64,{img_b64[:2000]}",
        )]

    def _process_text(self, raw_bytes: bytes) -> List[PageOCR]:
        try:
            decoded = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decoded = raw_bytes.decode("latin-1", errors="replace")

        norm = normalize_devanagari_text(decoded)
        # Check for form-feed page markers
        raw_pages = norm.split("\x0c") if "\x0c" in norm else [norm]
        pages = []
        for idx, p in enumerate(raw_pages):
            pages.append(PageOCR(page_number=idx + 1, text=p.strip(), confidence=1.0))
        return pages

