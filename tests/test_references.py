"""Tests for rfckb.references — cross-reference extraction."""

import pytest

from rfckb.references import extract_external_references, extract_internal_references
from rfckb.schema import ReferencePattern


@pytest.fixture
def default_patterns():
    return [
        ReferencePattern(pattern=r"Section (\d+(?:\.\d+)*)", group=1),
        ReferencePattern(pattern=r"Appendix ([A-Z](?:\.\d+)*)", group=1, prefix="appendix-"),
    ]


class TestExtractInternalReferences:
    def test_single_reference(self, default_patterns):
        text = "See Section 4.2 for details."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 1
        assert edges[0].target == "4.2"

    def test_multiple_references(self, default_patterns):
        text = "Section 3.1 defines the format. Section 3.2 defines the response."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 2
        assert edges[0].target == "3.1"
        assert edges[1].target == "3.2"

    def test_reference_at_start_of_sentence(self, default_patterns):
        text = "Section 5 specifies the requirements."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 1
        assert edges[0].target == "5"

    def test_reference_at_end_of_sentence(self, default_patterns):
        text = "The format is defined in Section 2.1."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 1
        assert edges[0].target == "2.1"

    def test_multiple_references_per_sentence(self, default_patterns):
        text = "See Section 3.1 and Section 3.2 for message formats."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 2

    def test_appendix_reference(self, default_patterns):
        text = "See Appendix A for examples."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 1
        assert edges[0].target == "appendix-A"

    def test_appendix_sub_reference(self, default_patterns):
        text = "The flow in Appendix A.1 illustrates this."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 1
        assert edges[0].target == "appendix-A.1"

    def test_deduplication(self, default_patterns):
        text = "Section 4 is important. As noted in Section 4, this matters."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 1
        assert edges[0].target == "4"

    def test_order_of_appearance(self, default_patterns):
        text = "First Section 5, then Section 2, then Section 8."
        edges = extract_internal_references(text, default_patterns)
        targets = [e.target for e in edges]
        assert targets == ["5", "2", "8"]

    def test_provenance_captured(self, default_patterns):
        text = "Clients MUST send the value described in Section 3.1."
        edges = extract_internal_references(text, default_patterns)
        assert "MUST" in edges[0].provenance
        assert "Section 3.1" in edges[0].provenance

    def test_deep_section_reference(self, default_patterns):
        text = "See Section 4.2.8 for key share details."
        edges = extract_internal_references(text, default_patterns)
        assert edges[0].target == "4.2.8"

    def test_no_references(self, default_patterns):
        text = "This section has no cross-references at all."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 0

    def test_reference_in_parentheses(self, default_patterns):
        text = "The value (see Section 7.2) must be valid."
        edges = extract_internal_references(text, default_patterns)
        assert len(edges) == 1
        assert edges[0].target == "7.2"


class TestExtractExternalReferences:
    def test_rfc_reference(self):
        text = "As specified in [RFC6066], extensions may be used."
        refs = extract_external_references(text)
        assert "RFC6066" in refs

    def test_named_reference(self):
        text = "The algorithm from [ECDSA] is used here."
        refs = extract_external_references(text)
        assert "ECDSA" in refs

    def test_multiple_references(self):
        text = "See [RFC7748] and [RFC7919] for curve definitions."
        refs = extract_external_references(text)
        assert "RFC7748" in refs
        assert "RFC7919" in refs

    def test_alphabetical_order(self):
        text = "Using [QUIC] and [ASN1] standards."
        refs = extract_external_references(text)
        assert refs == ["ASN1", "QUIC"]

    def test_deduplication(self):
        text = "[RFC6066] is great. We love [RFC6066]."
        refs = extract_external_references(text)
        assert refs == ["RFC6066"]

    def test_no_external_references(self):
        text = "No references here."
        refs = extract_external_references(text)
        assert refs == []
