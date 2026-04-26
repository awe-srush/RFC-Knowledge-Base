"""Cross-reference detection in RFC section text."""

from __future__ import annotations

import re

from rfckb.schema import Edge, ReferencePattern


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using a simple heuristic.

    Splits on period/question-mark/exclamation followed by whitespace and a
    capital letter, or on newline-separated paragraphs. Good enough for
    provenance extraction — doesn't need to be perfect.
    """
    # First, normalize text: join continuation lines but keep paragraph breaks
    # Split on sentence-ending punctuation followed by whitespace and uppercase
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    # Filter out empty strings
    return [s.strip() for s in sentences if s.strip()]


def _find_sentence_containing(text: str, match_start: int, match_end: int) -> str:
    """Find the sentence in text that contains the span [match_start, match_end)."""
    sentences = _split_sentences(text)
    # Walk through text to find which sentence contains the match
    pos = 0
    for sentence in sentences:
        idx = text.find(sentence, pos)
        if idx == -1:
            continue
        sent_end = idx + len(sentence)
        if idx <= match_start < sent_end:
            return sentence
        pos = idx + 1

    # Fallback: return a window around the match
    line_start = text.rfind("\n", 0, match_start)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = text.find("\n", match_end)
    line_end = len(text) if line_end == -1 else line_end
    return text[line_start:line_end].strip()


def extract_internal_references(
    body_text: str,
    patterns: list[ReferencePattern],
) -> list[Edge]:
    """Extract internal cross-references from section body text.

    Returns edges in order of appearance in the text.
    """
    edges: list[tuple[int, Edge]] = []  # (position, edge) for stable ordering
    seen_targets: set[str] = set()

    for ref_pattern in patterns:
        compiled = re.compile(ref_pattern.pattern)
        for match in compiled.finditer(body_text):
            raw_id = match.group(ref_pattern.group).rstrip(".")
            target_id = ref_pattern.prefix + raw_id

            if target_id in seen_targets:
                continue
            seen_targets.add(target_id)

            provenance = _find_sentence_containing(
                body_text, match.start(), match.end()
            )

            edges.append((match.start(), Edge(
                target=target_id,
                provenance=provenance,
            )))

    # Sort by position in text
    edges.sort(key=lambda x: x[0])
    return [e for _, e in edges]


# Pattern for external references like [RFC6066], [ECDSA], [DH76]
_EXTERNAL_REF_RE = re.compile(r"\[([A-Z][A-Za-z0-9]+(?:\d+)?)\]")


def extract_external_references(body_text: str) -> list[str]:
    """Extract external references (e.g., [RFC6066], [ECDSA]) from text.

    Returns alphabetically sorted, deduplicated list of reference identifiers.
    """
    refs = set()
    for match in _EXTERNAL_REF_RE.finditer(body_text):
        refs.add(match.group(1))
    return sorted(refs)
