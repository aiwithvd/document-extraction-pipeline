import json
from typing import Any

from openai import AsyncOpenAI, RateLimitError
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.documents import EXTRACTION_SCHEMAS
from app.utils.exceptions import LLMExtractionError
from app.utils.prompts import build_user_prompt, get_system_prompt
from app.utils.text_processing import chunk_text

logger = get_logger(__name__)

# Required fields per document type for confidence scoring
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "invoice": ["invoice_number", "date", "vendor_name", "total_amount"],
    "legal": ["parties", "effective_date", "terms"],
    "esg": ["company_name", "emissions"],
}

_OPTIONAL_FIELDS: dict[str, list[str]] = {
    "invoice": ["line_items", "currency"],
    "legal": ["jurisdiction", "document_title"],
    "esg": ["sustainability_score", "reporting_year", "frameworks"],
}


class LLMExtractionService:
    """Extracts structured data from text using either OpenAI or Ollama (OpenAI-compatible)."""

    def __init__(self) -> None:
        if settings.LLM_PROVIDER == "ollama":
            self.client = AsyncOpenAI(
                base_url=f"{settings.OLLAMA_BASE_URL}/v1",
                api_key="ollama",  # Ollama requires a non-empty key
            )
            self.model = settings.OLLAMA_MODEL
        else:
            if not settings.OPENAI_API_KEY:
                raise RuntimeError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
                )
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL

        logger.info(
            "LLM service initialised",
            provider=settings.LLM_PROVIDER,
            model=self.model,
        )

    async def extract(
        self,
        text: str,
        document_type: str,
    ) -> tuple[dict[str, Any], float]:
        """Extract structured data and return (result_dict, confidence_score).

        On low confidence (< 0.6) the extraction is retried once with an
        enhanced prompt before returning the best available result.
        """
        chunks = chunk_text(text)
        combined = "\n\n---\n\n".join(chunks[:5])  # use up to 5 chunks

        result_dict, confidence = await self._run_extraction(combined, document_type, enhanced=False)

        if confidence < 0.6:
            logger.warning(
                "Low confidence extraction, retrying with enhanced prompt",
                document_type=document_type,
                confidence=confidence,
            )
            retry_dict, retry_confidence = await self._run_extraction(
                combined, document_type, enhanced=True
            )
            if retry_confidence >= confidence:
                return retry_dict, retry_confidence

        return result_dict, confidence

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    async def _run_extraction(
        self,
        text: str,
        document_type: str,
        enhanced: bool = False,
    ) -> tuple[dict[str, Any], float]:
        system_prompt = get_system_prompt(document_type, enhanced=enhanced)
        user_prompt = build_user_prompt(document_type, text)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=2000,
            )
        except RateLimitError:
            raise  # Let tenacity handle it
        except Exception as exc:
            raise LLMExtractionError(f"LLM API call failed: {exc}") from exc

        raw_content = response.choices[0].message.content or "{}"

        # Parse JSON
        try:
            raw_dict = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise LLMExtractionError(f"LLM returned invalid JSON: {exc}") from exc

        # Validate against Pydantic schema
        schema_cls = EXTRACTION_SCHEMAS.get(document_type)
        if schema_cls is None:
            raise LLMExtractionError(f"Unknown document_type: {document_type}")

        try:
            validated = schema_cls(**raw_dict)
        except ValidationError as exc:
            raise LLMExtractionError(f"Extraction failed schema validation: {exc}") from exc

        result_dict = validated.model_dump()
        confidence = self._calculate_confidence(result_dict, document_type)
        return result_dict, confidence

    def _calculate_confidence(self, result: dict[str, Any], document_type: str) -> float:
        required = _REQUIRED_FIELDS.get(document_type, [])
        optional = _OPTIONAL_FIELDS.get(document_type, [])

        if not required:
            return 0.5

        required_score = sum(
            1.0
            for field in required
            if result.get(field) not in (None, "", [], {})
        ) / len(required)

        optional_score = 0.0
        if optional:
            optional_score = sum(
                1.0
                for field in optional
                if result.get(field) not in (None, "", [], {})
            ) / len(optional)

        # Required fields carry 80% weight, optional 20%
        return round(required_score * 0.8 + optional_score * 0.2, 3)


llm_service = LLMExtractionService()
