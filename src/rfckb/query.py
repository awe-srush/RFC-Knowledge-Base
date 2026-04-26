"""Knowledge base querying: section ID → assembled context markdown."""

from __future__ import annotations

import os
from difflib import get_close_matches

import yaml

from rfckb.schema import Index


def _load_index(kb_dir: str) -> Index:
    """Load and validate the _index.yaml from a knowledge base directory."""
    index_path = os.path.join(kb_dir, "_index.yaml")
    if not os.path.exists(index_path):
        raise FileNotFoundError(
            f"No _index.yaml found in {kb_dir}. Is this a valid knowledge base?"
        )
    with open(index_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Index(**data)


def _load_node_body(kb_dir: str, filename: str) -> str:
    """Load a node file and return just the body (after frontmatter)."""
    filepath = os.path.join(kb_dir, filename)
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # Strip YAML frontmatter (between --- markers)
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            # Skip past the closing --- and any following newlines
            body_start = end + 3
            if body_start < len(content) and content[body_start] == "\n":
                body_start += 1
            if body_start < len(content) and content[body_start] == "\n":
                body_start += 1
            return content[body_start:].rstrip("\n")
    return content.rstrip("\n")


def _load_node_edges(kb_dir: str, filename: str) -> list[dict]:
    """Load a node file and return its edges from frontmatter."""
    filepath = os.path.join(kb_dir, filename)
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm_str = content[3:end]
            fm = yaml.safe_load(fm_str)
            return fm.get("edges", [])
    return []


def get_context(kb_dir: str, section_id: str) -> str:
    """Assemble context for a section: target + priority + referenced sections.

    Returns a single markdown string.
    """
    index = _load_index(kb_dir)

    # Build lookup maps
    id_to_entry = {entry.id: entry for entry in index.sections}
    all_ids = list(id_to_entry.keys())

    # Validate section exists
    if section_id not in id_to_entry:
        similar = get_close_matches(section_id, all_ids, n=5, cutoff=0.4)
        msg = f"Section '{section_id}' not found in knowledge base."
        if similar:
            msg += f" Similar sections: {', '.join(similar)}"
        raise ValueError(msg)

    target_entry = id_to_entry[section_id]

    # Load target node edges
    edges = _load_node_edges(kb_dir, target_entry.filename)

    # Collect section IDs to include (preserving order and deduplicating)
    included_ids: list[str] = [section_id]
    seen: set[str] = {section_id}

    # Priority sections (in config order)
    for pid in index.priority_sections:
        if pid not in seen and pid in id_to_entry:
            included_ids.append(pid)
            seen.add(pid)

    # Referenced sections (in edge order), skipping excluded/missing
    for edge in edges:
        target = edge["target"]
        if edge.get("target_excluded") or edge.get("target_missing"):
            continue
        if target not in seen and target in id_to_entry:
            included_ids.append(target)
            seen.add(target)

    # Determine roles
    priority_set = set(index.priority_sections)
    target_title = id_to_entry[section_id].title

    # Build output
    parts: list[str] = []
    parts.append(f"# Context for {index.rfc_id} \u00a7{section_id} ({target_title})")

    for sid in included_ids:
        entry = id_to_entry[sid]
        body = _load_node_body(kb_dir, entry.filename)

        if sid == section_id:
            role = "target"
        elif sid in priority_set:
            role = "priority"
        else:
            role = "referenced"

        parts.append("---")
        parts.append(f"## {index.rfc_id} \u00a7{sid} \u2014 {entry.title} [{role}]")
        parts.append("")
        parts.append(body)
        parts.append("")

    return "\n\n".join(parts) + "\n"


def get_full_document(kb_dir: str) -> str:
    """Return the entire knowledge base as a single concatenated markdown blob.

    Sections appear in document order (as listed in _index.yaml).
    """
    index = _load_index(kb_dir)

    parts: list[str] = []
    parts.append(f"# {index.rfc_id} \u2014 {index.rfc_title} (full document)")

    for entry in index.sections:
        body = _load_node_body(kb_dir, entry.filename)
        parts.append("---")
        parts.append(f"## {index.rfc_id} \u00a7{entry.id} \u2014 {entry.title}")
        parts.append("")
        parts.append(body)
        parts.append("")

    return "\n\n".join(parts) + "\n"
