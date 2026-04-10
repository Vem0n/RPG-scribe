"""
Dragon Age: Origins save file extractor for RPG Scribe.

Reads a .das save file and outputs JSON matching the /api/v1/sync endpoint format.
Uses pygff from DASaveReader for binary GFF4 parsing.

Usage:
    python extract.py <save_file.das> [--username NAME] [--server URL]

Output (stdout): JSON sync payload
With --server: POSTs directly to the sync endpoint
"""

import sys
import os
import json
import argparse

# Add DASaveReader to path so we can import pygff and choice modules
DASAVEREADER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "DASaveReader")
sys.path.insert(0, DASAVEREADER_DIR)

from pygff.lazy import LazyGFF4
from io import BytesIO

# GFF4 field IDs (from DASaveReader/convert.py)
PLAYER_CHAR = 16002
PLAYER_CHAR_CHAR = 16208
STATS = 16209
STAT_LIST = 16350
STAT_BASE = 16300
STAT_INDEX = 16353
CLASS_INDEX = 27
APPEARANCE = 16320
GENDER = 16322
RACE = 16460
PARTY_LIST = 16003
PLOT_MANAGER = 16400
PLOT_LIST = 16401
PLOT_GUID = 16402
PLOT_FLAGS_1 = 16403
PLOT_FLAGS_2 = 16404
PLOT_FLAGS_3 = 16405
PLOT_FLAGS_4 = 16406


def has_flag(flags, flag_index):
    """Check if a specific bit is set across the four flag fields."""
    f1, f2, f3, f4 = flags
    if flag_index < 32:
        return bool((2 ** flag_index) & f1)
    elif flag_index < 64:
        return bool((2 ** (flag_index - 32)) & f2)
    elif flag_index < 96:
        return bool((2 ** (flag_index - 64)) & f3)
    elif flag_index < 128:
        return bool((2 ** (flag_index - 96)) & f4)
    return False


def any_flags_set(flags):
    """Check if any flags are set at all."""
    return any(f != 0 for f in flags)


def parse_save(filename):
    """Parse a .das save file and return plot data."""
    import time
    for attempt in range(5):
        try:
            with open(filename, "rb") as f:
                mem = BytesIO(f.read())
            break
        except PermissionError:
            if attempt < 4:
                time.sleep(2)
            else:
                raise
    gff = LazyGFF4(mem)
    data = gff.root

    # Extract plot flags: GUID -> (flags1, flags2, flags3, flags4)
    plots = {}
    quest_list = data[PARTY_LIST][PLOT_MANAGER][PLOT_LIST]
    for quest in quest_list:
        guid = str(quest[PLOT_GUID]).rstrip("\0")
        flags = (
            int(quest[PLOT_FLAGS_1]),
            int(quest[PLOT_FLAGS_2]),
            int(quest[PLOT_FLAGS_3]),
            int(quest[PLOT_FLAGS_4]),
        )
        plots[guid] = flags

    # Extract player info
    player = data[PLAYER_CHAR][PLAYER_CHAR_CHAR]
    race = int(player[RACE])
    gender = int(player[APPEARANCE][GENDER])
    player_class = 0
    for stat in player[STATS][STAT_LIST]:
        if int(stat[STAT_INDEX]) == CLASS_INDEX:
            player_class = int(stat[STAT_BASE])
            break

    return plots, race, gender, player_class


# --- Quest GUID constants (from DASaveReader/choice/quest_guid.py) ---

HERO_ORIGIN = "C9736A91F42440758E570D9ECD796597"
THE_HUNGRY_DESERTER = "F0CCF894E7F844A99BDF263D6DBB618A"
THE_MABARI_HOUND = "208DD668D74C413994BD638732767B64"
BROKEN_CIRCLE = "C232DA078A044178AA9FCBC6E537FA75"
CODEX_IRVING = "AE2F51ECCFCB46C0B145514455F6E0BB"
THE_HIGH_DRAGONS_CHAMPION = "7FD7A773C53142FABAB1BEDED0BED56A"
URN_MAIN = "8B254175421D48E1B47FC915E8750228"
RESCUE_THE_QUEEN = "6A46B80DFEDB44B09219CC6527AFCF76"
A_VILLAGE_UNDER_SIEGE = "EC0948ED98544E25A47CD6790DA71469"
THE_ATTACK_AT_NIGHTFALL = "C8BD51CF3BC0414192BFF6BC6BF8247C"
THE_POSSESSED_CHILD = "245482960AA04DB58C90E40C8354B6B5"
INTO_THE_FADE = "80D1FC2FA12E457896C0F1B64E51EEBC"
A_MISSING_CHILD = "3EE3B5C37C8D4A15B2F62A0AED56AB0F"
LOST_IN_THE_CASTLE = "65518CE61C8C4004970E6A85A9E5127C"
A_STIFF_DRINK = "C114C254A46B441DA2E87FBC35578B41"
CODEX_ISOLDE = "5A434C9E04BA4452921B5D4346A728C1"
NATURE_OF_THE_BEAST = "63DD3FD0AE584D59877B55269963459D"
CAMMENS_LAMENT = "18B66CC3E6E949FE93E85ED237EF934B"
ELORAS_HALLA = "8BFAAEE6FDD344A4932C1BFF152ABE4D"
LOST_TO_THE_CURSE = "7B5C94475ECF428F83E8F548D390EF91"
RARE_IRONBARK = "BE651409871F475E9FC20C48F6FBC8CE"
WOUNDED_IN_THE_FOREST = "AECCCA7FE54A4F28AC2838B15AC39ED6"
A_PARAGON_OF_HER_KIND = "B571814CBBA44127B605740BD5483A69"
ANVIL_OF_THE_VOID = "86FBBD4CB45D47FF885B0B2BB5407D1E"
A_MOTHERS_HOPE = "47DFDD542B48460CBC08E55B9DFA9BBE"
AN_UNLIKELY_SCHOLAR = "3324ED085FC640308F8753382634149E"
NOBLE_HUNTERS = "4D7A6069A935486D879C32F9EABBE770"
OF_NOBLE_BIRTH = "C93EAEA757434D5A893E7D7E2F636F8A"
THE_DEAD_CASTE = "FF482830F073470CACEA04B640C2560F"
THIEF_IN_THE_HOUSE_OF_LEARNING = "2C50728792CD464E82C27F3512C8E511"
THE_CHANT_IN_THE_DEEPS = "6EA7AC67D12B402084CA9905D3815F7D"
ZERLINDAS_WOE = "87AFF6349A0447B485A18D786E58682B"
LOST_TO_THE_MEMORIES = "1CF820951F69492495FBF635A8B0F68E"
PRECIOUS_METALS = "D5ED00AC5DBD4AFE9E9AC5704FCDBA34"
HONOR_BOUND = "DF5250E8C0A34857B3D96A00C74C798B"
TORTURED_NOBLE = "62AA9DB51BFF42C896235BB81033DEAB"
CRIME_WAVE = "5840679048B84D1DB4B1EFA5C3D058F5"
LOST_TEMPLAR = "7AD394C740504135A0D7241EA1B56D31"
HEARING_VOICES = "DD064DD1BFE64C7090ABE68292229296"
FORGOTTEN_VERSES = "51ECED21579443BD95DEF73AF5BBB9C4"
PEARLS_BEFORE_SWINE = "5C301313E4424E56BF1F3C08B065084C"
THE_CRIMSON_OARS = "1486DD45DAED4876B1DEDB749D8E8791"
THE_RANSOM = "C9913BA344A14BF992EA905B2E8D7930"
THE_TRIAL_OF_CROWS = "9AE0BECCF5194FBEA1F70D8BD0B144BA"
ALISTAIRS_FAMILY = "C2935B1B9E60470EAAEF083B012839AE"
LELIANAS_PAST = "919B6591AA754F5E8B871766F25A68AB"
THE_LANDSMEET = "841A4E6E0CDD43D3BA3BA484D9A2771F"
LANDSMEET_ALISTAIR = "587FDF09B1544773A5F15245C403D56D"
CLIMAX_ARCHDEMON = "A5FA53EF3C24463693440319F1D564B2"
PARTY = "25BC6F5E8DA847938245071233433332"
APPROVAL_ALISTAIR = "840C666EA1FE48CBA260AB1FE42FCFA7"
APPROVAL_MORRIGAN = "E8E833AC06C04BF2A3261A7937542D75"
APPROVAL_LELIANA = "E8CEBFA6EB2345EBB704DF06D794C803"
APPROVAL_ZEVRAN = "68F1B23EB3EA42F5B363ABE7FEB86A50"
MORRIGANS_RITUAL = "764C8DAFF2274DFEBC7C7B32FA2BB0CD"
DOG_MAIN = "6C3BF26236154969AF21F87C89944925"
THE_QUNARI_PRISONER = "2B9F3A9F5D024CA794874529BDC6F9B0"
GRAND_CLERIC = "FD98290AFDD34B89B50F8A0404BC9E6E"
STEN_SWORD = "AF48E71C721A4240B4E1FF4FB592C99F"
CHARACTER_OGHREN = "530C45E15B4548A5A41DEC739E1F2B2D"
CHARACTER_ZEVRAN = "1763DEA8045E4B1F911B44E51CA314D1"
FLEMETHS_GRIMOIRE = "70EF42CA62564177AA810FCD09C7AFD4"
SOLDIERS_PEAK = "2F247F5F5B1C41F7845E3D09F20D5144"
CHARACTER_AVERNUS = "14D501EF13CE49559111ED9DC9C44457"
CHARACTER_SOPHIA = "220B96C20A004539812763C4DE5D6C23"
BLOOD_ABILITIES = "0802E25F3C1144A5B59109F27AAE6CA7"
GOLEM = "A8211E73A50347D9B72448F24648064C"
CODEX_SHALE = "45CE5838602B431F96EF7B65D005D2C1"
SHALE_ANVIL = "D6BFE3A3A66E4BEF940DB167A634CD6B"
ARCHITECT = "5BE5FB37A9AB4219BC8380D54E0B7742"
HOWE_FAMILY = "5BEE8FEFF2AC44788A13AD590C96E67A"
FAMILY_MAN = "6F08DC1CF4984FF699D7DC3CAD18B753"
OGHREN_AWK = "D4920BFFC3E24C2FAC5A513AFD87C6DE"
SIEGE_VIGILS_KEEP = "923E283E44DB4F48BA557085F77D1152"
ASSAULT_AMARANTHINE = "1C7395DEAAC14F889A5D41F86854F48B"
MORRIGAN_ELUVIAN = "731EAE9148E94CE3B80B903A24C46E4A"

# --- GUIDs extracted from game data ERF files (designerplots.erf) ---

# Main quests
JOINING_RITUAL = "9C844A3E7568452D9043C9F52CD69283"
TAINTED_BLOOD = "695AB800D2444561A073AB5D03E2CADE"
TOWER_OF_ISHAL = "C698D36371E74CA0B99574F7C5D44CD4"
MAIN_LOTHERING = "DA64053DF18C47628B40B4D68EF0368B"

# Lothering side quests
LOT_BANDITS = "A01ACC433A3B43A68F41EAD86589485D"
LOT_BANDITS2 = "2E07B2B4258F4D40920FEC8A040B4590"
LOT_BEARS = "0FA0FDEED87A443B99AA336A9F3559CF"
LOT_BRYANT = "0F451500C8614793B91DE2ACD6284E5A"
LOT_HERBALISM = "0E7FA0A169D84B82ACF654B68A634001"
LOT_POISON = "30947AFA23D343E4A08119E0F9BAEB81"
LOT_TRAPS = "DDE3604674BC4FE0B8FFED7E21E22C6C"
LOT_LAST_KEEPSAKE = "741BC7A439B34C08A2EE88BBAC177DA9"

# Circle Tower side quests
FIVE_PAGES = "1C029737006946C0B442D0D8E2EEF93B"
SUMMONING_SCIENCES = "80D996E65EA249F3AEAF2389F6BAA4BF"
WATCHGUARD = "A8D5FDA4A1024BBDA5D7EA64E50D3A33"
ASUNDER = "C01337A205E249FCA537F57B03CE7913"

# Brecilian Forest side quests
ELVEN_RITUAL = "B98E2600DCF54239BBF696E2EC30EF1C"
MAGES_TREASURE = "BCF37CD809904B1F82CB2A35F692C7E8"
UNBOUND_REVENANT = "1E5BB3A060114359BE427D9FA36263B3"

# Orzammar side quests
LOST_NUG = "5B284FB773F940F598DAA25CF1B75803"
CAGED_IN_STONE = "04D653DE8E064030BCE5A04F51A2C7CE"
EXOTIC_METHODS = "9B3EB0BF2EE44BAD8DEAA28934EDC4C4"
JAMMERS_STASH = "28F8C171845C42C4A810698A75D0399F"
PROVING_AFTER_DARK = "68F2FEB4AB8F4C63B5F8C513FD30AB42"
KEY_TO_CITY = "72E70FBE55CD41D4BD8B4A97E30EAB05"
TOPSIDER = "27AEDCD8E8B74EF0AD0BFA6471E55346"

# Denerim side quests
ALLEY_JUSTICE = "B97874750637442F8E037B85D0CF04D0"
FAZZILS_REQUEST = "BEE2360A38664B4D8719276A1CB1FB32"
SOMETHING_WICKED = "542BF375DD054B77B515C03678EDA7BA"
MISSING_IN_ACTION = "794804999652451B96529213A952F0C9"
CAPTURED = "FA19CF63C15B4850ACFDD59954C9B853"
FRIENDS_OF_RED_JENNY = "89DEECEEFFB64996BC69816B66E128BC"
DRAGON_SCALE_ARMOR = "747337F836E248F581D0AAC7DD2953D7"
DRAKE_SCALE_ARMOR = "669920C801B14461A28162441DA2DD0F"
LAST_REQUEST = "6C50CC0F842640BF901658F2A615CF2A"

# Chanter's Board
CHANT_CIVIL = "076E5596FE5A4B68B7406B3D16357986"
CHANT_FEED = "8697C3E600744DA79FFE2B124AB5BF8C"
CHANT_REFUGEE = "17BC8062C0BE42348C1694674D75DF85"
CHANT_JOWAN = "600D82BC83054916AB9C2425FA1A6ACB"
CHANT_REMAINS = "92E309BE69834713A261EE61BF3AB5F4"
CHANT_ZOMBIE = "C93252CCC68C4BE399D0620FA6ADB765"
CHANT_TRICK = "1397522DCBE641DCB89F6E144C11D1DE"

# Blackstone Irregulars
BLACK_DESERTERS = "C263C7C3921C4B32BC6017E41F0530B4"
BLACK_GREASE = "E949337BCAA145198F597A5458949754"
BLACK_LEADERSHIP = "5C92AA21BC724948BD0AE82C3A47B7DD"
BLACK_CONDOLENCES = "FC8B5071B6C04B53BDDEB69BCFAD8472"
BLACK_RESTOCK = "2FFE9BE2483B47A2896983F15402629C"
BLACK_QUALITY = "1C0760339E294D09B008AED6C4EFB744"

# Mages Collective
MAGE_BANASTOR = "0482EF04D52A450FABB1A4A983919306"
MAGE_HERBAL = "2182FF84EABB46BE9F3CEEC3A0AF7D03"
MAGE_PLACES = "049F12F9496D4B5685552ECB52CE0415"
MAGE_JUSTICE = "16EC2C0B68C14F7A8AB3A7FBB5FAC4FA"
MAGE_KILLER = "E67D74F9F75E45C38D54DA63C840792D"
MAGE_TERMINATION = "A74B1BC1A14A4B6B90AFA2DAD9E8663A"
MAGE_WARNING = "BE79AF269EB740D29BE263AA5A45781F"
MAGE_WITNESSES = "C69AC07875044F6E828D6E01A7209CFA"
MAGE_DEFYING = "2B4B3024719543DAAFE5F8B13AE84AEF"

# Favors for Certain Interested Parties
ROGUE_BOX = "40E686A87CED4EC48B91122BF032E052"
ROGUE_WITNESS = "6C84C30E67964DB48B3681662A03BC50"
ROGUE_DECISIONS = "659EEE1D01C045F4914F186D77AEBDBD"
ROGUE_NEGOTIATION = "EBA1E99848CB4D3AA5E1F738D9DEFA79"
ROGUE_NEW_GROUND = "5B19D356BD94412C95B4BF8756A1668D"
ROGUE_LETTERS = "EDCBB9E81F6A40AABD9D94A368C6E092"
ROGUE_SOLVING = "77EF3B0C553B448FBCAD7CE8A60DF67F"
ROGUE_PIECES = "051FDE5A2A434334804C2C669E7FFB0D"

# Haven / Urn side quests
TRAIL_SIGNS = "765F44126AB3450BB0643C37CFB1A841"
LAST_WILL = "AD5F88856B354FBEB5BCAA3FC1F6C6C2"
PINCH_OF_ASHES = "78AD390C752941D480CFD5698AB2C5F8"
GENITIVI_MAIN = "8B254175421D48E1B47FC915E8750228"

# Ostagar prologue side quests
WARDENS_CACHE = "A65F3CB634B347CF8B93080425D16544"

# Companion quests
OGHREN_MAIN = "530C45E15B4548A5A41DEC739E1F2B2D"
WYNNE_MAIN = "0F78D9FC6FBD4183A1243DDC1BBE5D01"
SHALE_MAIN = "01C83688F4C74348B5750D77D9338E9B"

# Awakening quests
AWK_RIGHTEOUS_PATH = "B461EA253812468B8F3A99B7D0333D18"
AWK_IT_COMES_BENEATH = "4340AC7298C945EF82CF4AD7BCCE540D"
AWK_LAST_LEGION = "7063104BE78A4947A875ECA25F901D7F"
AWK_BLACKMARSH = "4DB1EB26F35B4FB3BE5F57E642ECA723"
AWK_KAL_HIROL = "0450CC52454D4FF9BF1A737F2200FAB8"
AWK_ANDERS_MAIN = "1BA3C1D88BD4454289459F4B46796804"
AWK_KRISTOFF_MAIN = "78D19D7452684516B3FFAAEF2D670CFE"

# Companion recruitment flags (from PARTY GUID)
RECRUIT_ALISTAIR = 0
RECRUIT_DOG = 1
RECRUIT_LELIANA = 4
RECRUIT_OGHREN = 6
RECRUIT_SHALE = 7
RECRUIT_WYNNE = 8
RECRUIT_ZEVRAN = 9
RECRUIT_LOGHAIN = 10
RECRUIT_STEN = 13

# Romance active flag (same bit across all approval GUIDs)
ROMANCE_ACTIVE = 21


def get_flags(plots, guid):
    """Get flags for a GUID, defaulting to all zeros."""
    return plots.get(guid, (0, 0, 0, 0))


def determine_quest_states(plots, race, gender, player_class):
    """Map plot data to quest states for the sync API.

    Returns a list of quest dicts: {quest_key, status, stages, result_text}
    """
    quests = []

    def q(quest_key, status, stages=None, result_text=""):
        quests.append({
            "quest_key": quest_key,
            "status": status,
            "stages": stages or [],
            "result_text": result_text,
        })

    def stage(key, completed):
        return {"stage_key": key, "completed": completed}

    # --- Hero Origin ---
    hero_flags = get_flags(plots, HERO_ORIGIN)
    origins = {
        0: "Dwarf Commoner", 1: "Dwarf Noble", 5: "City Elf",
        6: "Dalish Elf", 7: "Human Noble", 8: "Circle Mage",
    }
    origin_name = None
    for flag_bit, name in origins.items():
        if has_flag(hero_flags, flag_bit):
            origin_name = name
            break
    if origin_name:
        classes = {1: "Warrior", 2: "Mage", 3: "Rogue"}
        genders = {1: "Male", 2: "Female"}
        races = {1: "Human", 2: "Elf", 3: "Dwarf"}
        detail = f"{origin_name} -- {genders.get(gender, '?')} {races.get(race, '?')} {classes.get(player_class, '?')}"
        q("dao_hero_origin", "finished",
          [stage("origin_determined", True)], detail)
    else:
        q("dao_hero_origin", "unstarted")

    # --- Prologue ---
    deserter_flags = get_flags(plots, THE_HUNGRY_DESERTER)
    # Completion: killed(1), key(5), bribed(6), food(7)
    if has_flag(deserter_flags, 1) or has_flag(deserter_flags, 5) \
            or has_flag(deserter_flags, 6) or has_flag(deserter_flags, 7):
        q("dao_ostagar_deserter", "finished",
          [stage("encountered", True), stage("resolved", True)])
    elif any_flags_set(deserter_flags):
        q("dao_ostagar_deserter", "started", [stage("encountered", True)])
    else:
        q("dao_ostagar_deserter", "unstarted")

    mabari_flags = get_flags(plots, THE_MABARI_HOUND)
    # Completion: healed(4), killed(5)
    if has_flag(mabari_flags, 4) or has_flag(mabari_flags, 5):
        q("dao_ostagar_mabari", "finished",
          [stage("encountered", True), stage("resolved", True)])
    elif any_flags_set(mabari_flags):
        q("dao_ostagar_mabari", "started", [stage("encountered", True)])
    else:
        q("dao_ostagar_mabari", "unstarted")

    cache_flags = get_flags(plots, WARDENS_CACHE)
    if has_flag(cache_flags, 4):  # PRE_CACHE_PLOT_DONE
        q("dao_wardens_cache", "finished", [stage("completed", True)])
    elif any_flags_set(cache_flags):
        q("dao_wardens_cache", "started", [stage("started", True)])

    # --- Broken Circle ---
    circle_flags = get_flags(plots, BROKEN_CIRCLE)
    # Flag 0 = mages supported, Flag 6 = templars supported
    if has_flag(circle_flags, 0) or has_flag(circle_flags, 6):
        result = "Mages supported" if has_flag(circle_flags, 0) else "Templars supported"
        q("dao_broken_circle", "finished",
          [stage("started", True), stage("completed", True)], result)
    elif any_flags_set(circle_flags):
        q("dao_broken_circle", "started", [stage("started", True)])
    else:
        q("dao_broken_circle", "unstarted")

    # Irving fate — only resolved once Broken Circle is done
    irving_flags = get_flags(plots, CODEX_IRVING)
    # Completion: irving_dead(4) or circle quest resolved
    if has_flag(irving_flags, 4) or has_flag(circle_flags, 5) \
            or has_flag(circle_flags, 0) or has_flag(circle_flags, 6):
        survived = not has_flag(irving_flags, 4)
        result = "Irving survived" if survived else "Irving died"
        q("dao_irving_fate", "finished", [stage("resolved", True)], result)
    elif any_flags_set(irving_flags):
        q("dao_irving_fate", "started")
    else:
        q("dao_irving_fate", "unstarted")

    # Cullen's request (uses BROKEN_CIRCLE flag 5)
    if has_flag(circle_flags, 5):
        q("dao_cullens_request", "finished",
          [stage("resolved", True)], "Agreed to Cullen's request")
    elif has_flag(circle_flags, 0) or has_flag(circle_flags, 6):
        q("dao_cullens_request", "finished",
          [stage("resolved", True)], "Did not agree to Cullen's request")
    else:
        q("dao_cullens_request", "unstarted")

    # --- Urn of Sacred Ashes ---
    # Game data: URN_MAIN (plt_urnpt_main.plo) bit 4=URN_PLOT_DONE, bit 35=URN_PLOT_START
    # THE_HIGH_DRAGONS_CHAMPION is the cult subplot, NOT the main quest
    urn_main_flags = get_flags(plots, URN_MAIN)
    urn_cult_flags = get_flags(plots, THE_HIGH_DRAGONS_CHAMPION)
    if has_flag(urn_main_flags, 4):  # URN_PLOT_DONE
        poisoned = has_flag(urn_cult_flags, 8)  # PC_POORS_BLOOD
        result = "Urn poisoned" if poisoned else "Urn preserved"
        q("dao_urn_of_sacred_ashes", "finished",
          [stage("found_urn", True), stage("resolved", True)], result)
    elif has_flag(urn_main_flags, 35) or any_flags_set(urn_main_flags):  # URN_PLOT_START
        q("dao_urn_of_sacred_ashes", "started", [stage("found_urn", True)])
    else:
        q("dao_urn_of_sacred_ashes", "unstarted")

    # --- Redcliffe ---
    siege_flags = get_flags(plots, A_VILLAGE_UNDER_SIEGE)
    if has_flag(siege_flags, 0):
        q("dao_village_siege", "finished",
          [stage("started", True), stage("completed", True)], "Helped Redcliffe prepare")
    elif any_flags_set(siege_flags):
        q("dao_village_siege", "started", [stage("started", True)])
    else:
        q("dao_village_siege", "unstarted")

    nightfall_flags = get_flags(plots, THE_ATTACK_AT_NIGHTFALL)
    if has_flag(nightfall_flags, 0):
        q("dao_attack_nightfall", "finished",
          [stage("started", True), stage("completed", True)], "Helped Redcliffe fight")
    elif any_flags_set(nightfall_flags):
        q("dao_attack_nightfall", "started", [stage("started", True)])
    else:
        q("dao_attack_nightfall", "unstarted")

    connor_flags = get_flags(plots, THE_POSSESSED_CHILD)
    fade_flags = get_flags(plots, INTO_THE_FADE)
    if has_flag(connor_flags, 19):  # Connor freed flag
        result = "Connor alive, not possessed"
        if has_flag(fade_flags, 7) and not has_flag(fade_flags, 17):
            result = "Connor alive, possessed"
        q("dao_possessed_child", "finished",
          [stage("discovered", True), stage("resolved", True)], result)
    elif any_flags_set(connor_flags):
        q("dao_possessed_child", "started", [stage("discovered", True)])
    else:
        q("dao_possessed_child", "unstarted")

    missing_child_flags = get_flags(plots, A_MISSING_CHILD)
    # Game data: bit 21=QUEST_DONE_KAITLYN_GRATEFUL, 22=QUEST_DONE_KAITLYN_FEARFUL, 30=KAITLYN_LEFT_WITH_BEVIN
    if has_flag(missing_child_flags, 21) or has_flag(missing_child_flags, 22) \
            or has_flag(missing_child_flags, 30):
        q("dao_missing_child", "finished", [stage("resolved", True)])
    elif has_flag(missing_child_flags, 2):  # ACCEPTED_QUEST
        q("dao_missing_child", "started")
    elif any_flags_set(missing_child_flags):
        q("dao_missing_child", "started")
    else:
        q("dao_missing_child", "unstarted")

    castle_flags = get_flags(plots, LOST_IN_THE_CASTLE)
    # Game data: bit 4=PLOT_COMPLETE
    if has_flag(castle_flags, 4):
        q("dao_lost_in_castle", "finished", [stage("resolved", True)])
    elif has_flag(castle_flags, 0):  # QUEST_ACCEPTED
        q("dao_lost_in_castle", "started")
    else:
        q("dao_lost_in_castle", "unstarted")

    drink_flags = get_flags(plots, A_STIFF_DRINK)
    # Game data: bit 14=BELLA_IN_CHARGE, 16=BELLA_PAYS_FOR_TAVERN, 9=LLOYD_KILLED, 0=PC_OWNS_TAVERN
    if has_flag(drink_flags, 14) or has_flag(drink_flags, 16) \
            or has_flag(drink_flags, 9) or has_flag(drink_flags, 0):
        q("dao_stiff_drink", "finished", [stage("resolved", True)])
    elif any_flags_set(drink_flags):
        q("dao_stiff_drink", "started")
    else:
        q("dao_stiff_drink", "unstarted")

    # --- Nature of the Beast ---
    nature_flags = get_flags(plots, NATURE_OF_THE_BEAST)
    # Flag 0 = peace, Flag 1 = sided werewolves, Flag 4 = sided elves
    if has_flag(nature_flags, 0):
        q("dao_nature_of_the_beast", "finished",
          [stage("started", True), stage("completed", True)], "Brokered peace")
    elif has_flag(nature_flags, 1):
        q("dao_nature_of_the_beast", "finished",
          [stage("started", True), stage("completed", True)], "Sided with werewolves")
    elif has_flag(nature_flags, 4):
        q("dao_nature_of_the_beast", "finished",
          [stage("started", True), stage("completed", True)], "Sided with elves")
    elif any_flags_set(nature_flags):
        q("dao_nature_of_the_beast", "started", [stage("started", True)])
    else:
        q("dao_nature_of_the_beast", "unstarted")

    cammen_flags = get_flags(plots, CAMMENS_LAMENT)
    # Completion: seduced(2), together(4), broke up(3, 29)
    if has_flag(cammen_flags, 2) or has_flag(cammen_flags, 4) \
            or has_flag(cammen_flags, 3) or has_flag(cammen_flags, 29):
        q("dao_cammens_lament", "finished", [stage("resolved", True)])
    elif any_flags_set(cammen_flags):
        q("dao_cammens_lament", "started")
    else:
        q("dao_cammens_lament", "unstarted")

    halla_flags = get_flags(plots, ELORAS_HALLA)
    # Completion: missing mate found(3), killed(6)
    if has_flag(halla_flags, 3) or has_flag(halla_flags, 6):
        q("dao_eloras_halla", "finished", [stage("resolved", True)])
    elif any_flags_set(halla_flags):
        q("dao_eloras_halla", "started")
    else:
        q("dao_eloras_halla", "unstarted")

    curse_flags = get_flags(plots, LOST_TO_THE_CURSE)
    # Completion: told Athras(3)
    if has_flag(curse_flags, 3):
        q("dao_lost_to_the_curse", "finished", [stage("resolved", True)])
    elif any_flags_set(curse_flags):
        q("dao_lost_to_the_curse", "started")
    else:
        q("dao_lost_to_the_curse", "unstarted")

    ironbark_flags = get_flags(plots, RARE_IRONBARK)
    # Completion: brought(5), brought no crafting(12)
    if has_flag(ironbark_flags, 5) or has_flag(ironbark_flags, 12):
        q("dao_rare_ironbark", "finished", [stage("resolved", True)])
    elif any_flags_set(ironbark_flags):
        q("dao_rare_ironbark", "started")
    else:
        q("dao_rare_ironbark", "unstarted")

    deygan_flags = get_flags(plots, WOUNDED_IN_THE_FOREST)
    # Game data: bit 0=RETURNED_BODY, 1=RETURNED_ALIVE, 10=KILLED_BY_PC, 18=DIED, 28=BODY_LEFT_IN_FOREST
    if has_flag(deygan_flags, 0) or has_flag(deygan_flags, 1) \
            or has_flag(deygan_flags, 10) or has_flag(deygan_flags, 18) \
            or has_flag(deygan_flags, 28):
        q("dao_wounded_in_forest", "finished", [stage("resolved", True)])
    elif has_flag(deygan_flags, 4):  # FOUND_BY_PC
        q("dao_wounded_in_forest", "started")
    else:
        q("dao_wounded_in_forest", "unstarted")

    # --- A Paragon of Her Kind ---
    paragon_flags = get_flags(plots, A_PARAGON_OF_HER_KIND)
    if has_flag(paragon_flags, 0):
        q("dao_paragon_of_her_kind", "finished",
          [stage("started", True), stage("completed", True)], "Harrowmont rules")
    elif has_flag(paragon_flags, 1):
        q("dao_paragon_of_her_kind", "finished",
          [stage("started", True), stage("completed", True)], "Bhelen rules")
    elif any_flags_set(paragon_flags):
        q("dao_paragon_of_her_kind", "started", [stage("started", True)])
    else:
        q("dao_paragon_of_her_kind", "unstarted")

    anvil_flags = get_flags(plots, ANVIL_OF_THE_VOID)
    if has_flag(anvil_flags, 0) or has_flag(anvil_flags, 2) or has_flag(anvil_flags, 1):
        q("dao_anvil_of_the_void", "finished",
          [stage("found", True), stage("resolved", True)])
    elif any_flags_set(anvil_flags):
        q("dao_anvil_of_the_void", "started", [stage("found", True)])
    else:
        q("dao_anvil_of_the_void", "unstarted")

    mothers_hope_flags = get_flags(plots, A_MOTHERS_HOPE)
    # Game data: bit 1=COMPLETED_RUCK_DEAD, 2=FAILED_KILLED_RUCK, 4=FILDA_GOES_TO_DEEPROADS, 11=FAILED_DID_NOT_FIND_RUCK
    if has_flag(mothers_hope_flags, 1) or has_flag(mothers_hope_flags, 4):
        q("dao_mothers_hope", "finished", [stage("resolved", True)])
    elif has_flag(mothers_hope_flags, 2) or has_flag(mothers_hope_flags, 11):
        q("dao_mothers_hope", "finished", [stage("resolved", True)])
    elif has_flag(mothers_hope_flags, 0):  # ACCEPTED
        q("dao_mothers_hope", "started")
    else:
        q("dao_mothers_hope", "unstarted")

    scholar_flags = get_flags(plots, AN_UNLIKELY_SCHOLAR)
    # Game data: bit 2=COMPLETED, 6=REFUSED, 11=FAILED, 14=GREAGOIR_REFUSED
    if has_flag(scholar_flags, 2):
        q("dao_unlikely_scholar", "finished", [stage("resolved", True)])
    elif has_flag(scholar_flags, 6) or has_flag(scholar_flags, 14) \
            or has_flag(scholar_flags, 11):
        q("dao_unlikely_scholar", "finished", [stage("resolved", True)])
    elif has_flag(scholar_flags, 0):  # ACCEPTED
        q("dao_unlikely_scholar", "started")
    else:
        q("dao_unlikely_scholar", "unstarted")

    noble_hunter_flags = get_flags(plots, NOBLE_HUNTERS)
    if any_flags_set(noble_hunter_flags):
        q("dao_noble_hunters", "finished", [stage("resolved", True)])
    else:
        q("dao_noble_hunters", "unstarted")

    noble_birth_flags = get_flags(plots, OF_NOBLE_BIRTH)
    # Completion: complete(2), fail(1)
    if has_flag(noble_birth_flags, 2) or has_flag(noble_birth_flags, 1):
        q("dao_of_noble_birth", "finished", [stage("resolved", True)])
    elif any_flags_set(noble_birth_flags):
        q("dao_of_noble_birth", "started")
    else:
        q("dao_of_noble_birth", "unstarted")

    dead_caste_flags = get_flags(plots, THE_DEAD_CASTE)
    # Game data: bit 2=COMPLETE
    if has_flag(dead_caste_flags, 2):
        q("dao_dead_caste", "finished", [stage("resolved", True)])
    elif has_flag(dead_caste_flags, 1):  # INSIGNIA_OBTAINED
        q("dao_dead_caste", "started")
    else:
        q("dao_dead_caste", "unstarted")

    tome_flags = get_flags(plots, THIEF_IN_THE_HOUSE_OF_LEARNING)
    # Game data: bit 3=COMPLETED_TOME_RETURNED, 4=COMPLETED_TOME_SOLD
    if has_flag(tome_flags, 3) or has_flag(tome_flags, 4):
        q("dao_thief_house_learning", "finished", [stage("resolved", True)])
    elif has_flag(tome_flags, 0):  # ACCEPTED
        q("dao_thief_house_learning", "started")
    else:
        q("dao_thief_house_learning", "unstarted")

    chant_flags = get_flags(plots, THE_CHANT_IN_THE_DEEPS)
    # Game data: bit 1=COMPLETED, 2=FAILED
    if has_flag(chant_flags, 1) or has_flag(chant_flags, 2):
        q("dao_chant_in_deeps", "finished", [stage("resolved", True)])
    else:
        q("dao_chant_in_deeps", "unstarted")

    zerlinda_flags = get_flags(plots, ZERLINDAS_WOE)
    # Game data: bit 3=GONE_TO_CHANTRY, 5=GONE_TO_FAMILY_HAPPY, 12=GONE_TO_SURFACE, 15=FAILED
    if has_flag(zerlinda_flags, 3) or has_flag(zerlinda_flags, 5) \
            or has_flag(zerlinda_flags, 12) or has_flag(zerlinda_flags, 15):
        q("dao_zerlindas_woe", "finished", [stage("resolved", True)])
    elif has_flag(zerlinda_flags, 0) or has_flag(zerlinda_flags, 11):  # ACCEPTED
        q("dao_zerlindas_woe", "started")
    else:
        q("dao_zerlindas_woe", "unstarted")

    memories_flags = get_flags(plots, LOST_TO_THE_MEMORIES)
    # Game data: bit 4=COMPLETED, 5=FAILED
    if has_flag(memories_flags, 4) or has_flag(memories_flags, 5):
        q("dao_lost_to_memories", "finished", [stage("resolved", True)])
    elif has_flag(memories_flags, 0):  # ACCEPTED
        q("dao_lost_to_memories", "started")
    else:
        q("dao_lost_to_memories", "unstarted")

    metals_flags = get_flags(plots, PRECIOUS_METALS)
    # Game data: bit 5=COMPLETED, 9=FAILED
    if has_flag(metals_flags, 5) or has_flag(metals_flags, 9):
        q("dao_precious_metals", "finished", [stage("resolved", True)])
    elif has_flag(metals_flags, 0):  # ACCEPTED
        q("dao_precious_metals", "started")
    else:
        q("dao_precious_metals", "unstarted")

    # --- Denerim side quests ---
    landry_flags = get_flags(plots, HONOR_BOUND)
    # Game data: bit 2=RECONSIDERS (persuaded, quest done without journal entry),
    # bit 6=QUEST_DONE, bit 8=KILLED, bit 12=QUEST_ABORTED
    if has_flag(landry_flags, 6) or has_flag(landry_flags, 12):
        killed = has_flag(landry_flags, 8)
        q("dao_honor_bound", "finished",
          [stage("resolved", True)],
          "Ser Landry killed" if killed else "Ser Landry lives")
    elif has_flag(landry_flags, 2):  # RECONSIDERS = persuaded, walks off
        q("dao_honor_bound", "finished",
          [stage("resolved", True)], "Persuaded Ser Landry to stand down")
    elif has_flag(landry_flags, 0):  # DUEL_ACCEPTED
        q("dao_honor_bound", "started")
    else:
        q("dao_honor_bound", "unstarted")

    oswyn_flags = get_flags(plots, TORTURED_NOBLE)
    # Game data: bit 1=REWARD_GIVEN, 2=ASKED_FOR_NO_REWARD, 3=ABANDONED_QUEST
    if has_flag(oswyn_flags, 1) or has_flag(oswyn_flags, 2):
        q("dao_tortured_noble", "finished", [stage("resolved", True)])
    elif has_flag(oswyn_flags, 0):  # FREED
        q("dao_tortured_noble", "started")
    else:
        q("dao_tortured_noble", "unstarted")

    crime_flags = get_flags(plots, CRIME_WAVE)
    # Game data: bit 9=QUEST_DONE, 19=QUEST_ABORTED
    if has_flag(crime_flags, 9) or has_flag(crime_flags, 19):
        q("dao_crime_wave", "finished", [stage("resolved", True)])
    elif any_flags_set(crime_flags):
        q("dao_crime_wave", "started")
    else:
        q("dao_crime_wave", "unstarted")

    templar_flags = get_flags(plots, LOST_TEMPLAR)
    # Game data: bit 1=REWARD_GIVEN, 2=OFFER_REFUSED, 3=ABANDONED_QUEST
    if has_flag(templar_flags, 1) or has_flag(templar_flags, 2) \
            or has_flag(templar_flags, 3):
        q("dao_lost_templar", "finished", [stage("resolved", True)])
    elif has_flag(templar_flags, 0):  # GAVE_RING
        q("dao_lost_templar", "started")
    else:
        q("dao_lost_templar", "unstarted")

    voices_flags = get_flags(plots, HEARING_VOICES)
    # Game data: bit 1=GAVE_AMULET_TO_BEGGAR
    if has_flag(voices_flags, 1):
        q("dao_hearing_voices", "finished", [stage("resolved", True)])
    elif has_flag(voices_flags, 0):  # FOUND_AMULET
        q("dao_hearing_voices", "started")
    else:
        q("dao_hearing_voices", "unstarted")

    verses_flags = get_flags(plots, FORGOTTEN_VERSES)
    # Game data: bit 6=PLOT_DONE, 7=DIDNT_GIVE_SCROLLS
    if has_flag(verses_flags, 6) or has_flag(verses_flags, 7):
        q("dao_forgotten_verses", "finished", [stage("resolved", True)])
    elif has_flag(verses_flags, 4):  # PC_HAS_LOTHERING_SCROLLS
        q("dao_forgotten_verses", "started")
    elif any_flags_set(verses_flags):
        q("dao_forgotten_verses", "started")
    else:
        q("dao_forgotten_verses", "unstarted")

    pearl_flags = get_flags(plots, PEARLS_BEFORE_SWINE)
    # Game data: bit 5=QUEST_DONE, 8=QUEST_FAILED
    if has_flag(pearl_flags, 5) or has_flag(pearl_flags, 8):
        q("dao_pearls_before_swine", "finished", [stage("resolved", True)])
    elif has_flag(pearl_flags, 0):  # QUEST_ACCEPTED
        q("dao_pearls_before_swine", "started")
    else:
        q("dao_pearls_before_swine", "unstarted")

    oars_flags = get_flags(plots, THE_CRIMSON_OARS)
    # Game data: bit 1=QUEST_DONE, 6=QUEST_FAILED
    if has_flag(oars_flags, 1) or has_flag(oars_flags, 6):
        q("dao_crimson_oars", "finished", [stage("resolved", True)])
    elif has_flag(oars_flags, 0):  # QUEST_ACCEPTED
        q("dao_crimson_oars", "started")
    else:
        q("dao_crimson_oars", "unstarted")

    ransom_flags = get_flags(plots, THE_RANSOM)
    crows_flags = get_flags(plots, THE_TRIAL_OF_CROWS)
    # Completion: killed Ignacio(17) or ransom done(1)
    if has_flag(ransom_flags, 17) or has_flag(ransom_flags, 1):
        q("dao_trial_of_crows", "finished", [stage("resolved", True)])
    elif any_flags_set(crows_flags) or any_flags_set(ransom_flags):
        q("dao_trial_of_crows", "started")
    else:
        q("dao_trial_of_crows", "unstarted")

    goldanna_flags = get_flags(plots, ALISTAIRS_FAMILY)
    # Completion: met Goldanna(12)
    if has_flag(goldanna_flags, 12):
        q("dao_alistairs_family", "finished", [stage("resolved", True)])
    elif any_flags_set(goldanna_flags):
        q("dao_alistairs_family", "started")
    else:
        q("dao_alistairs_family", "unstarted")

    marjolaine_flags = get_flags(plots, LELIANAS_PAST)
    # Completion: killed(10), spared(31)
    if has_flag(marjolaine_flags, 10) or has_flag(marjolaine_flags, 31):
        q("dao_lelianas_past", "finished", [stage("resolved", True)])
    elif any_flags_set(marjolaine_flags):
        q("dao_lelianas_past", "started")
    else:
        q("dao_lelianas_past", "unstarted")

    # --- Rescue the Queen ---
    # Game data: bit 0=QUEST_GIVEN, 21=QUEST_COMPLETE, 22=QUEST_STARTED, 13=HOWE_KILLED
    rescue_flags = get_flags(plots, RESCUE_THE_QUEEN)
    if has_flag(rescue_flags, 21):  # QUEST_COMPLETE
        q("dao_rescue_the_queen", "finished",
          [stage("started", True), stage("howe_killed", has_flag(rescue_flags, 13)), stage("completed", True)])
    elif has_flag(rescue_flags, 22) or has_flag(rescue_flags, 13):  # QUEST_STARTED or HOWE_KILLED
        q("dao_rescue_the_queen", "started", [stage("started", True)])
    elif has_flag(rescue_flags, 0):  # QUEST_GIVEN
        q("dao_rescue_the_queen", "started", [stage("started", True)])
    else:
        q("dao_rescue_the_queen", "unstarted")

    # --- Landsmeet ---
    landsmeet_flags = get_flags(plots, THE_LANDSMEET)
    # Completion: Loghain killed(6) or lives(8)
    if has_flag(landsmeet_flags, 6) or has_flag(landsmeet_flags, 8):
        q("dao_the_landsmeet", "finished",
          [stage("started", True), stage("completed", True)])
    elif any_flags_set(landsmeet_flags):
        q("dao_the_landsmeet", "started", [stage("started", True)])
    else:
        q("dao_the_landsmeet", "unstarted")

    # --- Battle of Denerim ---
    archdemon_flags = get_flags(plots, CLIMAX_ARCHDEMON)
    if has_flag(archdemon_flags, 0) or has_flag(archdemon_flags, 1) or has_flag(archdemon_flags, 2):
        q("dao_battle_of_denerim", "finished",
          [stage("started", True), stage("archdemon_slain", True)])
    elif any_flags_set(archdemon_flags):
        q("dao_battle_of_denerim", "started", [stage("started", True)])
    else:
        q("dao_battle_of_denerim", "unstarted")

    # --- Main quest progression (using GUIDs from game data) ---
    joining_flags = get_flags(plots, JOINING_RITUAL)
    if has_flag(joining_flags, 3):  # PRE_RITUAL_END
        q("dao_joining", "finished", [stage("completed", True)])
    elif any_flags_set(joining_flags):
        q("dao_joining", "started", [stage("started", True)])

    blood_flags = get_flags(plots, TAINTED_BLOOD)
    if has_flag(blood_flags, 2):  # PRE_BLOOD_PLOT_DONE
        q("dao_tainted_blood", "finished", [stage("completed", True)])
    elif any_flags_set(blood_flags):
        q("dao_tainted_blood", "started", [stage("started", True)])

    tower_flags = get_flags(plots, TOWER_OF_ISHAL)
    if has_flag(tower_flags, 2):  # PRE_BEACON_LIT
        q("dao_tower_of_ishal", "finished", [stage("completed", True)])
    elif any_flags_set(tower_flags):
        q("dao_tower_of_ishal", "started", [stage("started", True)])

    lothering_flags = get_flags(plots, MAIN_LOTHERING)
    if has_flag(lothering_flags, 1):  # PC_CROSSED_LOTHERING
        q("dao_lothering", "finished", [stage("completed", True)])
    elif has_flag(lothering_flags, 0):
        q("dao_lothering", "started", [stage("started", True)])

    # Arl of Redcliffe (umbrella quest)
    redcliffe_done = (
        has_flag(siege_flags, 0) and
        has_flag(nightfall_flags, 0) and
        (has_flag(connor_flags, 19) or any_flags_set(connor_flags))
    )
    if redcliffe_done:
        q("dao_arl_of_redcliffe", "finished",
          [stage("started", True), stage("completed", True)])
    elif any_flags_set(siege_flags):
        q("dao_arl_of_redcliffe", "started", [stage("started", True)])

    # --- Companion quests ---
    party_flags = get_flags(plots, PARTY)

    # Romance
    romanced = None
    for guid, name in [
        (APPROVAL_ALISTAIR, "Alistair"), (APPROVAL_MORRIGAN, "Morrigan"),
        (APPROVAL_LELIANA, "Leliana"), (APPROVAL_ZEVRAN, "Zevran"),
    ]:
        if has_flag(get_flags(plots, guid), ROMANCE_ACTIVE):
            romanced = name
            break
    if romanced:
        q("dao_romance", "finished",
          [stage("romanced", True)], f"Romanced {romanced}")
    else:
        q("dao_romance", "unstarted")

    # Dog
    if has_flag(party_flags, RECRUIT_DOG):
        q("dao_recruit_dog", "finished", [stage("recruited", True)], "Recruited Dog")
    else:
        q("dao_recruit_dog", "unstarted")

    # Sten
    sten_flags = get_flags(plots, THE_QUNARI_PRISONER)
    if has_flag(party_flags, RECRUIT_STEN):
        q("dao_qunari_prisoner", "finished",
          [stage("freed", True), stage("recruited", True)], "Recruited Sten")
    elif any_flags_set(sten_flags):
        q("dao_qunari_prisoner", "started", [stage("freed", True)])
    else:
        q("dao_qunari_prisoner", "unstarted")

    sword_flags = get_flags(plots, STEN_SWORD)
    if any_flags_set(sword_flags):
        q("dao_stens_sword", "finished", [stage("resolved", True)])
    else:
        q("dao_stens_sword", "unstarted")

    # Oghren
    if has_flag(party_flags, RECRUIT_OGHREN):
        q("dao_recruit_oghren", "finished", [stage("recruited", True)])
    else:
        q("dao_recruit_oghren", "unstarted")

    # Zevran
    if has_flag(party_flags, RECRUIT_ZEVRAN):
        q("dao_recruit_zevran", "finished", [stage("recruited", True)])
    else:
        q("dao_recruit_zevran", "unstarted")

    # Wynne
    if has_flag(party_flags, RECRUIT_WYNNE):
        q("dao_recruit_wynne", "finished", [stage("recruited", True)])
    else:
        q("dao_recruit_wynne", "unstarted")

    # Leliana
    if has_flag(party_flags, RECRUIT_LELIANA):
        q("dao_recruit_leliana", "finished", [stage("recruited", True)], "Recruited Leliana")

    # Flemeth's Grimoire
    grimoire_flags = get_flags(plots, FLEMETHS_GRIMOIRE)
    if any_flags_set(grimoire_flags):
        q("dao_flemeths_grimoire", "finished", [stage("resolved", True)])
    else:
        q("dao_flemeths_grimoire", "unstarted")

    # Morrigan's Ritual
    ritual_flags = get_flags(plots, MORRIGANS_RITUAL)
    if any_flags_set(ritual_flags):
        q("dao_morrigans_ritual", "finished", [stage("resolved", True)])
    else:
        q("dao_morrigans_ritual", "unstarted")

    # Oghren's Old Flame
    oghren_main_flags = get_flags(plots, OGHREN_MAIN)
    if has_flag(oghren_main_flags, 1):  # GOT_HIS_MOJO_BACK
        q("dao_oghrens_old_flame", "finished", [stage("resolved", True)])
    elif any_flags_set(oghren_main_flags):
        q("dao_oghrens_old_flame", "started", [stage("started", True)])

    # Wynne's Regret
    wynne_main_flags = get_flags(plots, WYNNE_MAIN)
    if has_flag(wynne_main_flags, 3):  # TALKED_TO_ANEIRIN
        q("dao_wynnes_regret", "finished", [stage("resolved", True)])
    elif any_flags_set(wynne_main_flags):
        q("dao_wynnes_regret", "started", [stage("started", True)])

    # --- Lothering side quests (from game data GUIDs) ---
    def simple_quest(quest_key, guid, done_flag=None, started_flag=None):
        """Helper: map a GUID to started/finished.

        started_flag: if set, only this flag (not any_flags_set) means started.
                      Use for board quests where flag 0 is just initialization.
        done_flag: if set, this specific flag means finished.
        """
        flags = get_flags(plots, guid)
        if done_flag is not None and has_flag(flags, done_flag):
            q(quest_key, "finished", [stage("completed", True)])
        elif started_flag is not None and has_flag(flags, started_flag):
            q(quest_key, "started", [stage("started", True)])
        elif started_flag is None and any_flags_set(flags):
            q(quest_key, "finished" if done_flag is None else "started",
              [stage("completed", True)] if done_flag is None else [stage("started", True)])

    simple_quest("dao_bandits_on_road", LOT_BANDITS, 0)  # BANDITS_DONE
    simple_quest("dao_bandits_everywhere", LOT_BANDITS2, 3, started_flag=0)  # flag 5=CHANTER_BOARD, flag 0=ACCEPTED
    simple_quest("dao_when_bears_attack", LOT_BEARS, 1)  # BEARS_KILLED
    simple_quest("dao_fallen_templar", LOT_BRYANT, 0)  # ADDRESSED_TEMPLARS
    simple_quest("dao_more_than_plants", LOT_HERBALISM, 2)  # QUEST_DONE
    simple_quest("dao_poisonous_proposition", LOT_POISON, 2)  # QUEST_COMPLETE
    simple_quest("dao_traps_girls_best_friend", LOT_TRAPS, 3)  # QUEST_DONE
    simple_quest("dao_last_keepsake", LOT_LAST_KEEPSAKE, 2)  # REWARD_GIVEN

    # --- Circle Tower side quests ---
    simple_quest("dao_five_pages_four_mages", FIVE_PAGES, 1)  # COMPLETED
    simple_quest("dao_summoning_sciences", SUMMONING_SCIENCES, 1)  # EXERCISE_ONE_DONE
    simple_quest("dao_watchguard_of_reaching", WATCHGUARD, 2)  # PLOT_CLOSED
    simple_quest("dao_asunder", ASUNDER, 1)  # KEY_COMPLETE

    # --- Brecilian Forest side quests ---
    simple_quest("dao_elven_ritual", ELVEN_RITUAL)
    simple_quest("dao_mages_treasure", MAGES_TREASURE)
    simple_quest("dao_unbound", UNBOUND_REVENANT)

    # Arcane Warrior (learned from phylactery spirit in ruins)
    phylactery_flags = get_flags(plots, MAGES_TREASURE)
    if has_flag(phylactery_flags, 2):  # NTB_PHYLACTERY_PC_TOLD_ABOUT_ARCANE_WARRIOR
        q("dao_arcane_warrior", "finished", [stage("completed", True)])

    # --- Haven / Urn side quests ---
    simple_quest("dao_chasind_trail_signs", TRAIL_SIGNS)
    simple_quest("dao_last_will_and_testament", LAST_WILL, 1)  # LASTWILL_COMPLETE
    simple_quest("dao_pinch_of_ashes", PINCH_OF_ASHES, 0)  # ASH_COMPLETE
    genitivi_flags = get_flags(plots, GENITIVI_MAIN)
    if has_flag(genitivi_flags, 4):  # URN_PLOT_DONE
        q("dao_the_missionary", "finished", [stage("completed", True)])
    elif any_flags_set(genitivi_flags):
        q("dao_the_missionary", "started", [stage("started", True)])

    # --- Orzammar side quests ---
    simple_quest("dao_lost_nug", LOST_NUG, 1)  # PLOT_COMPLETED
    simple_quest("dao_caged_in_stone", CAGED_IN_STONE)
    simple_quest("dao_exotic_methods", EXOTIC_METHODS)
    simple_quest("dao_jammers_stash", JAMMERS_STASH, 1)  # COMPLETE
    simple_quest("dao_proving_after_dark", PROVING_AFTER_DARK, 3)  # FIGHT_WON
    simple_quest("dao_key_to_the_city", KEY_TO_CITY, 1)  # PC_SHOWED_PAPERS
    simple_quest("dao_shapers_life", KEY_TO_CITY)  # Same GUID as Key to City
    simple_quest("dao_admirable_topsider", TOPSIDER, 2)  # SWORD_RETURNED

    # --- Denerim side quests ---
    simple_quest("dao_back_alley_justice", ALLEY_JUSTICE, 3, started_flag=1)  # flag 0=CHANTER_BOARD
    simple_quest("dao_fazzils_request", FAZZILS_REQUEST, 3, started_flag=1)  # flag 0=CHANTER_BOARD
    simple_quest("dao_something_wicked", SOMETHING_WICKED, 1)  # flag 0=OTTO_ASKED (not a board flag)
    simple_quest("dao_missing_in_action", MISSING_IN_ACTION, 3, started_flag=1)  # flag 0=CHANTER_BOARD
    simple_quest("dao_captured", CAPTURED, 0)  # PC_CAPTURED
    simple_quest("dao_friends_of_red_jenny", FRIENDS_OF_RED_JENNY, 1)  # BOX_DELIVERED
    simple_quest("dao_dragon_scale_armor", DRAGON_SCALE_ARMOR)
    simple_quest("dao_drake_scale_armor", DRAKE_SCALE_ARMOR)
    simple_quest("dao_the_last_request", LAST_REQUEST, 2)  # QUEST_DONE

    # --- Chanter's Board (flag 0 = posted on board, flag 1 = accepted) ---
    simple_quest("dao_chanters_brothers_sons", CHANT_CIVIL, 2, started_flag=1)
    simple_quest("dao_chanters_caravan_down", CHANT_FEED, 2, started_flag=1)
    simple_quest("dao_chanters_desperate_haven", CHANT_REFUGEE, 2, started_flag=1)
    simple_quest("dao_chanters_jowans_intention", CHANT_JOWAN, 2, started_flag=1)
    simple_quest("dao_chanters_loghains_push", CHANT_REMAINS, 2, started_flag=1)
    simple_quest("dao_chanters_skin_deep", CHANT_ZOMBIE, 2, started_flag=1)
    simple_quest("dao_chanters_unintended", CHANT_TRICK, 2, started_flag=1)

    # --- Blackstone Irregulars ---
    # Board quests: bit 0 = posted, bit 1 = accepted, bit 2+ = progress/completion
    def board_quest(quest_key, guid, done_min_bit=2):
        """Board quest: finished if any bit >= done_min_bit is set, started if bit 1."""
        flags = get_flags(plots, guid)
        done = any(has_flag(flags, b) for b in range(done_min_bit, 32))
        if done:
            q(quest_key, "finished", [stage("completed", True)])
        elif has_flag(flags, 1) or has_flag(flags, 0):
            q(quest_key, "started", [stage("started", True)])

    board_quest("dao_blackstone_dereliction", BLACK_DESERTERS)
    board_quest("dao_blackstone_grease", BLACK_GREASE)
    board_quest("dao_blackstone_change_leadership", BLACK_LEADERSHIP)
    board_quest("dao_blackstone_notice_death", BLACK_CONDOLENCES)
    board_quest("dao_blackstone_restocking", BLACK_RESTOCK)
    board_quest("dao_blackstone_scraping", BLACK_QUALITY)

    # --- Mages Collective ---
    board_quest("dao_mages_scrolls_banastor", MAGE_BANASTOR)
    board_quest("dao_mages_herbal_magic", MAGE_HERBAL)
    board_quest("dao_mages_places_of_power", MAGE_PLACES)
    board_quest("dao_mages_gift_of_silence", MAGE_JUSTICE)
    board_quest("dao_mages_brothers_killer", MAGE_KILLER)
    board_quest("dao_mages_notice_termination", MAGE_TERMINATION)
    board_quest("dao_mages_blood_warning", MAGE_WARNING)
    board_quest("dao_mages_have_you_seen_me", MAGE_WITNESSES)
    board_quest("dao_mages_careless_accusations", MAGE_DEFYING)

    # --- Favors for Certain Interested Parties ---
    board_quest("dao_favors_dead_drops", ROGUE_BOX)
    board_quest("dao_favors_false_witness", ROGUE_WITNESS)
    board_quest("dao_favors_harsh_decisions", ROGUE_DECISIONS)
    board_quest("dao_favors_negotiation_aids", ROGUE_NEGOTIATION)
    board_quest("dao_favors_new_ground", ROGUE_NEW_GROUND)
    board_quest("dao_favors_signs_safe_passage", ROGUE_LETTERS)
    board_quest("dao_favors_solving_problems", ROGUE_SOLVING)
    board_quest("dao_favors_untraceable", ROGUE_PIECES)

    # --- DLC ---
    # Soldier's Peak / Warden's Keep
    avernus_flags = get_flags(plots, CHARACTER_AVERNUS)
    blood_flags = get_flags(plots, BLOOD_ABILITIES)
    if any_flags_set(avernus_flags) or any_flags_set(blood_flags):
        q("dao_soldiers_peak", "finished", [
            stage("avernus_resolved", any_flags_set(avernus_flags)),
            stage("concoction_decided", any_flags_set(blood_flags)),
        ])
    else:
        q("dao_soldiers_peak", "unstarted")

    # Stone Prisoner
    golem_flags = get_flags(plots, GOLEM)
    shale_recruited = has_flag(party_flags, RECRUIT_SHALE)
    if any_flags_set(golem_flags) or shale_recruited:
        q("dao_stone_prisoner", "finished", [
            stage("amalia_resolved", any_flags_set(golem_flags)),
            stage("shale_recruited", shale_recruited),
        ])
    elif any_flags_set(get_flags(plots, CODEX_SHALE)):
        q("dao_stone_prisoner", "started")
    else:
        q("dao_stone_prisoner", "unstarted")

    # Golem's Memories (Shale's personal quest)
    # Note: SHALE_MAIN flags 7/10/13 are *_EQ_0 init flags, not real progress
    shale_main_flags = get_flags(plots, SHALE_MAIN)
    shale_anvil_flags = get_flags(plots, SHALE_ANVIL)
    if has_flag(shale_main_flags, 1):  # CADASH_SHALE_REMEMBERS_PAST
        q("dao_golems_memories", "finished", [stage("resolved", True)])
    elif has_flag(shale_main_flags, 11) or any_flags_set(shale_anvil_flags):  # CADASH_VISITED
        q("dao_golems_memories", "started", [stage("started", True)])

    # Awakening - Architect
    architect_flags = get_flags(plots, ARCHITECT)
    if any_flags_set(architect_flags):
        q("dao_awakening_architect", "finished", [stage("resolved", True)])

    # Awakening - Assault on Vigil's Keep (opening)
    awk_siege_flags = get_flags(plots, SIEGE_VIGILS_KEEP)
    if any_flags_set(awk_siege_flags):
        q("dao_awakening_assault_keep", "finished", [stage("completed", True)])

    # Awakening - The Siege (final battle)
    amaranthine_flags = get_flags(plots, ASSAULT_AMARANTHINE)
    if has_flag(amaranthine_flags, 7):  # AMARANTHINE_SAVED
        q("dao_awakening_siege", "finished", [stage("resolved", True)])
    elif any_flags_set(amaranthine_flags) or any_flags_set(awk_siege_flags):
        q("dao_awakening_siege", "started")

    # Awakening - The Righteous Path
    righteous_flags = get_flags(plots, AWK_RIGHTEOUS_PATH)
    if has_flag(righteous_flags, 3):  # VELANNA_SECOND_ENCOUNTER
        q("dao_awakening_righteous_path", "finished", [stage("completed", True)])
    elif any_flags_set(righteous_flags):
        q("dao_awakening_righteous_path", "started", [stage("started", True)])

    # Awakening - It Comes From Beneath
    beneath_flags = get_flags(plots, AWK_IT_COMES_BENEATH)
    if has_flag(beneath_flags, 2):  # PLOT_03_COMPLETE
        q("dao_awakening_it_comes_beneath", "finished", [stage("completed", True)])
    elif any_flags_set(beneath_flags):
        q("dao_awakening_it_comes_beneath", "started", [stage("started", True)])

    # Awakening - Last of the Legion
    legion_flags = get_flags(plots, AWK_LAST_LEGION)
    if has_flag(legion_flags, 3):  # QUEST_COMPLETE
        q("dao_awakening_last_legion", "finished", [stage("completed", True)])
    elif any_flags_set(legion_flags):
        q("dao_awakening_last_legion", "started", [stage("started", True)])

    # Awakening - Shadows of the Blackmarsh
    blackmarsh_flags = get_flags(plots, AWK_BLACKMARSH)
    if has_flag(blackmarsh_flags, 4):  # RETURNED_FROM_FADE
        q("dao_awakening_shadows_blackmarsh", "finished", [stage("completed", True)])
    elif any_flags_set(blackmarsh_flags):
        q("dao_awakening_shadows_blackmarsh", "started", [stage("started", True)])

    # Awakening - Depths of Depravity (Kal'Hirol)
    kalhirol_flags = get_flags(plots, AWK_KAL_HIROL)
    if has_flag(kalhirol_flags, 3):  # PLOT_07_COMPLETED (flag 3 in extracted data)
        q("dao_awakening_depths_depravity", "finished", [stage("completed", True)])
    elif any_flags_set(kalhirol_flags):
        q("dao_awakening_depths_depravity", "started", [stage("started", True)])

    # Awakening - Freedom for Anders
    anders_flags = get_flags(plots, AWK_ANDERS_MAIN)
    if has_flag(anders_flags, 2):  # TEMPLARS_HOSTILE (quest progressed significantly)
        q("dao_awakening_freedom_anders", "finished", [stage("resolved", True)])
    elif any_flags_set(anders_flags):
        q("dao_awakening_freedom_anders", "started", [stage("started", True)])

    # Awakening - Justice for Kristoff
    kristoff_flags = get_flags(plots, AWK_KRISTOFF_MAIN)
    if any_flags_set(kristoff_flags):
        q("dao_awakening_justice_kristoff", "finished", [stage("resolved", True)])

    # Awakening - Howe Family (Nathaniel)
    howe_flags = get_flags(plots, HOWE_FAMILY)
    if any_flags_set(howe_flags):
        q("dao_awakening_howe_family", "finished", [stage("resolved", True)])

    # Awakening - Oghren the Family Man
    felsi_flags = get_flags(plots, FAMILY_MAN)
    oghren_awk_flags = get_flags(plots, OGHREN_AWK)
    if any_flags_set(felsi_flags) or any_flags_set(oghren_awk_flags):
        q("dao_awakening_oghren_family", "finished", [stage("resolved", True)])

    # Witch Hunt
    eluvian_flags = get_flags(plots, MORRIGAN_ELUVIAN)
    if any_flags_set(eluvian_flags):
        q("dao_witch_hunt", "finished", [stage("resolved", True)])
    else:
        q("dao_witch_hunt", "unstarted")

    return quests


def detect_playthrough_id(save_path):
    """Derive a playthrough identifier from the save path.

    Uses the character folder name as the external ID since each
    DA:O character has its own folder under Characters/.
    """
    # Path pattern: .../Characters/<name>/Saves/<slot>/<file>.das
    parts = save_path.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part.lower() == "characters" and i + 1 < len(parts):
            return parts[i + 1]
    return "unknown"


def build_sync_payload(save_path, username="default"):
    """Build the full sync API payload from a save file."""
    plots, race, gender, player_class = parse_save(save_path)
    quest_states = determine_quest_states(plots, race, gender, player_class)

    playthrough_name = detect_playthrough_id(save_path)

    # Filter out unstarted quests - only send quests with actual state
    active_quests = []
    for qs in quest_states:
        if qs["status"] == "unstarted":
            continue
        active_quests.append({
            "quest_key": qs["quest_key"],
            "status": qs["status"],
            "stages": qs["stages"],
        })

    return {
        "username": username,
        "game_slug": "dragon_age_origins",
        "playthrough": {
            "external_id": playthrough_name,
            "name": playthrough_name,
        },
        "quests": active_quests,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract DA:O save data for RPG Scribe")
    parser.add_argument("save_file", help="Path to .das save file")
    parser.add_argument("--username", default="default", help="Username for sync")
    parser.add_argument("--server", help="Server URL (e.g. http://localhost:8081)")
    parser.add_argument("--api-key", default="", help="API key")
    args = parser.parse_args()

    save_path = args.save_file
    # If given a non-.das file, look for .das in the same directory
    if os.path.isfile(save_path) and not save_path.endswith(".das"):
        save_path = os.path.dirname(save_path)
    # If given a directory, find the .das file inside it
    if os.path.isdir(save_path):
        das_files = [f for f in os.listdir(save_path) if f.endswith(".das")]
        if das_files:
            save_path = os.path.join(save_path, das_files[0])
        else:
            # Walk up/down to find the most recent .das file
            import glob
            pattern = os.path.join(save_path, "**", "*.das")
            matches = glob.glob(pattern, recursive=True)
            if matches:
                save_path = max(matches, key=os.path.getmtime)
            else:
                print(f"No .das files found in {save_path}", file=sys.stderr)
                sys.exit(1)

    try:
        payload = build_sync_payload(save_path, args.username)
    except Exception as e:
        print(f"Error parsing save: {e}", file=sys.stderr)
        sys.exit(1)

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
        with urllib.request.urlopen(req) as resp:
            print(f"Synced! Status: {resp.status}")
            print(resp.read().decode("utf-8"))
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
