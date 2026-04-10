#!/usr/bin/env python3
"""
Cyberpunk 2077 save file extractor for RPG Scribe.

Reads a CP2077 save folder (sav.dat + metadata.9.json) and outputs JSON
matching the /api/v1/sync endpoint format. Uses the parser in tools/
for binary FactsDB extraction and metadata merging.

Usage:
    python extract.py [save_folder]          # print sync JSON to stdout
    python extract.py --server http://localhost:8081  # POST to server
    python extract.py --list                 # list available saves

Output (stdout): JSON sync payload
With --server: POSTs directly to the sync endpoint
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add project root to path so we can import tools/parse_cp2077_save
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.parse_cp2077_save import parse_save, find_saves


SEED_DATA_PATH = PROJECT_ROOT / "seed-data" / "cyberpunk2077.json"

# Manual mapping for stages where the stage_key doesn't directly match
# the FactsDB naming convention. Maps stage_key -> list of fact name
# substrings that indicate the stage is done (checked against _done facts).
# Stages not listed here use the default '{stage_key}_done' pattern.
STAGE_DONE_FACTS = {
    # sq031 - Chippin' In (Johnny/Rogue questline)
    "sq031_rogue": ["sq031_afterlife_sequence_done"],
    "sq031_smack": ["sq031_cool_metal_fire_done"],
    "sq031_cinema": ["sq031_cinema_done", "sq031_blistering_done"],
    # sq023 - Sinnerman
    "sq023_hit": ["sq023_hit_done", "sq023_sinnerman_done"],
    "sq023_bd": ["sq023_bd_done"],
    "sq023_real": ["sq023_real_done"],
    # sq024 - Beast in Me (racing)
    "sq024_city": ["sq024_city_done"],
    "sq024_badlands": ["sq024_badlands_done"],
    "sq024_santo": ["sq024_santo_done"],
    "sq024_big": ["sq024_big_done", "sq024_done"],
    # mq025 - Beat on the Brat (first stage uses descriptive name)
    "mq025_psycho_brawl": ["mq025_fist_fight_quest_start"],
    # q301 - Dog Eat Dog (PL) — facts use numeric IDs (q301_00, q301_01)
    "q301": ["q301_00_done"],
    "q301_finding_myers": ["q301_01_done", "q301_finding_myers_done"],
    "q301_q302": ["q301_02_done", "q302_done"],
    # q303 - The Damned (PL)
    "q303_baron": ["q303_baron_done"],
    "q303_hands": ["q303_hands_done"],
    "q303_songbird": ["q303_songbird_done"],
    # q304 - Firestarter (PL)
    "q304_deal": ["q304_deal_done"],
    "q304_netrunners": ["q304_netrunners_done"],
    "q304_stadium": ["q304_stadium_done"],
    # q305 - Leave in Silence (PL - Reed's path)
    "q305_border_crossing": ["q305_border_crossing_done"],
    "q305_bunker": ["q305_bunker_done"],
    "q305_postcontent": ["q305_postcontent_done"],
    "q305_prison_convoy": ["q305_prison_convoy_done"],
    "q305_reed_epilogue": ["q305_reed_epilogue_done"],
    # q306 - The Killing Moon (PL - Songbird's path)
    "q306_devils_bargain": ["q306_devils_bargain_done"],
    "q306_postcontent": ["q306_postcontent_done"],
    "q306_reed_epilogue": ["q306_reed_epilogue_done"],
    "q306_somi_epilogue": ["q306_somi_epilogue_done"],
}


def load_seed_data():
    """Load seed data to get valid quest_keys and their stage_keys."""
    with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    quests = {}
    for q in data["quests"]:
        quests[q["quest_key"]] = {
            "name": q["name"],
            "category": q.get("category", ""),
            "stages": {s["stage_key"]: s["name"] for s in q.get("stages", [])},
        }
    return quests


def detect_playthrough_id(save_path, metadata):
    """Derive a playthrough identifier from save metadata.

    CP2077 doesn't have per-character folders like DA:O, so we use
    lifepath as the playthrough identifier. Falls back to 'V' if
    lifepath is unavailable.
    """
    lifepath = metadata.get("lifePath", "").strip()
    if lifepath:
        return lifepath
    return "V"


def determine_stage_completion(quest_key, stage_keys, quest_facts, quest_finished):
    """Determine which stages of a quest are completed based on FactsDB facts.

    Uses multiple signals:
    1. Direct: '{stage_key}_done' fact with value > 0
    2. Parent done: if stage_key == quest_key, check '{quest_key}_done'
    3. Sequential inference: if a later stage has _active/_started facts,
       all preceding stages are marked completed
    4. Quest finished: if the parent quest is finished (from metadata or
       _done fact), all stages are marked completed
    """
    if quest_finished:
        return [{"stage_key": sk, "completed": True} for sk in stage_keys]

    # First pass: check _done facts per stage
    stage_done = {}
    for stage_key in stage_keys:
        done = False

        # Check manual mapping first
        if stage_key in STAGE_DONE_FACTS:
            for fact_name in STAGE_DONE_FACTS[stage_key]:
                if quest_facts.get(fact_name, 0) > 0:
                    done = True
                    break
        # Default: check {stage_key}_done
        elif quest_facts.get(f"{stage_key}_done", 0) > 0:
            done = True
        # If stage_key == parent quest_key, check parent's _done
        elif stage_key == quest_key and quest_facts.get(f"{quest_key}_done", 0) > 0:
            done = True

        stage_done[stage_key] = done

    # Second pass: sequential inference — if a stage has _active or _started
    # facts, all prior stages in the list are completed
    highest_active_idx = -1
    for i, stage_key in enumerate(stage_keys):
        for fact_name, val in quest_facts.items():
            if val <= 0:
                continue
            if fact_name.startswith(f"{stage_key}_") and (
                "_active" in fact_name or "_started" in fact_name
            ):
                highest_active_idx = max(highest_active_idx, i)
                break

    # Mark all stages before the active one as completed
    for i in range(highest_active_idx):
        stage_done[stage_keys[i]] = True

    return [
        {"stage_key": sk, "completed": stage_done[sk]}
        for sk in stage_keys
    ]


def build_sync_payload(save_path, username="default", playthrough_name=None):
    """Build the full sync API payload from a CP2077 save folder.

    Parses the save file, loads seed data for quest/stage validation,
    and produces a payload matching the SyncRequest schema.
    """
    result = parse_save(save_path)
    parsed_quests = result["quests"]
    save_info = result["save_info"]
    seed_quests = load_seed_data()

    # Derive playthrough ID from metadata
    metadata = {
        "lifePath": save_info.get("lifepath", ""),
    }
    if playthrough_name is None:
        playthrough_name = detect_playthrough_id(save_path, metadata)

    # Build display name with more context
    level = save_info.get("level", 0)
    lifepath = save_info.get("lifepath", "Unknown")
    display_name = f"{lifepath} V (Level {level})" if level else f"{lifepath} V"

    # Map parsed quest states to sync format, only including quests
    # that exist in our seed data
    active_quests = []
    for quest_key, seed_info in seed_quests.items():
        parsed = parsed_quests.get(quest_key)
        if parsed is None:
            continue

        status = parsed["state"]
        if status == "unstarted":
            continue

        quest_entry = {
            "quest_key": quest_key,
            "status": status,
            "stages": [],
        }

        # If seed data defines stages for this quest, determine completion
        if seed_info["stages"]:
            stage_keys = list(seed_info["stages"].keys())
            quest_facts = parsed.get("facts", {})
            quest_entry["stages"] = determine_stage_completion(
                quest_key, stage_keys, quest_facts,
                quest_finished=(status == "finished"),
            )

        active_quests.append(quest_entry)

    return {
        "username": username,
        "game_slug": "cyberpunk2077",
        "playthrough": {
            "external_id": playthrough_name,
            "name": display_name,
        },
        "quests": active_quests,
    }


def find_latest_save(save_dir=None):
    """Find the most recently modified save folder."""
    saves = find_saves(save_dir)
    if not saves:
        return None

    # Sort by sav.dat modification time, newest first
    def mtime(s):
        sav = Path(s["path"]) / "sav.dat"
        try:
            return sav.stat().st_mtime
        except OSError:
            return 0

    saves.sort(key=mtime, reverse=True)
    return saves[0]["path"]


def main():
    parser = argparse.ArgumentParser(
        description="Extract CP2077 save data for RPG Scribe"
    )
    parser.add_argument(
        "save_path", nargs="?",
        help="Path to save folder (containing sav.dat). "
             "If omitted, uses the most recent save.",
    )
    parser.add_argument("--list", action="store_true", help="List available saves")
    parser.add_argument("--username", default="default", help="Username for sync")
    parser.add_argument(
        "--playthrough",
        help="Override playthrough name (default: auto-detect from lifepath)",
    )
    parser.add_argument(
        "--server",
        help="Server URL (e.g. http://localhost:8081). If set, POSTs the payload.",
    )
    parser.add_argument("--api-key", default="", help="API key")
    parser.add_argument(
        "--save-dir",
        help="Override the default save directory to search",
    )
    args = parser.parse_args()

    save_dir = Path(args.save_dir) if args.save_dir else None

    # List mode
    if args.list:
        saves = find_saves(save_dir)
        if not saves:
            print("No saves found.")
            sys.exit(1)
        print(f"Found {len(saves)} save(s):\n")
        for s in saves:
            ts = s.get("timestamp", "?")
            lv = s.get("level", "?")
            lp = s.get("lifepath", "?")
            fq = len(s.get("finished_quests", []))
            print(f"  {s['name']:<20s}  level={lv:<3}  {lp:<12}  "
                  f"finished={fq:<3}  {ts}")
        sys.exit(0)

    # Resolve save path
    save_path = args.save_path
    if save_path is None:
        save_path = find_latest_save(save_dir)
        if save_path is None:
            print("ERROR: No saves found. Specify a save folder or --save-dir.")
            sys.exit(1)
        print(f"Using latest save: {save_path}")

    save_path = Path(save_path)
    if not save_path.is_absolute() and save_dir:
        candidate = save_dir / save_path
        if candidate.exists():
            save_path = candidate

    # Build payload
    payload = build_sync_payload(
        save_path,
        username=args.username,
        playthrough_name=args.playthrough,
    )

    if args.server:
        import urllib.request
        url = f"{args.server.rstrip('/')}/api/v1/sync"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": args.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                result = json.loads(body)
                print(f"Synced! Status: {result.get('status', 'ok')}")
                print(f"  Playthrough ID: {result.get('playthrough_id')}")
                print(f"  Quests synced:  {result.get('quests_synced')}")
                print(f"  Stages synced:  {result.get('stages_synced')}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            print(f"ERROR: HTTP {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"ERROR: Could not connect to {url}: {e.reason}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
