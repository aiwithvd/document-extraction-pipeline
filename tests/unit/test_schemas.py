import pytest
from pydantic import ValidationError

from app.schemas.documents import ESGExtraction, InvoiceExtraction, LegalExtraction


class TestInvoiceSchema:
    def test_valid_invoice(self):
        data = {
            "invoice_number": "INV-001",
            "date": "2024-01-15",
            "vendor_name": "Acme Corp",
            "total_amount": 1500.00,
            "line_items": [
                {"description": "Widget", "quantity": 3, "unit_price": 500, "total": 1500}
            ],
        }
        invoice = InvoiceExtraction(**data)
        assert invoice.invoice_number == "INV-001"
        assert invoice.total_amount == 1500.00

    def test_negative_total_raises(self):
        with pytest.raises(ValidationError):
            InvoiceExtraction(
                invoice_number="INV-001",
                vendor_name="Acme",
                total_amount=-100.0,
            )

    def test_optional_fields_default_to_none(self):
        invoice = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            total_amount=0.0,
        )
        assert invoice.currency is None
        assert invoice.date is None


class TestLegalSchema:
    def test_valid_legal(self):
        data = {
            "parties": ["Acme Inc.", "John Doe"],
            "effective_date": "2024-06-01",
            "terms": ["Payment within 30 days", "Governing law: California"],
        }
        doc = LegalExtraction(**data)
        assert len(doc.parties) == 2

    def test_empty_parties_is_valid(self):
        doc = LegalExtraction(parties=[], effective_date=None, terms=[])
        assert doc.parties == []


class TestESGSchema:
    def test_valid_esg(self):
        data = {
            "company_name": "GreenCo",
            "emissions": {"co2_tonnes": 12345.0, "scope1": 5000.0},
            "sustainability_score": 78.5,
            "reporting_year": 2023,
        }
        report = ESGExtraction(**data)
        assert report.sustainability_score == 78.5

    def test_score_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            ESGExtraction(
                company_name="X",
                emissions={},
                sustainability_score=150.0,
            )

    def test_score_zero_is_valid(self):
        report = ESGExtraction(company_name="X", emissions={}, sustainability_score=0.0)
        assert report.sustainability_score == 0.0
