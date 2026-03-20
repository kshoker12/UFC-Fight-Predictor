#!/usr/bin/env python3
"""
Update `events/*.json` with real per-bout winners.

Rules:
- `winner: null` => bout has not happened yet (UFCStats shows "next")
- `winner: "Draw"` => draw / no contest / any case with no winner
- `winner: "<fighter name>"` => actual winner name

This script is intended to be run periodically (e.g. GitHub Actions every 24h).
It only re-scrapes events that have at least one fight with missing/NULL winner.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_EVENTS_DIR = REPO_ROOT / "events"


INVALID_FILENAME_CHARS_RE = re.compile(r"[<>:\"/\\|?*]")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    s = str(name).strip().lower()
    # Remove punctuation/spaces so we can join robustly.
    s = NON_ALNUM_RE.sub("", s)
    return s


def load_scraper_simple():
    """
    Dynamically import `ufc-analytics-scraper-simple.py` (hyphenated filename).
    """

    script_path = Path(__file__).with_name("ufc-analytics-scraper-simple.py")
    spec = importlib.util.spec_from_file_location("ufc_analytics_scraper_simple", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import scraper from: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def event_has_missing_winners(event_data: Dict[str, Any]) -> bool:
    fights = event_data.get("fights", [])
    if not isinstance(fights, list):
        return True
    for f in fights:
        if not isinstance(f, dict):
            return True
        if "winner" not in f:
            return True
        if f.get("winner", None) is None:
            return True
    return False


def build_scraped_winner_map(scraped_fights: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Optional[str]]:
    """
    Map (fighter_a_name, fighter_b_name) -> winner.
    winner is either:
    - None
    - "Draw"
    - "<fighter name>"
    """

    mapping: Dict[Tuple[str, str], Optional[str]] = {}
    for fight in scraped_fights:
        a = fight.get("fighter_a")
        b = fight.get("fighter_b")
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        key = (normalize_name(a), normalize_name(b))
        mapping[key] = fight.get("winner", None)
    return mapping


def update_event_file(event_path: Path, scraper: Any) -> Dict[str, Any]:
    event_data = json.loads(event_path.read_text(encoding="utf-8"))
    event_url = event_data.get("link", "")
    if not isinstance(event_url, str) or not event_url:
        raise ValueError(f"Missing/invalid `link` in {event_path}")

    scraped_fights = scraper.get_event_fights(event_url)
    scraped_map = build_scraped_winner_map(scraped_fights)

    fights = event_data.get("fights", [])
    if not isinstance(fights, list):
        raise ValueError(f"Invalid `fights` structure in {event_path}")

    updated = 0
    missing_matches = 0

    for f in fights:
        if not isinstance(f, dict):
            continue
        fighter_a = (f.get("fighter_a") or {}).get("name") if isinstance(f.get("fighter_a"), dict) else None
        fighter_b = (f.get("fighter_b") or {}).get("name") if isinstance(f.get("fighter_b"), dict) else None
        if not isinstance(fighter_a, str) or not isinstance(fighter_b, str):
            continue

        key = (normalize_name(fighter_a), normalize_name(fighter_b))
        if key in scraped_map:
            scraped_winner = scraped_map[key]
            if f.get("winner", None) != scraped_winner:
                f["winner"] = scraped_winner
                updated += 1
        else:
            # Attempt swapped order; winner is stored as a fighter name string so it's safe to set.
            swapped_key = (normalize_name(fighter_b), normalize_name(fighter_a))
            if swapped_key in scraped_map:
                f["winner"] = scraped_map[swapped_key]
                updated += 1
            else:
                missing_matches += 1

    event_path.write_text(json.dumps(event_data, indent=4, ensure_ascii=False), encoding="utf-8")

    return {
        "event_path": str(event_path),
        "event_name": event_data.get("name", None),
        "event_url": event_url,
        "updated_fight_records": updated,
        "missing_fight_matches": missing_matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-dir", type=str, default=str(DEFAULT_EVENTS_DIR))
    parser.add_argument("--max-events", type=int, default=0, help="0 means no limit.")
    parser.add_argument("--force", action="store_true", help="Re-scrape every event, even if winners exist.")
    parser.add_argument("--log-file", type=str, default=str(REPO_ROOT / "event_winner_update.log"))
    args = parser.parse_args()

    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")],
    )

    events_dir = Path(args.events_dir)
    if not events_dir.exists():
        raise FileNotFoundError(f"Events dir not found: {events_dir}")

    scraper = load_scraper_simple()

    event_paths = sorted(events_dir.glob("*.json"))
    if not event_paths:
        logging.info("No event JSON files found in %s", events_dir)
        return

    processed = 0
    updated_events = 0
    skipped_complete = 0

    for event_path in event_paths:
        if args.max_events and processed >= args.max_events:
            break
        processed += 1

        try:
            raw = event_path.read_text(encoding="utf-8")
            event_data = json.loads(raw)
        except Exception as e:
            logging.warning("Skipping unreadable JSON %s: %s", event_path, e)
            continue

        needs_update = args.force or event_has_missing_winners(event_data)
        if not needs_update:
            skipped_complete += 1
            continue

        logging.info("Updating winners for %s", event_path.name)
        try:
            result = update_event_file(event_path, scraper)
            updated_events += 1
            logging.info(
                "Updated event=%s updated_fights=%s missing_matches=%s",
                result.get("event_name"),
                result.get("updated_fight_records"),
                result.get("missing_fight_matches"),
            )
        except Exception as e:
            logging.exception("Failed updating winners for %s: %s", event_path.name, e)
            continue

    logging.info(
        "Done. processed=%s updated_events=%s skipped_complete=%s max_events=%s",
        processed,
        updated_events,
        skipped_complete,
        args.max_events,
    )


if __name__ == "__main__":
    main()

