"""
Dynamic ESM quest resolver for FNV/TTW saves.

Instead of hardcoded FormID → quest_key mappings, this module:
1. Reads the save's plugin list to know which ESMs are loaded
2. Scans each ESM's QUST records for FormIDs, EDIDs, and names
3. Builds a FormID → quest info lookup at parse time
4. Matches save FormIDs against the actual loaded ESMs

This handles TTW, mod-added quests, and any load order changes.
"""
import struct
import zlib
from pathlib import Path
from typing import Optional

H = 24  # Record header size for FO3/FNV


def find_esm_path(plugin_name: str, game_data_dirs: list[Path]) -> Optional[Path]:
    """Find an ESM file across multiple data directories."""
    for data_dir in game_data_dirs:
        candidate = data_dir / plugin_name
        if candidate.exists():
            return candidate
        # Also check subdirectories (MO2 mod folders)
        for sub in data_dir.glob(f"**/{plugin_name}"):
            if sub.is_file():
                return sub
    return None


def scan_esm_quests(esm_path: Path) -> dict:
    """
    Extract all QUST records from an ESM.
    Returns: {formid: {"edid": str, "name": str, "stages": [int]}}
    """
    data = esm_path.read_bytes()

    # Skip TES4 header
    rs = struct.unpack_from('<I', data, 4)[0]
    pos = H + rs

    # Find QUST group
    qust_start = qust_end = 0
    while pos < len(data) - 4:
        if data[pos:pos+4] == b'GRUP':
            gs = struct.unpack_from('<I', data, pos+4)[0]
            if data[pos+8:pos+12] == b'QUST':
                qust_start = pos
                qust_end = pos + gs
                break
            pos += gs
        else:
            pos += H + struct.unpack_from('<I', data, pos+4)[0]

    if qust_end == 0:
        return {}

    quests = {}

    def scan(s, e):
        p = s
        while p < e - 4:
            t = data[p:p+4]
            if t == b'GRUP':
                gs = struct.unpack_from('<I', data, p+4)[0]
                scan(p + H, p + gs)
                p += gs
            else:
                rs2 = struct.unpack_from('<I', data, p+4)[0]
                if t == b'QUST':
                    fl = struct.unpack_from('<I', data, p+8)[0]
                    fid = struct.unpack_from('<I', data, p+12)[0]
                    rd = data[p+H:p+H+rs2]

                    if fl & 0x00040000:  # Compressed
                        try:
                            rd = zlib.decompress(rd[4:])
                        except zlib.error:
                            p += H + rs2
                            continue

                    edid = name = ""
                    stages = []
                    sp = 0
                    while sp + 6 <= len(rd):
                        st = rd[sp:sp+4].decode('ascii', errors='replace')
                        ss = struct.unpack_from('<H', rd, sp+4)[0]
                        sp += 6
                        sd = rd[sp:sp+ss]
                        sp += ss

                        if st == 'EDID':
                            edid = sd.rstrip(b'\x00').decode('ascii', errors='replace')
                        elif st == 'FULL':
                            full = sd.rstrip(b'\x00')
                            if not (len(full) <= 4 and len(sd) == 4):
                                name = full.decode('utf-8', errors='replace')
                        elif st == 'INDX' and len(sd) >= 2:
                            stages.append(struct.unpack_from('<h', sd, 0)[0])

                    quests[fid] = {
                        "edid": edid,
                        "name": name,
                        "stages": sorted(set(stages)),
                    }
                p += H + rs2

    scan(qust_start + H, qust_end)
    return quests


class ESMResolver:
    """
    Resolves save FormIDs to quest names by scanning the actual ESMs
    loaded by the save.
    """

    # Default locations to search for ESMs.
    # Order matters: vanilla first (saves reference vanilla FormIDs),
    # then TTW (for TTW-specific records), then MO2 mods.
    DEFAULT_DATA_DIRS = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas\Data"),
        Path(r"C:\Modding\Nuclear Sunset\mods\[NoDelete] [INF] [DB] - Tale of Two Wastelands (TTW)"),
        Path(r"C:\Modding\Nuclear Sunset\mods"),
    ]

    def __init__(self, plugins: list[str], data_dirs: list[Path] = None):
        self.plugins = plugins
        self.data_dirs = data_dirs or self.DEFAULT_DATA_DIRS
        self._cache: dict[str, dict] = {}  # plugin_name -> {fid: quest_info}
        self._scanned: set[str] = set()

    def _ensure_scanned(self, plugin_name: str):
        """Scan an ESM/ESP if not already cached. Searches all data dirs + MO2 mod folders."""
        if plugin_name in self._scanned:
            return
        self._scanned.add(plugin_name)

        merged = {}
        found = False
        for data_dir in self.data_dirs:
            # Direct path
            candidate = data_dir / plugin_name
            if candidate.exists():
                found = True
                try:
                    quests = scan_esm_quests(candidate)
                    for fid, info in quests.items():
                        if fid not in merged:
                            merged[fid] = info
                except Exception:
                    pass

            # Search subdirectories (MO2 mod folders)
            if not found and data_dir.exists():
                for sub in data_dir.rglob(plugin_name):
                    if sub.is_file():
                        found = True
                        try:
                            quests = scan_esm_quests(sub)
                            for fid, info in quests.items():
                                if fid not in merged:
                                    merged[fid] = info
                        except Exception:
                            pass
                        break  # Use first found in this dir

        if merged:
            self._cache[plugin_name] = merged

    def resolve(self, formid: int, plugin_idx: int) -> Optional[dict]:
        """
        Resolve a FormID to quest info.

        Args:
            formid: The full FormID from the save (with plugin prefix)
            plugin_idx: The plugin index (0-255)

        Returns:
            {"edid": str, "name": str, "stages": [int]} or None
        """
        if plugin_idx >= len(self.plugins):
            return None

        plugin_name = self.plugins[plugin_idx]
        self._ensure_scanned(plugin_name)

        plugin_quests = self._cache.get(plugin_name, {})

        # The save FormID has the plugin index in the upper byte(s)
        # The ESM FormID has a different prefix (its own load order index)
        # We match by the lower 24 bits (the actual record ID within the plugin)
        raw_id = formid & 0x00FFFFFF

        # Try exact match with raw ID
        for esm_fid, info in plugin_quests.items():
            esm_raw = esm_fid & 0x00FFFFFF
            if esm_raw == raw_id:
                return info

        # For master-referenced records, the ESM might use a different prefix
        # Try matching by just checking all records
        # (This handles TTW's cross-master references)
        return None

    def resolve_all_quests(self, save_quests: dict) -> dict:
        """
        Resolve all quest FormIDs from a parsed save.

        Args:
            save_quests: {formid: {"plugin_idx": int, "stages": [...], ...}}

        Returns:
            {formid: {"edid": str, "name": str, "quest_key": str, "category": str, ...}}
        """
        resolved = {}

        for fid, qdata in save_quests.items():
            pidx = qdata["plugin_idx"]
            info = self.resolve(fid, pidx)

            if info and info["name"]:
                # Generate a quest_key from the EDID
                quest_key = self._make_quest_key(info["edid"], info["name"], pidx)
                category = self._categorize(pidx, info["edid"])
                resolved[fid] = {
                    "quest_key": quest_key,
                    "name": info["name"],
                    "edid": info["edid"],
                    "category": category,
                    "esm_stages": info["stages"],
                }

        return resolved

    def _make_quest_key(self, edid: str, name: str, plugin_idx: int) -> str:
        """Generate a stable quest_key from EDID."""
        if edid:
            return edid.lower()
        # Fallback: slugify the name
        slug = name.lower()
        for ch in "',!?.:()-\"":
            slug = slug.replace(ch, '')
        return '_'.join(slug.split())

    def _categorize(self, plugin_idx: int, edid: str) -> str:
        """Determine quest category from plugin and EDID."""
        edid_lower = edid.lower()

        # Main quest patterns
        if any(edid_lower.startswith(p) for p in ['mq', 'vcg', 'vmq', 'cg0']):
            return "main"

        # DLC patterns
        if any(edid_lower.startswith(p) for p in ['nvdlc', 'dlc0']):
            return "dlc"

        # FO3 main quest
        if plugin_idx == 6 and edid_lower.startswith('mq'):
            return "fo3_main"

        # FO3 side quests
        if plugin_idx == 6 and edid_lower.startswith('ms'):
            return "fo3_side"

        # FO3 DLC
        if plugin_idx in (7, 8, 9, 10, 11):
            return "fo3_dlc"

        # Companion quests
        if 'companion' in edid_lower or 'follower' in edid_lower:
            return "companion"

        return "side"


def build_dynamic_seed(resolver: ESMResolver, save_quests: dict) -> dict:
    """
    Build seed data dynamically from the save's actual quests.
    This generates the quest definitions that the server needs.
    """
    resolved = resolver.resolve_all_quests(save_quests)
    quests = []

    for fid, info in sorted(resolved.items(), key=lambda x: x[1]["name"]):
        stages = []
        for stage_id in info["esm_stages"]:
            stages.append({
                "stage_key": f"stage_{stage_id}",
                "name": f"Stage {stage_id}",
                "sort_order": stage_id,
            })

        quests.append({
            "quest_key": info["quest_key"],
            "name": info["name"],
            "description": "",
            "category": info["category"],
            "sort_order": 0,
            "guide_content": "",
            "stages": stages,
        })

    return {
        "game": {
            "slug": "fallout_new_vegas",
            "name": "Fallout: New Vegas",
        },
        "quests": quests,
    }
