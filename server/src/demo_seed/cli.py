from __future__ import annotations

import argparse
import asyncio
import json

from src.demo_seed.context import SeedRunContext
from src.demo_seed.logging import configure_logging
from src.demo_seed.orchestrator import cleanup_command, collect_media_command, review_media_command, run_seed_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.demo_seed", description="Nerdex demo seed CLI")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")

    subparsers = parser.add_subparsers(dest="command", required=True)

    media = subparsers.add_parser("media", help="Media operations")
    media_sub = media.add_subparsers(dest="media_command", required=True)

    media_collect = media_sub.add_parser("collect", help="Collect media from Pixabay")
    media_collect.add_argument("--seed", type=int, default=42)

    media_sub.add_parser("review", help="Generate media review HTML")

    run = subparsers.add_parser("run", help="Run full seed")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--reset", action="store_true")

    cleanup = subparsers.add_parser("cleanup", help="Cleanup one seed run")
    cleanup.add_argument("--seed-run-id", required=True)

    return parser


async def run_cli_async(args: argparse.Namespace) -> int:
    configure_logging(verbose=bool(args.verbose))

    if args.command == "media" and args.media_command == "collect":
        context = SeedRunContext.create(seed=args.seed)
        result = await collect_media_command(context)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "media" and args.media_command == "review":
        context = SeedRunContext.create(seed=42)
        result = await review_media_command(context)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run":
        context = SeedRunContext.create(seed=args.seed)
        result = await run_seed_command(context, reset=bool(args.reset))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "cleanup":
        result = await cleanup_command(seed_run_id=args.seed_run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run_cli_async(args))
