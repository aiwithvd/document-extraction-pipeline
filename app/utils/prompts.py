INVOICE_SYSTEM_PROMPT = """You are a document data extraction assistant.
Extract structured data from the invoice text provided.
Return ONLY valid JSON matching this exact schema:
{
  "invoice_number": "<string>",
  "date": "<YYYY-MM-DD or null>",
  "vendor_name": "<string>",
  "total_amount": <number>,
  "line_items": [
    {"description": "<string>", "quantity": <number>, "unit_price": <number>, "total": <number>}
  ],
  "currency": "<3-letter code or null>"
}
Rules:
- Use null for any field you cannot find.
- total_amount must be a number (no currency symbols).
- date must be ISO 8601 (YYYY-MM-DD) or null.
- Do not include any text outside the JSON object."""

LEGAL_SYSTEM_PROMPT = """You are a legal document data extraction assistant.
Extract structured data from the legal document text provided.
Return ONLY valid JSON matching this exact schema:
{
  "parties": ["<party name>"],
  "effective_date": "<YYYY-MM-DD or null>",
  "terms": ["<key term or clause summary>"],
  "jurisdiction": "<jurisdiction or null>",
  "document_title": "<title or null>"
}
Rules:
- parties must be a list of entity/person names.
- terms should summarise key obligations and conditions (one string per term).
- Use null for any field you cannot find.
- Do not include any text outside the JSON object."""

ESG_SYSTEM_PROMPT = """You are an ESG report data extraction assistant.
Extract structured data from the ESG report text provided.
Return ONLY valid JSON matching this exact schema:
{
  "company_name": "<string>",
  "emissions": {"<metric_name>": <number>},
  "sustainability_score": <number 0-100 or null>,
  "reporting_year": <integer or null>,
  "frameworks": ["<framework name>"]
}
Rules:
- emissions should map metric names (e.g. "co2_tonnes", "scope1_mtco2e") to their numeric values.
- sustainability_score is a 0-100 numeric score; use null if not present.
- frameworks lists reporting standards mentioned (e.g. "GRI", "TCFD", "CDP").
- Use null for any field you cannot find.
- Do not include any text outside the JSON object."""

ENHANCED_SUFFIX = """

IMPORTANT: Some fields may have been missed in a previous extraction attempt.
Look carefully for any remaining data and populate as many fields as possible.
The response MUST be a single valid JSON object."""

SYSTEM_PROMPTS = {
    "invoice": INVOICE_SYSTEM_PROMPT,
    "legal": LEGAL_SYSTEM_PROMPT,
    "esg": ESG_SYSTEM_PROMPT,
}


def build_user_prompt(document_type: str, text: str) -> str:
    return f"Extract data from the following {document_type} document:\n\n{text}"


def get_system_prompt(document_type: str, enhanced: bool = False) -> str:
    base = SYSTEM_PROMPTS.get(document_type, INVOICE_SYSTEM_PROMPT)
    return base + (ENHANCED_SUFFIX if enhanced else "")
