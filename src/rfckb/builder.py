"""Knowledge base builder: sections + config → markdown node files on disk."""

from __future__ import annotations

import hashlib
import os
import sys

import yaml

from rfckb.parser import compute_parent, load_and_clean, parse_sections
from rfckb.references import extract_external_references, extract_internal_references
from rfckb.schema import Config, Edge, Index, IndexEntry, NodeFrontmatter, Section


def _section_id_to_filename(rfc_id: str, section_id: str) -> str:
    """Convert section ID to a flat filename. Dots become dashes."""
    safe_id = section_id.replace(".", "-")
    return f"{rfc_id}-{safe_id}.md"


def _serialize_frontmatter(fm: NodeFrontmatter) -> str:
    """Serialize frontmatter to YAML string with controlled field order."""
    data: dict = {
        "rfc_id": fm.rfc_id,
        "section_id": fm.section_id,
        "title": fm.title,
        "depth": fm.depth,
        "parent": fm.parent,
        "is_priority": fm.is_priority,
    }

    if fm.edges:
        edges_list = []
        for edge in fm.edges:
            edge_dict: dict = {"target": edge.target, "provenance": edge.provenance}
            if edge.target_excluded:
                edge_dict["target_excluded"] = True
            if edge.target_missing:
                edge_dict["target_missing"] = True
            edges_list.append(edge_dict)
        data["edges"] = edges_list

    if fm.external_references:
        data["external_references"] = fm.external_references

    return yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=1000,  # avoid line wrapping in provenance strings
    )


def build_knowledge_base(
    rfc_path: str,
    config: Config,
    output_dir: str,
) -> None:
    """Build the knowledge base from an RFC file and config."""
    # Step 1: Load and clean
    text = load_and_clean(rfc_path, config)

    # Step 2: Parse sections
    sections = parse_sections(text)

    # Step 3: Build section ID sets for validation
    section_ids = {s.id for s in sections}
    exclude_set = set(config.exclude_sections)
    priority_set = set(config.priority_sections)

    def _is_excluded(section_id: str) -> bool:
        """Check if a section or any of its ancestors is excluded."""
        if section_id in exclude_set:
            return True
        # Check if any ancestor (prefix) is excluded
        # e.g., if "12" is excluded, "12.1" and "12.2" are also excluded
        for exc in exclude_set:
            if section_id.startswith(exc + "."):
                return True
        return False

    # Filter out excluded sections (including children of excluded parents)
    active_sections = [s for s in sections if not _is_excluded(s.id)]

    # Step 4: Process each section — extract references, build frontmatter
    ref_patterns = config.get_reference_patterns()
    nodes: list[tuple[str, NodeFrontmatter, str]] = []  # (filename, frontmatter, body)

    total_internal_refs = 0
    excluded_refs = 0
    missing_refs = 0
    total_external_refs = 0

    for section in active_sections:
        # Extract references
        edges = extract_internal_references(section.body_text, ref_patterns)
        external_refs = extract_external_references(section.body_text)

        # Annotate edges
        annotated_edges: list[Edge] = []
        for edge in edges:
            # Skip self-references
            if edge.target == section.id:
                continue

            if _is_excluded(edge.target):
                annotated_edges.append(Edge(
                    target=edge.target,
                    provenance=edge.provenance,
                    target_excluded=True,
                ))
                excluded_refs += 1
            elif edge.target not in section_ids:
                annotated_edges.append(Edge(
                    target=edge.target,
                    provenance=edge.provenance,
                    target_missing=True,
                ))
                missing_refs += 1
                print(
                    f"WARNING: Section {section.id} references nonexistent "
                    f"section {edge.target}",
                    file=sys.stderr,
                )
            else:
                annotated_edges.append(edge)

            total_internal_refs += 1

        total_external_refs += len(external_refs)

        filename = _section_id_to_filename(config.rfc_id, section.id)
        fm = NodeFrontmatter(
            rfc_id=config.rfc_id,
            section_id=section.id,
            title=section.title,
            depth=section.depth,
            parent=compute_parent(section.id),
            is_priority=section.id in priority_set,
            edges=annotated_edges,
            external_references=external_refs,
        )

        nodes.append((filename, fm, section.body_text))

    # Step 5: Write files
    os.makedirs(output_dir, exist_ok=True)

    # Check for filename collisions
    filenames = [fn for fn, _, _ in nodes]
    if len(filenames) != len(set(filenames)):
        seen = set()
        for fn in filenames:
            if fn in seen:
                print(f"ERROR: Filename collision: {fn}", file=sys.stderr)
            seen.add(fn)
        raise ValueError("Filename collisions detected")

    for filename, fm, body in nodes:
        filepath = os.path.join(output_dir, filename)
        frontmatter_str = _serialize_frontmatter(fm)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(frontmatter_str)
            f.write("---\n\n")
            f.write(body)
            f.write("\n")

    # Write _index.yaml
    config_hash = hashlib.sha256(
        yaml.safe_dump(config.model_dump(), sort_keys=True).encode()
    ).hexdigest()

    index = Index(
        rfc_id=config.rfc_id,
        rfc_title=config.rfc_title,
        config_hash=config_hash,
        section_count=len(nodes),
        priority_sections=config.priority_sections,
        sections=[
            IndexEntry(
                id=fm.section_id,
                title=fm.title,
                filename=filename,
            )
            for filename, fm, _ in nodes
        ],
    )

    index_path = os.path.join(output_dir, "_index.yaml")
    index_data = index.model_dump()
    with open(index_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            index_data,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )

    # Validation: check priority sections exist
    for ps in config.priority_sections:
        if ps not in section_ids and ps not in exclude_set:
            print(
                f"WARNING: Priority section {ps} not found in RFC",
                file=sys.stderr,
            )

    # Report summary
    active_priority = [p for p in config.priority_sections if p in section_ids]
    print(f"Built {config.rfc_id} knowledge base:")
    print(f"  {len(nodes)} sections written to {output_dir}/")
    if active_priority:
        print(f"  {len(active_priority)} priority sections: {', '.join(active_priority)}")
    print(f"  {total_internal_refs} internal cross-references resolved")
    if excluded_refs:
        print(f"  {excluded_refs} cross-references to excluded sections (skipped at query time)")
    if missing_refs:
        print(f"  {missing_refs} cross-references to missing sections (target_missing: true)")
    print(f"  {total_external_refs} external references recorded")
