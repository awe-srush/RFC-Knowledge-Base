"""Tests for rfckb.query — context assembly and full document dump."""

import os

import pytest

from rfckb.builder import build_knowledge_base
from rfckb.query import get_context, get_full_document
from rfckb.schema import Config


@pytest.fixture
def kb_dir(tmp_path):
    """Build a knowledge base from the tiny RFC fixture and return its path."""
    config = Config(
        rfc_id="rfc9999",
        rfc_title="Tiny Test Protocol",
        priority_sections=["4"],
        exclude_sections=["5"],
        page_footer_patterns=[
            r"Author\s+Standards Track\s+\[Page \d+\]",
            r"RFC \d+\s+TTP\s+\w+ \d+",
        ],
    )
    out = str(tmp_path / "kb")
    build_knowledge_base("tests/fixtures/tiny_rfc.txt", config, out)
    return out


class TestGetContext:
    def test_target_section_first(self, kb_dir):
        result = get_context(kb_dir, "2.1")
        # Target should appear first with [target] tag
        lines = result.split("\n")
        # Find the first section header
        headers = [l for l in lines if l.startswith("## ")]
        assert "[target]" in headers[0]
        assert "2.1" in headers[0]

    def test_priority_section_included(self, kb_dir):
        result = get_context(kb_dir, "2.1")
        assert "[priority]" in result
        assert "§4" in result

    def test_referenced_sections_included(self, kb_dir):
        result = get_context(kb_dir, "2.1")
        # Section 2.1 references 3.1 and 3.2
        assert "§3.1" in result or "§3.2" in result

    def test_role_tags_present(self, kb_dir):
        result = get_context(kb_dir, "3")
        assert "[target]" in result
        assert "[priority]" in result

    def test_deduplication(self, kb_dir):
        result = get_context(kb_dir, "4")
        # Section 4 is both the target and a priority section
        # It should appear only once
        count = result.count("§4 —")
        assert count == 1

    def test_nonexistent_section_error(self, kb_dir):
        with pytest.raises(ValueError, match="not found"):
            get_context(kb_dir, "99.99")

    def test_similar_sections_suggested(self, kb_dir):
        with pytest.raises(ValueError, match="Similar"):
            get_context(kb_dir, "2.3")

    def test_header_line(self, kb_dir):
        result = get_context(kb_dir, "1")
        assert result.startswith("# Context for rfc9999 §1")

    def test_body_content_present(self, kb_dir):
        result = get_context(kb_dir, "1")
        assert "Tiny Test Protocol" in result

    def test_section_order(self, kb_dir):
        result = get_context(kb_dir, "3")
        # Order should be: target (3), priority (4), then referenced sections
        headers = [l for l in result.split("\n") if l.startswith("## ")]
        assert "[target]" in headers[0]
        # Priority should come before referenced
        priority_idx = None
        ref_idx = None
        for i, h in enumerate(headers):
            if "[priority]" in h and priority_idx is None:
                priority_idx = i
            if "[referenced]" in h and ref_idx is None:
                ref_idx = i
        if priority_idx is not None and ref_idx is not None:
            assert priority_idx < ref_idx


class TestGetFullDocument:
    def test_contains_all_sections(self, kb_dir):
        result = get_full_document(kb_dir)
        assert "§1 —" in result
        assert "§2 —" in result
        assert "§3 —" in result
        assert "§4 —" in result

    def test_excludes_excluded_sections(self, kb_dir):
        result = get_full_document(kb_dir)
        # Section 5 was excluded
        assert "§5 —" not in result

    def test_document_order(self, kb_dir):
        result = get_full_document(kb_dir)
        # Sections should appear in document order
        pos_1 = result.find("§1 —")
        pos_2 = result.find("§2 —")
        pos_3 = result.find("§3 —")
        pos_4 = result.find("§4 —")
        assert pos_1 < pos_2 < pos_3 < pos_4

    def test_no_role_tags(self, kb_dir):
        result = get_full_document(kb_dir)
        assert "[target]" not in result
        assert "[priority]" not in result
        assert "[referenced]" not in result

    def test_header(self, kb_dir):
        result = get_full_document(kb_dir)
        assert result.startswith("# rfc9999 — Tiny Test Protocol (full document)")

    def test_body_content(self, kb_dir):
        result = get_full_document(kb_dir)
        assert "Tiny Test Protocol" in result
        assert "Client Hello" in result
