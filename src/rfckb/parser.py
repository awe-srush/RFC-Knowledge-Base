"""RFC text parsing: cleaning and section boundary detection."""

from __future__ import annotations

import re

from rfckb.schema import Config, Section


def load_and_clean(rfc_path: str, config: Config) -> str:
    """Load RFC text file, strip page footers/headers, and normalize."""
    with open(rfc_path, encoding="utf-8") as f:
        text = f.read()

    # Replace form-feed characters with newlines
    text = text.replace("\x0c", "\n")

    # Strip page footer/header patterns from config
    for pattern in config.page_footer_patterns:
        text = re.sub(pattern, "", text)

    # Collapse runs of 3+ blank lines down to 2 (page break artifacts)
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text


def _is_toc_line(line: str) -> bool:
    """Check if a line is a table-of-contents entry (has dot leaders)."""
    return bool(re.search(r"\.{4,}", line))


def _is_toc_region_entry(line: str) -> bool:
    """Check if a line looks like a TOC entry that lost its dot leaders.

    Some TOC entries span page breaks and after page footer stripping,
    the dot leaders end up on a different line. These entries typically
    end with a bare page number.
    """
    stripped = line.rstrip()
    return bool(re.search(r"\.\.\d+$", stripped))


# Pattern for numbered section headings: N. or N.N. or N.N.N. etc.
# Real section headings in RFCs start at the beginning of the line (no
# indentation). Indented numbered items are list items in prose, not headings.
_SECTION_HEADING_RE = re.compile(
    r"^"                               # must start at beginning of line
    r"(\d+(?:\.\d+){0,3})"            # section number (1-4 levels)
    r"\."                              # trailing period (required for headings)
    r"\s{2,}"                          # at least 2 spaces after period
    r"([A-Z0-9(].*)"                   # title starting with capital letter, digit, or paren
    r"$"
)

# Pattern for appendix headings: "Appendix X.  Title"
# Must start at beginning of line (no indentation).
_APPENDIX_HEADING_RE = re.compile(
    r"^"                               # no leading whitespace
    r"Appendix\s+"
    r"([A-Z](?:\.\d+)*)"              # appendix letter, optionally with sub-numbers
    r"\."                              # trailing period required
    r"\s{2,}"                          # at least 2 spaces
    r"(.*\S)"                          # title
    r"$"
)

# Pattern for appendix sub-section headings (e.g., "A.1.  Heading")
# Must start at beginning of line (no indentation).
_APPENDIX_SUB_HEADING_RE = re.compile(
    r"^"                               # no leading whitespace
    r"([A-Z]\.\d+(?:\.\d+)*)"         # e.g., A.1 or A.1.2
    r"\."                              # trailing period required
    r"\s{2,}"                          # at least 2 spaces
    r"([A-Z0-9(].*)"                   # title starting with capital letter, digit, or paren
    r"$"
)


def parse_sections(text: str) -> list[Section]:
    """Parse RFC text into an ordered list of Section objects."""
    lines = text.split("\n")
    headings: list[tuple[int, str, str, int]] = []  # (line_idx, section_id, title, depth)

    for i, line in enumerate(lines):
        if _is_toc_line(line):
            continue

        # Try numbered section heading
        m = _SECTION_HEADING_RE.match(line)
        if m:
            raw_id = m.group(1)
            section_id = raw_id.rstrip(".")
            title = m.group(2).strip()
            depth = section_id.count(".") + 1
            headings.append((i, section_id, title, depth))
            continue

        # Try appendix heading (Appendix X.  Title)
        m = _APPENDIX_HEADING_RE.match(line)
        if m:
            letter = m.group(1)
            section_id = f"appendix-{letter}"
            title = m.group(2).strip()
            depth = letter.count(".") + 1
            headings.append((i, section_id, title, depth))
            continue

        # Try appendix sub-section heading (A.1.  Title)
        m = _APPENDIX_SUB_HEADING_RE.match(line)
        if m:
            raw_id = m.group(1).rstrip(".")
            section_id = f"appendix-{raw_id}"
            title = m.group(2).strip()
            # depth: A.1 = 2, A.1.2 = 3
            depth = raw_id.count(".") + 1
            headings.append((i, section_id, title, depth))
            continue

    # Build sections from heading positions
    sections: list[Section] = []
    for idx, (line_idx, section_id, title, depth) in enumerate(headings):
        start = line_idx
        if idx + 1 < len(headings):
            end = headings[idx + 1][0]
        else:
            end = len(lines)

        body_text = "\n".join(lines[start:end]).rstrip()
        sections.append(Section(
            id=section_id,
            title=title,
            depth=depth,
            body_text=body_text,
        ))

    return sections


def compute_parent(section_id: str) -> str | None:
    """Compute the parent section ID from a section ID."""
    if section_id.startswith("appendix-"):
        inner = section_id[len("appendix-"):]
        if "." in inner:
            parent_inner = inner.rsplit(".", 1)[0]
            return f"appendix-{parent_inner}"
        # Top-level appendix has no parent
        return None

    if "." in section_id:
        return section_id.rsplit(".", 1)[0]
    return None
