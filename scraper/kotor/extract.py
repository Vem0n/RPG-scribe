"""
KOTOR save file extractor for RPG Scribe.

Reads GLOBALVARS.res from a KOTOR save directory and maps global variable
values to journal quest states.

KOTOR quest tracking:
  - Each quest has a Tag (e.g., "k_starforge") that matches a global number variable
  - The variable value is the journal entry ID
  - Journal entries with End=1 are completion states

Usage:
    python extract.py <save_dir> [--username NAME] [--server URL] [--api-key KEY]
"""
import json
import argparse
from pathlib import Path

from explore_save import parse_gff3


def extract_globals(save_dir: Path) -> dict:
    """Extract global variables from GLOBALVARS.res."""
    gv_path = save_dir / "GLOBALVARS.res"
    gff = parse_gff3(gv_path.read_bytes())

    # Boolean names + packed bitfield
    bool_names = [e["Name"] for e in gff.get("CatBoolean", [])]
    bool_bytes = gff.get("ValBoolean", b"")
    booleans = {}
    for i, name in enumerate(bool_names):
        byte_idx = i // 8
        bit_idx = i % 8
        if byte_idx < len(bool_bytes):
            booleans[name] = bool((bool_bytes[byte_idx] >> bit_idx) & 1)

    # Number names + byte values
    num_names = [e["Name"] for e in gff.get("CatNumber", [])]
    num_bytes = gff.get("ValNumber", b"")
    numbers = {}
    for i, name in enumerate(num_names):
        if i < len(num_bytes):
            numbers[name] = num_bytes[i]

    return {"booleans": booleans, "numbers": numbers}


def extract_save_info(save_dir: Path) -> dict:
    """Extract save metadata from savenfo.res."""
    nfo_path = save_dir / "savenfo.res"
    gff = parse_gff3(nfo_path.read_bytes())
    return {
        "save_name": gff.get("SAVEGAMENAME", ""),
        "area_name": gff.get("AREANAME", ""),
        "last_module": gff.get("LASTMODULE", ""),
        "time_played": gff.get("TIMEPLAYED", 0),
        "portrait": gff.get("PORTRAIT0", ""),
    }


def load_journal_data() -> list:
    """Load journal quest definitions from extracted game data."""
    journal_path = Path(__file__).parent / "journal_data.json"
    with open(journal_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_journal_from_partytable(save_dir: Path) -> dict:
    """Extract journal quest states from PARTYTABLE.res JNL_Entries."""
    pt_path = save_dir / "PARTYTABLE.res"
    gff = parse_gff3(pt_path.read_bytes())
    entries = gff.get("JNL_Entries", [])

    # Map: tag -> current state (entry ID)
    journal_state = {}
    for e in entries:
        plot_id = e.get("JNL_PlotID", "")
        state = e.get("JNL_State", 0)
        if plot_id and state > 0:
            journal_state[plot_id.lower()] = state

    return journal_state


# Global variable → journal tag mapping.
# KOTOR scripts set these variables and call AddJournalQuestEntry separately.
# This mapping was built by cross-referencing variable names with quest tags.
GLOBAL_VAR_TO_TAG = {
    # Main quests
    "K_STAR_MAP": "k_starforge",
    "K_CAPTURED_LEV": "lev_captured",
    "STA_GENERATORS": "sta_confront",
    # Taris
    "Tar_Duel": "tar_duelring",
    "Tar_Rukil": "tar_promisedland",
    "Tar_Dia": "tar_diabounty",
    "Tar_BenBount": "tar_bendakbounty",
    "Tar_LargoBoun": "tar_largobounty",
    "Tar_Matrik": "tar_matrik",
    "Tar_SelBoun": "tar_selvenbounty",
    "Tar_Sarna": "tar_party",
    "Tar_Mission": "tar_bastsearch",
    "Tar_Canderous": "tar_meetCand",
    "Tar_JaniceDro": "tar_buydroid",
    "Tar_ZelkaRm": "tar_rakghoulserum",
    "TAR_HENDAR": "tar_infectedoutcasts",
    "TAR_SITHARMORPLOT": "tar_vulkarbase",
    "Tar_YunGend": "tar_rukilapprentice",
    # Dantooine
    "DAN_JEDI_PLOT": "dan_trials",
    "DAN_PLANET_PLOT": "dan_ruins",
    "DAN_MAND_STATE": "dan_raiders",
    "DAN_ROMANCE_PLOT": "dan_romance",
    "DAN_JUHANI_PLOT": "dan_companion",
    "DAN_BOLOOK_STATE": "dan_murder",
    "DAN_ELISE_PLOT": "dan_casus",
    # Tatooine
    "tat_AreaLocator": "tat17_starmap",
    "tat_RaceComplete": "tat17ae_swoopracing",
    "TAT_SWOOP_ACCEL": "tat17ae_swoopracing",
    "tat_WraidHerd": "tat18ac_dragonhunt",
    "tat_GriffCaptive": "tat17aa_jawarescue",
    "tat_AmbushDead": "tat_ambush",
    # Kashyyyk
    "kas_JoleeKatarn": "kas22_starmap",
    "kas_MandalorPlot": "kas25_mandalorians",
    "KAS_RULAN_NPC": "kas24_tachpoaching",
    # Manaan
    "MAN_PLANET_PLOT": "man_planet",
    "MAN_MURDER_PLOT": "man_murder",
    "MAN_MISSING_PLOT": "man_missing",
    # Korriban
    "KOR_SITH_PRESTIGE": "kor35_waysith",
    "KOR_FINAL_TEST": "kor33_findstarmap",
    "KOR_ROGUE_DROID": "kor38_roguedroid",
    "KOR_RENEGADE_DEAL": "kor35_renegadesith",
    "KOR_KEL_DOUBT": "kor25_doubtsith",
    "KOR_BETRAYAL": "kor35_doublecross",
    # Unknown World
    "Unk_Prisoner": "unk_trapped",
    # Ebon Hawk
    "EBO_SASHA_PLOT": "k_pebo_stowaway",
    "EBO_GIZKA_PLOT": "k_pebo_gizkatrouble",
    "EBO_MYSTERY_BOX": "ebo46_unfinishedbusiness",
    # Companions
    "K_SWG_BASTILA": "k_swg_bastilatalk",
    "K_SWG_CARTH": "k_swg_carthtalk",
    "K_SWG_JOLEE": "k_swg_joleetalk",
    "K_SWG_HELENA": "k_swg_helenatalk",
    "G_CAND_PLOT": "k_swg_canderous",
    "G_JUHANI_PLOT": "k_swg_juhani",
    "K_SWG_HK47_FIX": "k_swg_hk47talk",
    "K_XOR_AMBUSH": "k_xor",
    # Genoharadan
    "k_genoharadan": "Genoharadan",
    "k_geno_lorgal": "Geno_Lorgal",
    "k_geno_Ithorak": "Geno_Ithorak",
    "k_geno_Rulan": "Geno_Rulan",
    "k_Geno_Zuulan": "Geno_Zuulan",
    "k_geno_Vorn": "Geno_Vorn",
    # Misc
    "K_MISSBROTH": "k_missbroth",
    "Mis_MissionTalk": "k_missbroth",
    # Additional mappings
    "END_TRASK_DLG": "end_attack",
    "MAN_QUESTION_STATE": "man26_starmap",
    "DAN_MEET_DONE": "dan_council",
    "MAN_LIVEA_STATE": "man_murder",
    "MAN_SELJUD1_STATE": "man_missing",
    "UNK_AREA": "unk_trapped",
    "UNK_PARTYSHOWDOWN": "unk_invis",
    "Lev_Escape": "lev_captured",
    "MAN_INTER_NUM": "Man26ab_swoopraces",
    "tat_QueedleState": "tat17aa_middleman",
    # Korriban side quests
    "KOR_KNOW_ACADEMY": "kor33_enteracademy",
    "KOR33_SHAARDAN": "kor35_aidlashowe",
    "KOR_DANEL": "kor35_findingdustil",
    "KOR_SITH_CODE": "Category000",
    "KOR_PILLARR": "kor37_ajuntapall",
    "KOR_TORT_END": "kor38_hermit",
    "KOR_DUEL_NUM": "kor35_mandalorian",
    # Manaan side quests
    "MAN_ELORAS_DONE": "man_elora",
    "MAN_FIRITHR_DONE": "man_firith",
    "MAN_RODIANF_DONE": "man_gluupor",
    "MAN_GONTOM_DONE": "man_ignus",
    "MAN_CONFESS_DONE": "man_sunry",
    "MAN_MERCD_DONE": "man_merc",
    "man_ManaanRaceState": "Man26ab_swoopraces",
    # Tatooine side quests
    "PTAT_SPN_TUSKAN": "tat17ag_sandbounty",
    "tat_IzizCaptive": "tat17aa_jawarescue",
    "tat_DuneSeaEnc": "tat_ambush",
    "tat_TanisSaved": "tat18aa_tanistrapped",
    # Kashyyyk side quests
    "kas_EmittersOff": "kas24_removepoachers",
    "KAS_HURT_PLOT": "kas23_rorworr",
    "kas_FreyyrDead": "kas23_mainwookplot",
    # Companion/misc
    "K_KALO_BANDON": "k_jagi",
    "Tar_StrongBox": "tar_rancor",
    "Tar_BenChall": "tar_bendakbounty",
    "unk_redvill": "unk_research",
    "Ebo_Sasha_State": "k_pebo_stowaway",
    "Ebon_Vision": "k_ebonhawk",
    "EBO_LURARKA": "ebo_supplies",
    # Droid for Sale
    "tat_JawaCaptive": "tat17ad_buyinghk47",
    # Honest Debt, Signing Nico
    "tat_MissCaptive": "tat17ae_signingnico",
}

# Boolean variables that indicate quest completion.
# These are separate from the number variables.
BOOL_QUEST_DONE = {
    "MAN_ELORAS_DONE": "man_elora",
    "MAN_FIRITHR_DONE": "man_firith",
    "MAN_RODIANF_DONE": "man_gluupor",
    "MAN_GONTOM_DONE": "man_ignus",
    "MAN_CONFESS_DONE": "man_sunry",
    "MAN_MERCD_DONE": "man_merc",
    "MAN_GLUUPEV_DONE": "man_gluupor",
    "MAN_INTERR_DONE": "man_murder",
    "DAN_JUHANI_DONE": "dan_companion",
    "DAN_LEAVE_DONE": "dan_council",
    "KAS_HURT_PLOT": "kas23_rorworr",
    "tat_TanisSaved": "tat18aa_tanistrapped",
    "tat_HunterDead": "tat18ac_dragonhunt",
    "UNK_RAKPLOT": "unk_research",
    "G_Terentanek_Dead": "kor38_hermit",
    "KOR38B_DROID_DEAD": "kor38_roguedroid",
}


# Known max-state values for global variables (from KOTOR script analysis).
# When the variable reaches this value, the quest is complete.
GLOBAL_VAR_DONE_AT = {
    # Main story progression
    "K_STAR_MAP": 50,          # all 5 star maps (10 each)
    "K_CAPTURED_LEV": 10,      # Leviathan captured
    "STA_GENERATORS": 6,       # Star Forge generators
    # Taris
    "Tar_Duel": 7,             # all arena duels done
    "Tar_Rukil": 40,           # Promised Land journals found
    "Tar_Dia": 99,             # bounty done
    "Tar_BenBount": 99,        # bounty done
    "Tar_LargoBoun": 99,       # bounty done
    "Tar_Matrik": 99,          # bounty done
    "Tar_SelBoun": 99,         # bounty done
    "Tar_Sarna": 99,           # party done
    "Tar_Mission": 30,         # Search for Bastila progressed
    "Tar_Canderous": 2,        # met Canderous
    "Tar_JaniceDro": 30,       # droid purchased
    "Tar_ZelkaRm": 99,         # serum quest done
    "Tar_Hendar": 99,          # outcasts done
    "TAR_SITHARMORPLOT": 2,    # vulkar base infiltrated
    "Tar_YunGend": 99,         # apprentice quest done
    # Dantooine
    "DAN_JEDI_PLOT": 7,        # Jedi training complete
    "DAN_PLANET_PLOT": 3,      # ruins investigated, star map found
    "DAN_MAND_STATE": 5,       # Mandalorian raiders dealt with
    "DAN_ROMANCE_PLOT": 4,     # Sandral-Matale feud resolved
    "DAN_JUHANI_PLOT": 3,      # Juhani quest resolved
    "DAN_BOLOOK_STATE": 5,     # murder investigation done
    "DAN_ELISE_PLOT": 6,       # dead settler resolved
    # Tatooine
    "tat_AreaLocator": 4,      # star map found
    "tat_RaceComplete": 3,     # swoop races done
    "tat_WraidHerd": 2,        # krayt dragon area reached
    "tat_GriffCaptive": 3,     # Jawa rescue progressed
    "tat_AmbushDead": 12,      # ambush dealt with
    # Kashyyyk
    "kas_JoleeKatarn": 4,      # star map found
    "kas_MandalorPlot": 2,     # Mandalorians dealt with
    "KAS_RULAN_NPC": 3,        # tach poaching dealt with
    # Manaan
    "MAN_PLANET_PLOT": 3,      # star map found
    "MAN_MURDER_PLOT": 5,      # trial done
    "MAN_MISSING_PLOT": 4,     # missing selkath found
    # Korriban
    "KOR_SITH_PRESTIGE": 5,    # enough prestige (>=5)
    "KOR_FINAL_TEST": 6,       # star map found
    "KOR_ROGUE_DROID": 2,      # droid quest done
    "KOR_RENEGADE_DEAL": 3,    # renegade sith done
    "KOR_KEL_DOUBT": 5,        # doubting sith resolved
    "KOR_BETRAYAL": 2,         # double-cross done
    # Unknown World
    "Unk_Prisoner": 3,         # temple quest progressed
    # Ebon Hawk
    "EBO_SASHA_PLOT": 2,       # stowaway resolved
    "EBO_GIZKA_PLOT": 1,       # gizka quest started (only 1 = active)
    "EBO_MYSTERY_BOX": 99,     # unfinished business done
    # Companions (high values = full dialogue tree exhausted)
    "K_SWG_BASTILA": 13,       # Bastila talks done
    "K_SWG_CARTH": 99,         # Carth talks done
    "K_SWG_JOLEE": 5,          # Jolee talks done
    "K_SWG_HELENA": 5,         # Helena quest done
    "G_CAND_PLOT": 3,          # Canderous talks done
    "G_JUHANI_PLOT": 4,        # Juhani talks done
    "K_SWG_HK47_FIX": 1,      # HK-47 repaired (1 = done)
    "K_XOR_AMBUSH": 3,         # Xor dealt with
    # Genoharadan
    "k_genoharadan": 70,       # Genoharadan questline done
    "k_geno_lorgal": 99,
    "k_geno_Ithorak": 99,
    "k_geno_Rulan": 99,
    "k_Geno_Zuulan": 99,
    "k_geno_Vorn": 99,
    # Misc
    "Mis_MissionTalk": 99,     # Mission's Brother done
}

# Some quests are guaranteed done once game reaches certain milestones.
MILESTONE_QUESTS = {
    # If K_STAR_MAP >= 10 (at least one star map), Dantooine is done:
    ("K_STAR_MAP", 10): [
        "dan_council",
    ],
    # If K_STAR_MAP >= 50 (all maps), these star map quests are done:
    ("K_STAR_MAP", 50): [
        "dan_ruins", "kor33_findstarmap", "man26_starmap",
        "tat17_starmap", "kas22_starmap",
    ],
    # If at Star Forge (K_CURRENT_PLANET >= 50), early game quests are done:
    ("K_CURRENT_PLANET", 50): [
        "end_attack", "tar_escape", "tar_bastsearch", "tar_meetcand",
        "tar_vulkarbase", "dan_trials", "dan_council", "lev_captured",
        "unk_trapped",
    ],
}

# Extra done-at values for newly added variables
GLOBAL_VAR_DONE_AT.update({
    "END_TRASK_DLG": 32,
    "MAN_QUESTION_STATE": 6,
    "DAN_MEET_DONE": 1,       # boolean-like
    "MAN_LIVEA_STATE": 2,
    "MAN_SELJUD1_STATE": 5,
    "UNK_AREA": 13,
    "UNK_PARTYSHOWDOWN": 2,
    "Lev_Escape": 6,
    "MAN_INTER_NUM": 1,
    "tat_QueedleState": 1,
    # Korriban
    "KOR_KNOW_ACADEMY": 1,
    "KOR33_SHAARDAN": 5,
    "KOR_DANEL": 1,
    "KOR_SITH_CODE": 2,
    "KOR_PILLARR": 24,
    "KOR_TORT_END": 4,
    "KOR_DUEL_NUM": 3,
    # Tatooine
    "PTAT_SPN_TUSKAN": 6,
    "tat_IzizCaptive": 3,
    "tat_DuneSeaEnc": 3,
    "tat_JawaCaptive": 3,
    "tat_MissCaptive": 3,
    # Kashyyyk
    "kas_EmittersOff": 2,
    # Misc
    "Tar_StrongBox": 3,
    "Tar_BenChall": 20,
    "Ebo_Sasha_State": 99,
    "Ebon_Vision": 99,
    "EBO_LURARKA": 5,
    "man_ManaanRaceState": 3,
    "unk_redvill": 1,
    "K_KALO_BANDON": 40,
    "TAR_HENDAR": 99,
})


def _is_quest_done_by_global(tag_lower: str, var_value: int, numbers: dict) -> bool:
    """Determine if a quest is complete based on its global variable value."""
    # Check milestone-based completion
    for (milestone_var, threshold), quest_tags in MILESTONE_QUESTS.items():
        if tag_lower in quest_tags:
            if numbers.get(milestone_var, 0) >= threshold:
                return True

    # Check if the variable reached its known done-state
    for var_name, tag in GLOBAL_VAR_TO_TAG.items():
        if tag.lower() == tag_lower:
            done_val = GLOBAL_VAR_DONE_AT.get(var_name)
            if done_val is not None and var_value >= done_val:
                return True
            break

    # Fallback: 99+ is almost always "done" in KOTOR scripts
    if var_value >= 99:
        return True

    return False


def determine_quest_states(numbers: dict, booleans: dict,
                           journal_state: dict, journal: list) -> list:
    """Map global variables + PARTYTABLE journal to quest states.

    KOTOR quest state comes from two sources:
    1. PARTYTABLE JNL_Entries: exact journal entry IDs (reliable but only keeps ~14 recent)
    2. Global variables: internal script state values (NOT journal entry IDs!)
       These indicate quest progress but values don't map to entry IDs.
       We use them only as "quest was active" indicators with heuristic completion detection.
    """
    tag_to_quest = {q["tag"].lower(): q for q in journal}
    quest_results = {}  # tag_lower -> {"state": int, "source": str}

    # 1. PARTYTABLE journal entries (exact journal entry IDs)
    for tag_lower, state in journal_state.items():
        quest_results[tag_lower] = {"state": state, "source": "partytable"}

    # 2. Global number variables — detect quest involvement and likely completion
    # Variable values are NOT journal entry IDs. They're internal state counters.
    for var_name, tag in GLOBAL_VAR_TO_TAG.items():
        tag_lower = tag.lower()
        if tag_lower in quest_results:
            continue
        val = numbers.get(var_name, 0)
        if val == 0:
            # Check if this var is also a boolean (some _DONE vars are in both maps)
            if booleans.get(var_name, False):
                quest_results[tag_lower] = {"state": 99, "source": "global"}
            continue
        quest_results[tag_lower] = {"state": val, "source": "global"}

    # 3. Boolean completion markers (_DONE flags)
    for var_name, tag in BOOL_QUEST_DONE.items():
        tag_lower = tag.lower()
        if tag_lower in quest_results:
            continue
        if booleans.get(var_name, False):
            quest_results[tag_lower] = {"state": 99, "source": "global"}

    # Build output
    quests = []
    for tag_lower, info in quest_results.items():
        quest = tag_to_quest.get(tag_lower)
        if not quest:
            continue

        entries = quest["entries"]
        end_ids = {e["id"] for e in entries if e["end"]}
        state_value = info["state"]
        source = info["source"]

        if source == "partytable":
            # PARTYTABLE values ARE journal entry IDs — use directly
            if state_value in end_ids:
                status = "finished"
            else:
                status = "started"

            # KOTOR quests have branching paths — entries at same level are
            # mutually exclusive (e.g., "killed Freyyr" vs "saved Freyyr").
            # Only mark an entry completed if:
            #   1. It IS the current entry, OR
            #   2. It has a lower ID AND is not itself an END entry
            #      (END entries at lower IDs are alternative branch endings)
            stages = []
            for entry in sorted(entries, key=lambda e: e["id"]):
                eid = entry["id"]
                if eid == state_value:
                    completed = True
                elif eid < state_value and not entry["end"]:
                    completed = True
                else:
                    completed = False
                stages.append({
                    "stage_key": f"entry_{eid}",
                    "completed": completed,
                })
        else:
            # Global variable — value is NOT a journal entry ID.
            # Use known max-state values per variable to determine completion.
            is_done = _is_quest_done_by_global(tag_lower, state_value, numbers)
            if is_done:
                status = "finished"
                # Mark non-END entries as completed, but for END entries
                # only mark the highest one (we don't know which branch was taken,
                # but the highest END entry is the most likely actual ending)
                sorted_entries = sorted(entries, key=lambda e: e["id"])
                end_entry_ids = sorted([e["id"] for e in entries if e["end"]])
                highest_end = end_entry_ids[-1] if end_entry_ids else None
                stages = []
                for entry in sorted_entries:
                    if not entry["end"]:
                        stages.append({"stage_key": f"entry_{entry['id']}", "completed": True})
                    elif entry["id"] == highest_end:
                        stages.append({"stage_key": f"entry_{entry['id']}", "completed": True})
                    else:
                        stages.append({"stage_key": f"entry_{entry['id']}", "completed": False})
            else:
                status = "started"
                stages = []
                for i, entry in enumerate(sorted(entries, key=lambda e: e["id"])):
                    stages.append({
                        "stage_key": f"entry_{entry['id']}",
                        "completed": i == 0,
                    })

        quests.append({
            "quest_key": quest["tag"].lower(),
            "status": status,
            "stages": stages,
        })

    return quests


def build_sync_payload(save_dir: Path, username: str = "default") -> dict:
    """Build the full sync payload for the server."""
    save_info = extract_save_info(save_dir)
    globals_data = extract_globals(save_dir)
    journal = load_journal_data()

    journal_state = extract_journal_from_partytable(save_dir)
    quest_states = determine_quest_states(
        globals_data["numbers"], globals_data["booleans"],
        journal_state, journal,
    )

    # Playthrough ID from save name or area
    playthrough_name = save_info.get("save_name", "")
    if not playthrough_name:
        playthrough_name = save_dir.name

    return {
        "username": username,
        "game_slug": "kotor",
        "playthrough": {
            "external_id": playthrough_name,
            "name": playthrough_name,
        },
        "quests": quest_states,
    }


def main():
    parser = argparse.ArgumentParser(description="KOTOR save extractor for RPG Scribe")
    parser.add_argument("save_dir", help="Path to KOTOR save directory")
    parser.add_argument("--username", default="default")
    parser.add_argument("--server", help="Server URL to POST to")
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()

    save_dir = Path(args.save_dir)
    if not (save_dir / "GLOBALVARS.res").exists():
        print(f"ERROR: {save_dir / 'GLOBALVARS.res'} not found")
        return

    payload = build_sync_payload(save_dir, args.username)

    started = sum(1 for q in payload["quests"] if q["status"] == "started")
    finished = sum(1 for q in payload["quests"] if q["status"] == "finished")
    total_stages = sum(len(q["stages"]) for q in payload["quests"])
    print(f"Quests: {started} started, {finished} finished ({started + finished} total)")
    print(f"Stages: {total_stages}")

    if args.server:
        import urllib.request
        url = f"{args.server}/api/v1/sync"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": args.api_key,
            },
        )
        resp = urllib.request.urlopen(req)
        print(f"Synced! Status: {resp.status}")
        print(resp.read().decode())
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
