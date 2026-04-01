import asyncio
import io
from functools import partial

import pytesseract
from PIL import Image, ImageFilter, ImageOps

from app.core.logging import get_logger
from app.utils.exceptions import OCRError

logger = get_logger(__name__)

# Tesseract config: LSTM engine, auto page segmentation
_TESSERACT_CONFIG = "--oem 3 --psm 6"


class OCRService:
    """Extracts text from PDF and image files using Tesseract OCR."""

    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        """Return the full text extracted from the given file bytes."""
        try:
            if mime_type == "application/pdf":
                images = await self._pdf_to_images(file_bytes)
            else:
                images = [await self._bytes_to_image(file_bytes)]

            tasks = [self._ocr_image(img) for img in images]
            page_texts = await asyncio.gather(*tasks)
            return "\n\n".join(t for t in page_texts if t.strip())
        except OCRError:
            raise
        except Exception as exc:
            raise OCRError(f"OCR processing failed: {exc}") from exc

    async def _pdf_to_images(self, pdf_bytes: bytes) -> list[Image.Image]:
        loop = asyncio.get_running_loop()
        try:
            from pdf2image import convert_from_bytes

            images: list[Image.Image] = await loop.run_in_executor(
                None,
                partial(convert_from_bytes, pdf_bytes, dpi=200, fmt="PNG"),
            )
            return images
        except Exception as exc:
            raise OCRError(f"PDF to image conversion failed: {exc}") from exc

    async def _bytes_to_image(self, file_bytes: bytes) -> Image.Image:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: Image.open(io.BytesIO(file_bytes)).convert("RGB")
        )

    async def _ocr_image(self, image: Image.Image) -> str:
        loop = asyncio.get_running_loop()
        preprocessed = await loop.run_in_executor(None, self._preprocess, image)
        text: str = await loop.run_in_executor(
            None,
            partial(pytesseract.image_to_string, preprocessed, config=_TESSERACT_CONFIG),
        )
        return text

    @staticmethod
    def _preprocess(image: Image.Image) -> Image.Image:
        """Convert to greyscale and apply light sharpening."""
        grey = ImageOps.grayscale(image)
        return grey.filter(ImageFilter.SHARPEN)


ocr_service = OCRService()
