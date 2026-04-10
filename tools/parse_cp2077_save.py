#!/usr/bin/env python3
"""
Cyberpunk 2077 Save File Parser — Quest Facts Extractor

Parses a CP2077 sav.dat file and extracts quest progress from FactsDB nodes.
Uses the CyberpunkPythonHacks library for save file decompression and node
tree traversal, then reads FactsDB/FactsTable binary structures directly.

Save file location (Windows):
  %USERPROFILE%/Saved Games/CD Projekt Red/Cyberpunk 2077/

Each save folder contains: sav.dat, metadata.9.json, screenshot.png

FactsDB structure (inside questSystem node):
  questSystem
    └── FactsDB
          ├── FactsTable #0  (main quest facts)
          ├── FactsTable #1
          └── ... up to ~10 tables

  FactsTable binary layout:
    node_id(4) + packed_int(count) + hashes(count*4) + values(count*4)
    Hashes and values are parallel uint32 LE arrays.
    Hashes are FNV-1a 32-bit of the fact name string.

Requires:
  - CyberpunkPythonHacks (git submodule or sibling dir)
  - tools/facts.json (hash-to-name mapping from CyberCAT-SimpleGUI)
"""

import json
import struct
import sys
import os
from pathlib import Path

# Add CyberpunkPythonHacks to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "CyberpunkPythonHacks"))

from cp2077save import SaveFile

FACTS_JSON = SCRIPT_DIR / "facts.json"

DEFAULT_SAVE_DIR = Path(
    os.environ.get("USERPROFILE", ""),
    "Saved Games", "CD Projekt Red", "Cyberpunk 2077",
)

# Quest fact prefixes we care about
QUEST_PREFIXES = ("q0", "q1", "q2", "q3", "sq", "mq", "sts_")


# ---------------------------------------------------------------------------
# Binary helpers
# ---------------------------------------------------------------------------

def read_packed_int(data: bytes, offset: int) -> tuple[int, int]:
    """Read a CP2077 packed integer. Returns (value, bytes_consumed)."""
    a = data[offset]
    value = a & 0x3F
    sign = bool(a & 0x80)
    consumed = 1
    if a & 0x40:
        a = data[offset + 1]; consumed = 2
        value |= (a & 0x7F) << 6
        if a & 0x80:
            a = data[offset + 2]; consumed = 3
            value |= (a & 0x7F) << 13
            if a & 0x80:
                a = data[offset + 3]; consumed = 4
                value |= (a & 0x7F) << 20
                if a & 0x80:
                    a = data[offset + 4]; consumed = 5
                    value |= (a & 0xFF) << 27
    return (-value if sign else value), consumed


def fnv1a32(s: str) -> int:
    """FNV-1a 32-bit hash, matching the game's hashing."""
    h = 0x811C9DC5
    for c in s.encode("ascii"):
        h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    return h


# ---------------------------------------------------------------------------
# FactsDB / FactsTable parsing
# ---------------------------------------------------------------------------

def parse_facts_table(data: bytes) -> list[tuple[int, int]]:
    """Parse a single FactsTable node payload.
    Returns list of (hash, value) pairs.
    """
    # Skip 4-byte node ID
    offset = 4
    count, consumed = read_packed_int(data, offset)
    offset += consumed

    if count <= 0:
        return []

    hashes = struct.unpack_from(f"<{count}I", data, offset)
    offset += count * 4
    values = struct.unpack_from(f"<{count}I", data, offset)

    return list(zip(hashes, values))


def extract_facts(save: SaveFile) -> list[tuple[int, int]]:
    """Walk the node tree to find FactsDB -> FactsTable nodes and
    extract all fact (hash, value) pairs.
    """
    ni = save.nodes_info

    # Find the FactsDB node by name
    facts_db_idx = None
    for i, info in enumerate(ni):
        name = info.name.decode() if isinstance(info.name, bytes) else info.name
        if name == "FactsDB":
            facts_db_idx = i
            break

    if facts_db_idx is None:
        raise RuntimeError("FactsDB node not found in save file")

    # Iterate FactsTable children
    all_facts = []
    next_id = ni[facts_db_idx].child
    while next_id is not None:
        info = ni[next_id]
        raw = bytes(save.data[info.offset : info.offset + info.size])
        all_facts.extend(parse_facts_table(raw))
        next_id = info.next

    return all_facts


# ---------------------------------------------------------------------------
# Hash resolution
# ---------------------------------------------------------------------------

def load_facts_map() -> dict[str, str]:
    """Load the hash-to-name mapping from facts.json."""
    with open(FACTS_JSON, "r") as f:
        return json.load(f)


def resolve_facts(
    raw_facts: list[tuple[int, int]],
    facts_map: dict[str, str],
) -> dict[str, int]:
    """Resolve fact hashes to names and return {name: value} dict.
    Only includes facts that have a known name mapping.
    """
    resolved = {}
    for h, v in raw_facts:
        name = facts_map.get(str(h))
        if name is not None:
            resolved[name] = v
    return resolved


# ---------------------------------------------------------------------------
# Quest state derivation
# ---------------------------------------------------------------------------

def extract_quest_id(fact_name: str) -> str | None:
    """Extract the base quest ID from a fact name.

    Quest IDs match what the game uses in metadata.finishedQuests:
        q005_done              -> q005
        q105_04_done           -> q105   (04 is a stage, not a quest)
        sq031_afterlife_done   -> sq031
        sq_q001_wakako_done    -> sq_q001
        mq010_active           -> mq010
        sts_wat_kab_01_done    -> sts_wat_kab_01
        sts_wat_kab_tier_1     -> None   (tier facts are unlock flags, skip)
    """
    # Street stories: sts_[dist]_[subdist]_[num]_suffix
    if fact_name.startswith("sts_"):
        # Skip tier/system facts (sts_*_tier_*, sts_loop_start, etc.)
        if "_tier_" in fact_name or "retaliation" in fact_name or "loop_start" in fact_name:
            return None
        parts = fact_name.split("_")
        # Need at least sts + dist + subdist + number
        for i in range(3, len(parts)):
            if parts[i].isdigit():
                return "_".join(parts[: i + 1])
        return None

    # Special case: sq_q001_* (The Gift, The Gig, The Gun)
    # Three separate prologue quests identified by the third token
    if fact_name.startswith("sq_q"):
        parts = fact_name.split("_")
        known_subs = {"tbug", "wakako", "wilson"}
        if len(parts) >= 3 and parts[2] in known_subs:
            return f"{parts[0]}_{parts[1]}_{parts[2]}"
        # Fallback to two-token ID for quest-level facts (sq_q001_done, etc.)
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1]}"
        return None

    # Main/side/minor quests: the quest ID is just the first token (q005, sq031, mq010)
    # Fact names like q105_04_done have sub-stage numbers — those belong to q105
    parts = fact_name.split("_")
    if len(parts) < 2:
        return None

    return parts[0]


def derive_quest_states(
    facts: dict[str, int],
) -> dict[str, dict]:
    """Derive quest states from resolved facts.

    Returns dict keyed by quest_id:
        {
            "quest_id": {
                "state": "unstarted" | "started" | "finished" | "failed",
                "facts": {fact_name: value, ...}
            }
        }
    """
    # First pass: group facts by quest ID
    quest_facts: dict[str, dict[str, int]] = {}
    for name, value in facts.items():
        if not any(name.startswith(p) for p in QUEST_PREFIXES):
            continue
        qid = extract_quest_id(name)
        if qid is None:
            continue
        quest_facts.setdefault(qid, {})[name] = value

    # Second pass: derive state per quest
    quests = {}
    for qid, qfacts in quest_facts.items():
        state = "unstarted"

        # Check for done/finished/completed indicators
        done_keys = [k for k in qfacts if k.endswith("_done") and not _is_sub_stage(k, qid)]
        active_keys = [k for k in qfacts if k.endswith("_active")]
        started_keys = [k for k in qfacts if k.endswith("_started") and not _is_sub_stage(k, qid)]
        failed_keys = [k for k in qfacts if k.endswith("_failed")]

        # The primary done fact is typically just "{qid}_done"
        primary_done = f"{qid}_done"
        primary_active = f"{qid}_active"
        primary_started = f"{qid}_started"

        if primary_done in qfacts and qfacts[primary_done] > 0:
            state = "finished"
        elif any(qfacts.get(k, 0) > 0 for k in failed_keys):
            state = "failed"
        elif primary_active in qfacts and qfacts[primary_active] > 0:
            state = "started"
        elif primary_started in qfacts and qfacts[primary_started] > 0:
            state = "started"
        elif any(qfacts.get(k, 0) > 0 for k in done_keys):
            # Sub-stages done but no primary done — quest is in progress
            state = "started"
        elif any(qfacts.get(k, 0) > 0 for k in active_keys):
            state = "started"
        elif any(v > 0 for v in qfacts.values()):
            # Any non-zero fact means the quest has been touched
            state = "started"

        quests[qid] = {"state": state, "facts": qfacts}

    return quests


def _is_sub_stage(fact_name: str, quest_id: str) -> bool:
    """Check if a fact is a sub-stage indicator rather than the quest-level one.

    e.g. q105_bd_clue_cup_done is a sub-stage of q105, not the primary done.
         q105_done IS the primary done for q105.
    """
    # Strip the quest_id prefix
    suffix = fact_name[len(quest_id):]
    # Primary facts: {quest_id}_done, {quest_id}_active, {quest_id}_started
    return suffix not in ("_done", "_active", "_started", "_failed")


# ---------------------------------------------------------------------------
# Save file discovery
# ---------------------------------------------------------------------------

def find_saves(save_dir: Path | None = None) -> list[dict]:
    """Find all save folders and return metadata sorted by date (newest first)."""
    if save_dir is None:
        save_dir = DEFAULT_SAVE_DIR

    saves = []
    for item in save_dir.iterdir():
        sav_file = item / "sav.dat"
        meta_file = item / "metadata.9.json"
        if not sav_file.is_file():
            continue

        info = {"name": item.name, "path": str(item)}

        if meta_file.is_file():
            try:
                with open(meta_file, "r") as f:
                    raw_meta = json.load(f)
                meta = raw_meta.get("Data", {}).get("metadata", {})
                info["timestamp"] = meta.get("timestampString", "")
                info["playtime"] = meta.get("playTime", 0)
                info["lifepath"] = meta.get("lifePath", "")
                info["level"] = int(meta.get("level", 0))
                info["difficulty"] = meta.get("difficulty", "")
                info["finished_quests"] = meta.get("finishedQuests", "").split()
            except (json.JSONDecodeError, KeyError):
                pass

        saves.append(info)

    # Sort by name to group types, newest first within each type
    saves.sort(key=lambda s: s["name"])
    return saves


# ---------------------------------------------------------------------------
# Main output
# ---------------------------------------------------------------------------

def load_metadata(save_path: Path) -> dict:
    """Load the metadata.9.json sidecar for a save folder."""
    if save_path.is_file():
        save_path = save_path.parent
    meta_file = save_path / "metadata.9.json"
    if not meta_file.is_file():
        return {}
    try:
        with open(meta_file, "r") as f:
            return json.load(f).get("Data", {}).get("metadata", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def merge_metadata_quests(
    quests: dict[str, dict],
    metadata: dict,
) -> dict[str, dict]:
    """Merge finishedQuests from save metadata into our quest states.

    The metadata.finishedQuests field is the game's authoritative list of
    completed quests. Many gigs (sts_*) and some side quests don't have
    individual _done facts in FactsDB, so this fills the gaps.
    """
    finished_list = metadata.get("finishedQuests", "").split()
    if not finished_list:
        return quests

    for qid in finished_list:
        # Skip NCPD map activities (ma_*)
        if qid.startswith("ma_"):
            continue
        if qid in quests:
            quests[qid]["state"] = "finished"
            quests[qid]["metadata_confirmed"] = True
        else:
            quests[qid] = {
                "state": "finished",
                "facts": {},
                "metadata_confirmed": True,
            }

    return quests


def parse_save(save_path: str | Path) -> dict:
    """Parse a CP2077 save and return structured quest progress.

    Combines two data sources:
    1. FactsDB — quest facts from the binary save (active/started/stage tracking)
    2. metadata.9.json — finishedQuests field (authoritative completion list)

    Returns:
        {
            "save_info": { ... },
            "stats": { ... },
            "quests": {
                "q005": {"state": "finished", "facts": {...}},
                ...
            }
        }
    """
    save_path = Path(save_path)
    save = SaveFile(str(save_path))

    header = save.header
    metadata = load_metadata(save_path)

    save_info = {
        "path": str(save_path),
        "game_version": f"{header.game_ver / 1000:.1f}",
        "save_version": header.save_ver,
        "date": header.date,
        "time": header.time,
        "lifepath": metadata.get("lifePath", ""),
        "level": int(metadata.get("level", 0)),
        "street_cred": int(metadata.get("streetCred", 0)),
        "playtime_seconds": metadata.get("playTime", 0),
        "difficulty": metadata.get("difficulty", ""),
    }

    facts_map = load_facts_map()
    raw_facts = extract_facts(save)
    resolved = resolve_facts(raw_facts, facts_map)

    quest_facts = {
        k: v for k, v in resolved.items()
        if any(k.startswith(p) for p in QUEST_PREFIXES)
    }

    quests = derive_quest_states(resolved)
    quests = merge_metadata_quests(quests, metadata)

    return {
        "save_info": save_info,
        "stats": {
            "total_facts": len(raw_facts),
            "resolved_facts": len(resolved),
            "quest_facts": len(quest_facts),
            "quests_found": len(quests),
        },
        "quests": quests,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse Cyberpunk 2077 save files and extract quest progress"
    )
    parser.add_argument(
        "save_path",
        nargs="?",
        help="Path to a save folder (containing sav.dat) or sav.dat file. "
             "If omitted, lists available saves.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available saves and exit",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON instead of human-readable summary",
    )
    parser.add_argument(
        "--save-dir",
        help="Override the save directory to search",
    )
    args = parser.parse_args()

    save_dir = Path(args.save_dir) if args.save_dir else DEFAULT_SAVE_DIR

    if args.list or args.save_path is None:
        saves = find_saves(save_dir)
        if not saves:
            print(f"No saves found in {save_dir}")
            sys.exit(1)
        print(f"Found {len(saves)} save(s) in {save_dir}:\n")
        for s in saves:
            ts = s.get("timestamp", "?")
            lv = s.get("level", "?")
            lp = s.get("lifepath", "?")
            print(f"  {s['name']:<20s}  level={lv}  lifepath={lp}  {ts}")
        if args.save_path is None:
            sys.exit(0)

    save_path = Path(args.save_path)
    if not save_path.is_absolute():
        # Try relative to save dir
        candidate = save_dir / save_path
        if candidate.exists():
            save_path = candidate

    result = parse_save(save_path)

    if args.json:
        print(json.dumps(result, indent=2))
        sys.exit(0)

    # Human-readable output
    info = result["save_info"]
    stats = result["stats"]
    quests = result["quests"]

    print(f"Save: {info['path']}")
    print(f"Game version: {info['game_version']}  "
          f"Date: {info['date']} {info['time']}")
    print(f"Facts: {stats['total_facts']} total, "
          f"{stats['resolved_facts']} resolved, "
          f"{stats['quest_facts']} quest-related")
    print(f"Quests detected: {stats['quests_found']}")
    print()

    # Group by category
    categories = {
        "Main Quests": [],
        "Side Quests": [],
        "Minor Quests": [],
        "Gigs": [],
    }

    for qid, qdata in sorted(quests.items()):
        if qid.startswith("sts_"):
            categories["Gigs"].append((qid, qdata))
        elif qid.startswith("mq"):
            categories["Minor Quests"].append((qid, qdata))
        elif qid.startswith("sq"):
            categories["Side Quests"].append((qid, qdata))
        else:
            categories["Main Quests"].append((qid, qdata))

    state_icons = {
        "finished": "[x]",
        "started": "[~]",
        "failed": "[!]",
        "unstarted": "[ ]",
    }

    for cat_name, cat_quests in categories.items():
        if not cat_quests:
            continue
        finished = sum(1 for _, q in cat_quests if q["state"] == "finished")
        started = sum(1 for _, q in cat_quests if q["state"] == "started")
        print(f"=== {cat_name} ({finished} done, {started} active, "
              f"{len(cat_quests)} total) ===")
        for qid, qdata in cat_quests:
            icon = state_icons[qdata["state"]]
            print(f"  {icon} {qid}: {qdata['state']}")
        print()


if __name__ == "__main__":
    main()
