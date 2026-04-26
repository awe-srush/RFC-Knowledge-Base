"""Pydantic models for config validation and node frontmatter."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ReferencePattern(BaseModel):
    """A regex pattern for detecting cross-references in RFC text."""

    pattern: str
    group: int = 1
    prefix: str = ""


class Config(BaseModel):
    """User-authored config YAML for building an RFC knowledge base."""

    rfc_id: str
    rfc_title: str
    priority_sections: list[str] = Field(default_factory=list)
    exclude_sections: list[str] = Field(default_factory=list)
    reference_patterns: list[ReferencePattern] = Field(default_factory=list)
    page_footer_patterns: list[str] = Field(default_factory=list)

    def get_reference_patterns(self) -> list[ReferencePattern]:
        """Return reference patterns, using defaults if none configured."""
        if self.reference_patterns:
            return self.reference_patterns
        return [
            ReferencePattern(
                pattern=r"Section (\d+(?:\.\d+)*)",
                group=1,
            ),
            ReferencePattern(
                pattern=r"Appendix ([A-Z](?:\.\d+)*)",
                group=1,
                prefix="appendix-",
            ),
        ]


class Section(BaseModel):
    """A parsed section from an RFC document."""

    id: str
    title: str
    depth: int
    body_text: str


class Edge(BaseModel):
    """A cross-reference edge from one section to another."""

    target: str
    provenance: str
    target_excluded: bool = False
    target_missing: bool = False


class NodeFrontmatter(BaseModel):
    """Frontmatter for a knowledge base node file."""

    rfc_id: str
    section_id: str
    title: str
    depth: int
    parent: Optional[str] = None
    is_priority: bool = False
    edges: list[Edge] = Field(default_factory=list)
    external_references: list[str] = Field(default_factory=list)


class IndexEntry(BaseModel):
    """An entry in the knowledge base index."""

    id: str
    title: str
    filename: str


class Index(BaseModel):
    """The _index.yaml file for a knowledge base."""

    rfc_id: str
    rfc_title: str
    config_hash: str
    section_count: int
    priority_sections: list[str] = Field(default_factory=list)
    sections: list[IndexEntry] = Field(default_factory=list)
