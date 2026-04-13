"""
MinerU-based document text extraction service.

Drop-in replacement for OCRService with the same async interface:

    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str

Uses the `mineru` CLI (vlm-auto-engine, auto parse method) to convert PDFs and
images to Markdown, which is returned as a text string for the downstream LLM
extraction step. Markdown output preserves tables, headers, and lists — all
critical for accurate structured data extraction.

Model config is written to ~/magic-pdf.json at service instantiation (once per
worker process via the module-level singleton).
"""

import asyncio
import json
import shutil
import subprocess
import tempfile
from functools import partial
from pathlib import Path

import structlog

from app.core.config import settings
from app.utils.exceptions import OCRError

logger = structlog.get_logger(__name__)

# MIME type → file extension mapping for temp file naming
_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
}


def _write_mineru_config() -> None:
    """Write ~/magic-pdf.json for the running user.

    Called once at MinerUService instantiation (module-level singleton),
    so MinerU finds a valid config before its first import.
    """
    config = {
        "models-dir": settings.MINERU_MODELS_DIR,
        "device-mode": settings.MINERU_DEVICE,
        "layout-config": {
            "model": "doclayout_yolo",
        },
    }
    config_path = Path.home() / "magic-pdf.json"
    config_path.write_text(json.dumps(config, indent=2))
    logger.info("Wrote MinerU config", path=str(config_path))


def _image_to_pdf(image_bytes: bytes, mime_type: str, dest_path: str) -> None:
    """Convert an image file to a single-page PDF using img2pdf.

    MinerU's vlm-auto-engine works best with PDF input. This conversion keeps
    the pipeline uniform regardless of the original upload format.
    """
    try:
        import img2pdf  # type: ignore[import-untyped]

        pdf_bytes = img2pdf.convert(image_bytes)
        Path(dest_path).write_bytes(pdf_bytes)
    except Exception as exc:
        raise OCRError(f"Image-to-PDF conversion failed for {mime_type}: {exc}") from exc


def _run_mineru_sync(input_path: str, output_dir: str) -> str:
    """Run the `mineru` CLI on input_path and return the Markdown output.

    Uses vlm-auto-engine with auto parse method (no explicit language — MinerU
    detects language automatically). Runs synchronously; call via
    loop.run_in_executor() from async context.

    Raises OCRError on non-zero exit or if no Markdown output is produced.
    """
    cmd = [
        "mineru",
        "-p", input_path,
        "-o", output_dir,
        "-m", "auto",
        "-b", "vlm-auto-engine",
    ]
    logger.debug("Running MinerU CLI", cmd=" ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        raise OCRError("MinerU extraction timed out after 300s") from exc
    except FileNotFoundError as exc:
        raise OCRError(
            "mineru CLI not found — ensure mineru[all] is installed"
        ) from exc

    if result.returncode != 0:
        raise OCRError(
            f"mineru CLI exited with code {result.returncode}: {result.stderr.strip()}"
        )

    # MinerU writes output to {output_dir}/{stem}/{stem}.md
    # Use glob to find the .md file regardless of subdirectory nesting
    md_files = list(Path(output_dir).glob("**/*.md"))
    if not md_files:
        raise OCRError(
            f"MinerU produced no Markdown output in {output_dir}. "
            f"stderr: {result.stderr.strip()}"
        )

    # Take the largest .md file in case MinerU writes auxiliary files
    md_file = max(md_files, key=lambda p: p.stat().st_size)
    return md_file.read_text(encoding="utf-8")


class MinerUService:
    """Extracts text from PDF and image documents using MinerU (vlm-auto-engine).

    Identical async interface to the former OCRService:
        extract_text(file_bytes, mime_type) -> str (Markdown)

    The returned Markdown string is passed directly to LLMExtractionService.
    Tables, headers, and lists are preserved in Markdown syntax, which
    significantly improves structured-data extraction accuracy vs raw OCR text.
    """

    def __init__(self) -> None:
        _write_mineru_config()

    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        """Return Markdown text extracted from file_bytes.

        PDFs are passed directly to MinerU. Images (PNG/JPEG/TIFF) are first
        converted to PDF via img2pdf so MinerU's vlm-auto-engine can process
        them uniformly.

        Raises OCRError on failure (preserves compatibility with the retry
        logic in app/workers/tasks.py).
        """
        tmp_dir = tempfile.mkdtemp(prefix="mineru_")
        try:
            if mime_type == "application/pdf":
                input_path = str(Path(tmp_dir) / "input.pdf")
                Path(input_path).write_bytes(file_bytes)
            else:
                # Convert image to PDF for uniform MinerU processing
                input_path = str(Path(tmp_dir) / "input.pdf")
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    partial(_image_to_pdf, file_bytes, mime_type, input_path),
                )

            output_dir = str(Path(tmp_dir) / "output")
            Path(output_dir).mkdir()

            loop = asyncio.get_running_loop()
            markdown_text: str = await loop.run_in_executor(
                None,
                partial(_run_mineru_sync, input_path, output_dir),
            )
            return markdown_text

        except OCRError:
            raise
        except Exception as exc:
            raise OCRError(f"MinerU service error: {exc}") from exc
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# Module-level singleton — _write_mineru_config() runs once per worker process
mineru_service = MinerUService()
