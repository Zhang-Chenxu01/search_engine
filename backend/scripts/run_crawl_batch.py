"""Batch crawl runner — execute crawl_batches.yaml entries.

Usage::

    cd backend

    # Dry-run: show what would run
    python scripts/run_crawl_batch.py --dry-run

    # Run a single batch
    python scripts/run_crawl_batch.py --batch news_main

    # Run all batches sequentially
    python scripts/run_crawl_batch.py --all

    # Run with parallel workers
    python scripts/run_crawl_batch.py --all --parallel 4

    # Override max_pages
    python scripts/run_crawl_batch.py --batch news_main --max-pages 2000
"""

import argparse
import json
import os
import subprocess
import sys
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "crawler/nku_crawler/config/crawl_batches.yaml",
)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_command(batch: dict, max_pages_override: Optional[int] = None) -> list[str]:
    """Build a ``scrapy crawl batch`` command line from a batch config dict."""
    mp = max_pages_override or batch.get("max_pages", 5000)
    depth = batch.get("depth_limit", 8)

    cmd = [
        sys.executable, "-m", "scrapy", "crawl", "batch",
        "-a", f"batch_name={batch['name']}",
        "-a", f"allowed_domains={','.join(batch['allowed_domains'])}",
        "-a", f"start_urls={','.join(batch['start_urls'])}",
        "-a", f"max_pages={mp}",
        "-a", f"output_file={batch['output']}",
        "-a", f"source_site={batch.get('source_site', '')}",
        "-a", f"category={batch.get('category', 'web')}",
        "-s", f"DEPTH_LIMIT={depth}",
    ]

    # Create output directory
    out_dir = os.path.dirname(batch["output"])
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    return cmd


def run_batch(batch: dict, max_pages_override: Optional[int] = None) -> int:
    """Run a single batch. Returns exit code."""
    cmd = build_command(batch, max_pages_override)
    print(f"\n{'='*60}")
    print(f"Starting batch: {batch['name']}")
    print(f"  Domains: {batch['allowed_domains']}")
    print(f"  Max pages: {max_pages_override or batch.get('max_pages')}")
    print(f"  Output: {batch['output']}")
    print(f"{'='*60}\n")

    t0 = time.time()
    cmd_dir = os.path.join(os.path.dirname(__file__), "..", "crawler")
    result = subprocess.run(cmd, cwd=cmd_dir)
    elapsed = time.time() - t0

    # Check stats (batch output is relative to crawler/ directory)
    cmd_dir = os.path.join(os.path.dirname(__file__), "..", "crawler")
    stats_path = os.path.join(cmd_dir, batch["output"].replace(".jsonl", ".stats.json"))
    if os.path.exists(stats_path):
        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)
        print(f"\nBatch '{batch['name']}' completed in {elapsed:.0f}s")
        print(f"  Pages scraped: {stats.get('pages_scraped', 0)}")
        print(f"  Pages/min: {stats.get('pages_per_minute', 0)}")
    else:
        print(f"\nBatch '{batch['name']}' completed (exit {result.returncode})")

    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch crawl runner")
    parser.add_argument("--batch", help="Run a single batch by name")
    parser.add_argument("--all", action="store_true", help="Run all batches")
    parser.add_argument("--parallel", type=int, default=1, help="Max parallel workers")
    parser.add_argument("--max-pages", type=int, default=None, help="Override max_pages for all batches")
    parser.add_argument("--dry-run", action="store_true", help="Print commands, don't execute")
    args = parser.parse_args()

    if not args.batch and not args.all:
        print("Usage: --batch <name> or --all\nRun --dry-run to preview.")
        sys.exit(1)

    config = load_config(CONFIG_PATH)
    all_batches = config["batches"]

    # ── Select batches ──────────────────────────────────────
    if args.batch:
        batches = [b for b in all_batches if b["name"] == args.batch]
        if not batches:
            print(f"Batch '{args.batch}' not found. Available:")
            for b in all_batches:
                print(f"  {b['name']}")
            sys.exit(1)
    else:
        batches = all_batches

    # ── Dry-run ─────────────────────────────────────────────
    if args.dry_run:
        total = 0
        for b in batches:
            mp = args.max_pages or b.get("max_pages", 5000)
            total += mp
            print(f"  {b['name']:30s} → {b['output']}  ({mp} pages, {b['allowed_domains']})")
        print(f"\n{len(batches)} batches, {total:,} total pages")
        return

    # ── Run ─────────────────────────────────────────────────
    if args.parallel == 1:
        # Sequential
        for b in batches:
            rc = run_batch(b, args.max_pages)
            if rc != 0:
                print(f"WARNING: batch '{b['name']}' exited with code {rc}")
    else:
        # Parallel
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {
                pool.submit(run_batch, b, args.max_pages): b["name"]
                for b in batches
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Batch '{name}' failed: {e}")

    print("\nAll batches complete.")


if __name__ == "__main__":
    main()
