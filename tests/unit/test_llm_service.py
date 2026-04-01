import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.prompts import build_user_prompt, get_system_prompt


class TestPrompts:
    def test_invoice_system_prompt_contains_schema(self):
        prompt = get_system_prompt("invoice")
        assert "invoice_number" in prompt
        assert "total_amount" in prompt

    def test_legal_system_prompt_contains_schema(self):
        prompt = get_system_prompt("legal")
        assert "parties" in prompt
        assert "effective_date" in prompt

    def test_esg_system_prompt_contains_schema(self):
        prompt = get_system_prompt("esg")
        assert "company_name" in prompt
        assert "emissions" in prompt

    def test_enhanced_prompt_adds_suffix(self):
        base = get_system_prompt("invoice", enhanced=False)
        enhanced = get_system_prompt("invoice", enhanced=True)
        assert len(enhanced) > len(base)
        assert "IMPORTANT" in enhanced

    def test_user_prompt_includes_document_type(self):
        prompt = build_user_prompt("invoice", "Invoice text here")
        assert "invoice" in prompt.lower()
        assert "Invoice text here" in prompt


class TestConfidenceScoring:
    """Test confidence scoring logic by calling the private method directly."""

    def _make_service(self):
        """Create service with mocked OpenAI client to avoid network calls."""
        with patch("app.services.llm_service.AsyncOpenAI"), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_settings.OLLAMA_MODEL = "llama3"

            from app.services.llm_service import LLMExtractionService
            svc = LLMExtractionService.__new__(LLMExtractionService)
            svc.model = "gpt-4o-mini"
            return svc

    def test_full_invoice_score_is_high(self):
        from app.services.llm_service import LLMExtractionService
        svc = LLMExtractionService.__new__(LLMExtractionService)
        result = {
            "invoice_number": "INV-001",
            "date": "2024-01-01",
            "vendor_name": "Acme",
            "total_amount": 100.0,
            "line_items": [{"description": "x", "quantity": 1, "unit_price": 100, "total": 100}],
            "currency": "USD",
        }
        score = svc._calculate_confidence(result, "invoice")
        assert score >= 0.9

    def test_missing_required_fields_lowers_score(self):
        from app.services.llm_service import LLMExtractionService
        svc = LLMExtractionService.__new__(LLMExtractionService)
        result = {
            "invoice_number": None,
            "date": None,
            "vendor_name": None,
            "total_amount": None,
            "line_items": [],
            "currency": None,
        }
        score = svc._calculate_confidence(result, "invoice")
        assert score == 0.0
