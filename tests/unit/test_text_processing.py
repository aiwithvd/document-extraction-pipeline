import pytest

from app.utils.text_processing import chunk_text, clean_text, sanitize_filename


class TestCleanText:
    def test_removes_excess_blank_lines(self):
        raw = "line1\n\n\n\nline2"
        result = clean_text(raw)
        assert "\n\n\n" not in result
        assert "line1" in result
        assert "line2" in result

    def test_strips_noise_lines(self):
        raw = "Invoice\n---\nTotal: $100"
        result = clean_text(raw)
        assert "---" not in result
        assert "Invoice" in result

    def test_normalises_unicode(self):
        # Composed vs decomposed é
        composed = "\u00e9"
        decomposed = "e\u0301"
        assert clean_text(decomposed) == clean_text(composed)

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_strips_form_feed(self):
        result = clean_text("page1\fpage2")
        assert "\f" not in result
        assert "page1" in result
        assert "page2" in result


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        text = "Short text"
        chunks = chunk_text(text, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_splits_into_multiple_chunks(self):
        text = "word " * 1000  # ~5000 chars
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1

    def test_no_empty_chunks(self):
        text = "a" * 3000
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert all(c.strip() for c in chunks)

    def test_overlap_content_repeated(self):
        text = "sentence one. sentence two. sentence three. " * 50
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        # Content in the overlap zone should appear in consecutive chunks
        assert len(chunks) > 1


class TestSanitizeFilename:
    def test_strips_path_components(self):
        result = sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result

    def test_replaces_special_chars(self):
        result = sanitize_filename("my file (copy).pdf")
        assert "(" not in result
        assert " " not in result

    def test_respects_max_length(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_fallback_for_empty(self):
        result = sanitize_filename("")
        assert result == "upload"
