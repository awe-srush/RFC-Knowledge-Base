"""Tests for rfckb.parser — RFC text cleaning and section parsing."""

import pytest

from rfckb.parser import compute_parent, load_and_clean, parse_sections
from rfckb.schema import Config


@pytest.fixture
def tiny_config():
    return Config(
        rfc_id="rfc9999",
        rfc_title="Tiny Test Protocol",
        priority_sections=["4"],
        exclude_sections=["5"],
        page_footer_patterns=[
            r"Author\s+Standards Track\s+\[Page \d+\]",
            r"RFC \d+\s+TTP\s+\w+ \d+",
        ],
    )


@pytest.fixture
def tiny_rfc_path():
    return "tests/fixtures/tiny_rfc.txt"


class TestLoadAndClean:
    def test_strips_page_footers(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        assert "[Page 1]" not in text
        assert "[Page 2]" not in text
        assert "Standards Track" not in text

    def test_strips_page_headers(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        # The "RFC 9999  TTP  January 2030" headers should be removed
        assert "January 2030" not in text

    def test_preserves_content(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        assert "Tiny Test Protocol" in text
        assert "Client Hello" in text

    def test_replaces_form_feeds(self, tmp_path, tiny_config):
        rfc_file = tmp_path / "test.txt"
        rfc_file.write_text("Section 1\x0cSection 2")
        text = load_and_clean(str(rfc_file), tiny_config)
        assert "\x0c" not in text
        assert "Section 1" in text
        assert "Section 2" in text


class TestParseSections:
    def test_detects_all_sections(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        sections = parse_sections(text)
        ids = [s.id for s in sections]
        assert "1" in ids
        assert "2" in ids
        assert "2.1" in ids
        assert "2.2" in ids
        assert "3" in ids
        assert "3.1" in ids
        assert "3.2" in ids
        assert "4" in ids
        assert "5" in ids

    def test_detects_appendix(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        sections = parse_sections(text)
        ids = [s.id for s in sections]
        assert "appendix-A" in ids
        assert "appendix-A.1" in ids

    def test_rejects_toc_entries(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        sections = parse_sections(text)
        # There should not be duplicate sections from TOC
        ids = [s.id for s in sections]
        # Each ID should appear exactly once
        assert len(ids) == len(set(ids))

    def test_section_titles(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        sections = parse_sections(text)
        by_id = {s.id: s for s in sections}
        assert by_id["1"].title == "Introduction"
        assert by_id["2.1"].title == "Message Format"
        assert by_id["3.1"].title == "Client Hello"

    def test_section_depth(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        sections = parse_sections(text)
        by_id = {s.id: s for s in sections}
        assert by_id["1"].depth == 1
        assert by_id["2"].depth == 1
        assert by_id["2.1"].depth == 2
        assert by_id["3.1"].depth == 2

    def test_section_body_contains_text(self, tiny_rfc_path, tiny_config):
        text = load_and_clean(tiny_rfc_path, tiny_config)
        sections = parse_sections(text)
        by_id = {s.id: s for s in sections}
        assert "Tiny Test Protocol" in by_id["1"].body_text
        assert "type-length-value" in by_id["2.1"].body_text

    def test_rejects_prose_section_mentions(self):
        """Section references in prose should not be detected as headings."""
        text = "   as described in Section 4.2 above, the protocol works.\n"
        sections = parse_sections(text)
        # "Section 4.2" in prose should not create a section
        assert len(sections) == 0

    def test_rejects_indented_numbered_list_items(self):
        """Indented numbered items (e.g., '   1.  This data...') are not headings."""
        text = "   1.  This data is not forward secret.\n   2.  There are no guarantees.\n"
        sections = parse_sections(text)
        assert len(sections) == 0

    def test_rejects_appendix_in_prose(self):
        """Prose mentions like 'Appendix C for additional info' are not headings."""
        text = "      Appendix C for additional information.\n"
        sections = parse_sections(text)
        assert len(sections) == 0

    def test_depth_4_section(self):
        text = "1.2.3.4.  Deep Nested Section\n\n   Some content here.\n"
        sections = parse_sections(text)
        assert len(sections) == 1
        assert sections[0].id == "1.2.3.4"
        assert sections[0].depth == 4

    def test_title_with_parentheses(self):
        text = "7.  Security (Overview)\n\n   Content.\n"
        sections = parse_sections(text)
        assert len(sections) == 1
        assert "Overview" in sections[0].title


class TestComputeParent:
    def test_top_level(self):
        assert compute_parent("1") is None
        assert compute_parent("4") is None

    def test_depth_2(self):
        assert compute_parent("2.1") == "2"
        assert compute_parent("4.3") == "4"

    def test_depth_3(self):
        assert compute_parent("2.1.3") == "2.1"

    def test_appendix_top(self):
        assert compute_parent("appendix-A") is None

    def test_appendix_sub(self):
        assert compute_parent("appendix-A.1") == "appendix-A"
        assert compute_parent("appendix-B.2.3") == "appendix-B.2"
