from datetime import date

from pydantic import BaseModel, field_validator


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float


class InvoiceExtraction(BaseModel):
    invoice_number: str
    date: date | str | None = None
    vendor_name: str
    total_amount: float
    line_items: list[LineItem] = []
    currency: str | None = None

    @field_validator("total_amount")
    @classmethod
    def total_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("total_amount must be non-negative")
        return v


class LegalExtraction(BaseModel):
    parties: list[str]
    effective_date: date | str | None = None
    terms: list[str] = []
    jurisdiction: str | None = None
    document_title: str | None = None


class ESGExtraction(BaseModel):
    company_name: str
    emissions: dict[str, float] = {}
    sustainability_score: float | None = None
    reporting_year: int | None = None
    frameworks: list[str] = []

    @field_validator("sustainability_score")
    @classmethod
    def score_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("sustainability_score must be between 0 and 100")
        return v


EXTRACTION_SCHEMAS: dict[str, type] = {
    "invoice": InvoiceExtraction,
    "legal": LegalExtraction,
    "esg": ESGExtraction,
}
