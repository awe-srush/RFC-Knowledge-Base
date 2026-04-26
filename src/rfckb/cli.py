"""CLI entry point with argparse subcommands."""

from __future__ import annotations

import argparse
import sys

import yaml

from rfckb.schema import Config


def _cmd_build(args: argparse.Namespace) -> None:
    """Handle the 'build' subcommand."""
    from rfckb.builder import build_knowledge_base

    # Load and validate config
    with open(args.config, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    try:
        config = Config(**config_data)
    except Exception as e:
        print(f"Invalid config: {e}", file=sys.stderr)
        sys.exit(1)

    build_knowledge_base(args.rfc, config, args.output)


def _cmd_context(args: argparse.Namespace) -> None:
    """Handle the 'context' subcommand."""
    from rfckb.query import get_context

    try:
        result = get_context(args.kb, args.section)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Context written to {args.output}")
    else:
        print(result)


def _cmd_dump(args: argparse.Namespace) -> None:
    """Handle the 'dump' subcommand."""
    from rfckb.query import get_full_document

    try:
        result = get_full_document(args.kb)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Full document written to {args.output}")
    else:
        print(result)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="rfckb",
        description="RFC Knowledge Base builder and query tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # build
    build_p = subparsers.add_parser("build", help="Build a knowledge base from an RFC")
    build_p.add_argument("--rfc", required=True, help="Path to RFC text file")
    build_p.add_argument("--config", required=True, help="Path to config YAML")
    build_p.add_argument("--output", required=True, help="Output directory")
    build_p.set_defaults(func=_cmd_build)

    # context
    ctx_p = subparsers.add_parser("context", help="Assemble context for a section")
    ctx_p.add_argument("--kb", required=True, help="Path to knowledge base directory")
    ctx_p.add_argument("--section", required=True, help="Section ID to query")
    ctx_p.add_argument("--output", help="Output file path (default: stdout)")
    ctx_p.set_defaults(func=_cmd_context)

    # dump
    dump_p = subparsers.add_parser("dump", help="Dump full RFC as markdown")
    dump_p.add_argument("--kb", required=True, help="Path to knowledge base directory")
    dump_p.add_argument("--output", help="Output file path (default: stdout)")
    dump_p.set_defaults(func=_cmd_dump)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
