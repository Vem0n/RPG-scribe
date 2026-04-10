#!/usr/bin/env python3
"""
Fallout: New Vegas save file extractor for RPG Scribe.

Reads a .fos save file and outputs JSON matching the /api/v1/sync endpoint
format. Parses the pipe-delimited binary format to extract quest stage
completion data from QUST change form records.

Usage:
    python extract.py [save_file.fos]           # print sync JSON to stdout
    python extract.py --server http://localhost:8081  # POST to server
    python extract.py --list                    # list available saves

Output (stdout): JSON sync payload
With --server: POSTs directly to the sync endpoint
"""

import sys
import json
import struct
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SEED_DATA_PATH = PROJECT_ROOT / "seed-data" / "fallout_new_vegas.json"

DEFAULT_SAVE_DIR = Path.home() / "Documents" / "my games" / "FalloutNV" / "Saves"

# --- Import save parsing functions ---
from explore_save import (
    parse_header,
    parse_plugins,
    parse_file_location_table,
    parse_change_form,
)

# =====================================================================
# Constants
# =====================================================================
QUST_CHANGE_TYPE = 9

CHANGE_FORM_FLAGS         = 0x00000001
CHANGE_QUEST_FLAGS        = 0x00000002
CHANGE_QUEST_SCRIPT_DELAY = 0x00000004
CHANGE_QUEST_OBJECTIVES   = 0x20000000
CHANGE_QUEST_SCRIPT       = 0x40000000
CHANGE_QUEST_STAGES       = 0x80000000


# =====================================================================
# FormID → quest_key mapping
# Maps FalloutNV.esm FormIDs to seed data quest_keys.
# Includes BOTH vanilla ESM FormIDs and TTW-remapped FormIDs.
# =====================================================================
FORMID_TO_QUEST_KEY = {
    # --- FalloutNV.esm ---
    0x00080664: "come_fly_with_me",  # Come Fly With Me
    0x000810E2: "repconn_generic_ghoul_banter",  # REPCONN Generic Ghoul Banter
    0x000842DD: "they_went_thataway",  # They Went That-a-Way
    0x0008D0E3: "i_fought_the_law",  # I Fought the Law
    0x000C6E93: "waterbeggars",  # WaterBeggars
    0x000E282D: "that_lucky_old_sun",  # That Lucky Old Sun
    0x000E37E7: "dont_make_a_beggar_of_me",  # Don't Make a Beggar of Me
    0x000E790F: "i_put_a_spell_on_you",  # I Put a Spell on You
    0x000E8F7D: "the_legend_of_the_star",  # The Legend of the Star
    0x000E8FA0: "variables_for_the_white_wash",  # Variables for The White Wash
    0x000ED567: "wild_wasteland",  # Wild Wasteland
    0x000EDB37: "you_can_depend_on_me",  # You Can Depend on Me
    0x000EFB3B: "there_stands_the_grass",  # There Stands the Grass
    0x000F0629: "the_white_wash",  # The White Wash
    0x000F81BD: "threecard_bounty",  # Three-Card Bounty
    0x000F8892: "the_coyotes",  # The Coyotes
    0x000FF5DF: "volare",  # Volare!
    0x00102037: "welcome_to_fabulous_new_vegas",  # Welcome To Fabulous New Vegas
    0x00104C1C: "aint_that_a_kick_in_the_head",  # Ain't That a Kick in the Head
    0x00104EAE: "ghost_town_gunfight",  # Ghost Town Gunfight
    0x00105998: "a_valuable_lesson",  # A Valuable Lesson
    0x001083DE: "ant_misbehavin",  # Ant Misbehavin'
    0x0010A214: "back_in_the_saddle",  # Back in the Saddle
    0x0010D229: "return_to_sender",  # Return To Sender
    0x0010D2C6: "beyond_the_beef",  # Beyond the Beef
    0x0010E196: "gi_blues",  # G.I. Blues
    0x0010E1DA: "high_times",  # High Times
    0x0010E1DB: "wang_dang_atomic_tango",  # Wang Dang Atomic Tango
    0x0010E1DC: "debt_collector",  # Debt Collector
    0x0010E908: "boulder_city_showdown",  # Boulder City Showdown
    0x00110A63: "how_little_we_know",  # How Little We Know
    0x00110A65: "bye_bye_love",  # Bye Bye Love
    0x00112577: "classic_inspiration",  # Classic Inspiration
    0x0011345D: "ringadingding",  # Ring-a-Ding-Ding!
    0x00116504: "talent_pool",  # Talent Pool
    0x00116B41: "things_that_go_boom",  # Things That Go Boom
    0x001176B8: "nothin_but_a_hound_dog",  # Nothin' But a Hound Dog
    0x0011A0C5: "the_moon_comes_over_the_tower",  # The Moon Comes Over the Tower
    0x0011F86A: "pheeble_will",  # Pheeble Will
    0x0011F86B: "jailhouse_rock",  # Jailhouse Rock
    0x0011F935: "anywhere_i_wander",  # Anywhere I Wander
    0x0011F95B: "kings_gambit",  # Kings' Gambit
    0x001214AA: "restoring_hope",  # Restoring Hope
    0x001214AB: "medical_mystery",  # Medical Mystery
    0x00124123: "birds_of_a_feather",  # Birds of a Feather
    0x001252D6: "et_tumor_brute",  # Et Tumor, Brute?
    0x00125E7E: "we_are_legion",  # We Are Legion
    0x001268BD: "i_hear_you_knocking",  # I Hear You Knocking
    0x001271EA: "the_finger_of_suspicion",  # The Finger of Suspicion
    0x00129445: "back_in_your_own_backyard",  # Back in Your Own Backyard
    0x00129D14: "render_unto_caesar",  # Render Unto Caesar
    0x00131E7C: "booted",  # Booted
    0x00131F08: "youll_know_it_when_it_happens",  # You'll Know It When It Happens
    0x00131F09: "arizona_killer",  # Arizona Killer
    0x00133045: "no_not_much",  # No, Not Much
    0x00133046: "climb_evry_mountain",  # Climb Ev'ry Mountain
    0x00133075: "eureka",  # Eureka!
    0x00134498: "eye_for_an_eye",  # Eye for an Eye
    0x001344E8: "bright_and_shiny",  # Bright and Shiny
    0x001348DB: "bleed_me_dry",  # Bleed Me Dry
    0x001349A7: "i_forgot_to_remember_to_forget",  # I Forgot to Remember to Forget
    0x00135F63: "left_my_heart",  # Left My Heart
    0x00136166: "for_the_republic_part_2",  # For the Republic, Part 2
    0x00137AB9: "veni_vidi_vici",  # Veni, Vidi, Vici
    0x00139B8D: "bitter_springs_infirmary_blues",  # Bitter Springs Infirmary Blues
    0x0013A40B: "viva_las_vegas",  # Viva Las Vegas!
    0x0013E5AF: "why_cant_we_be_friends",  # Why Can't We Be Friends?
    0x0013F405: "guess_who_i_saw_today",  # Guess Who I Saw Today
    0x0014050C: "we_will_all_go_together",  # We Will All Go Together
    0x0014050D: "wheel_of_fortune",  # Wheel of Fortune
    0x00140C3A: "oh_my_papa",  # Oh My Papa
    0x00140C3B: "aba_daba_honeymoon",  # Aba Daba Honeymoon
    0x00140C3C: "cry_me_a_river",  # Cry Me a River
    0x001429F2: "the_house_always_wins",  # The House Always Wins
    0x00144122: "can_you_find_it_in_your_heart",  # Can You Find it in Your Heart?
    0x00144519: "arachnophobia",  # Arachnophobia
    0x00145F85: "i_could_make_you_care",  # I Could Make You Care
    0x00147885: "the_house_always_wins_i",  # The House Always Wins, I
    0x00147886: "the_house_always_wins_ii",  # The House Always Wins, II
    0x00147887: "the_house_always_wins_iii",  # The House Always Wins, III
    0x00147888: "the_house_always_wins_iv",  # The House Always Wins, IV
    0x00147889: "the_house_always_wins_v",  # The House Always Wins, V
    0x0014788A: "the_house_always_wins_vi",  # The House Always Wins, VI
    0x0014788B: "the_house_always_wins_viii",  # The House Always Wins, VIII
    0x00148A34: "unfriendly_persuasion",  # Unfriendly Persuasion
    0x0014EF5F: "pressing_matters",  # Pressing Matters
    0x00151403: "one_for_my_baby",  # One for My Baby
    0x0015412F: "exploring_vault_74",  # Exploring Vault 74
    0x00154233: "no_gods_no_masters",  # No Gods, No Masters
    0x00154234: "all_or_nothing",  # All or Nothing
    0x00157321: "wild_card_change_in_management",  # Wild Card: Change in Management
    0x00157322: "wild_card_side_bets",  # Wild Card: Side Bets
    0x00157E60: "for_auld_lang_syne",  # For Auld Lang Syne
    0x0015827D: "wild_card_finishing_touches",  # Wild Card: Finishing Touches
    0x001599CD: "the_house_always_wins_vii",  # The House Always Wins, VII
    0x00159FA0: "hard_luck_blues",  # Hard Luck Blues
    0x0015CB8B: "young_hearts",  # Young Hearts
    0x0015D79D: "still_in_the_dark",  # Still in the Dark
    0x0015D912: "by_a_campfire_on_the_trail",  # By a Campfire on the Trail
    0x0015DA16: "heartache_by_the_number",  # Heartache by the Number
    0x0015E480: "i_dont_hurt_anymore",  # I Don't Hurt Anymore
    0x0015EC5B: "run_goodsprings_run",  # Run Goodsprings Run
    0x0015ECC9: "sunshine_boogie",  # Sunshine Boogie
    0x001633F2: "tend_to_your_business",  # Tend to Your Business
    0x001638F0: "eyesight_to_the_blind",  # Eyesight to the Blind
    0x0016511C: "friend_of_the_night",  # Friend of the Night
    0x0016517F: "ferocious_loyalty",  # Ferocious Loyalty
    0x00165AC2: "the_house_has_gone_bust",  # The House Has Gone Bust!
    0x00165C37: "wild_card_ace_in_the_hole",  # Wild Card: Ace in the Hole
    0x00166B87: "crazy_crazy_crazy",  # Crazy, Crazy, Crazy
    0x0016A161: "wild_card_you_and_what_army",  # Wild Card: You and What Army?
    # --- DeadMoney.esm ---
    0x01000FBF: "mq01_master_quest",  # MQ01 Master Quest
    0x01000FC0: "trigger_the_gala_event",  # Trigger the Gala Event
    0x01000FC1: "heist_of_the_centuries",  # Heist of the Centuries
    0x01005229: "sierra_madre_grand_opening",  # Sierra Madre Grand Opening!
    0x0100F3F7: "elijah_signal_established",  # Elijah Signal Established
    0x010139DF: "find_collar_8_dog",  # Find Collar 8: "Dog"
    0x010139E0: "find_collar_14_dean_domino",  # Find Collar 14: Dean Domino
    0x010139E1: "find_collar_12_christine",  # Find Collar 12: Christine
    0x01013A03: "put_the_beast_down",  # Put the Beast Down
    0x01013A04: "mixed_signals",  # Mixed Signals
    0x01013A3F: "fires_in_the_sky",  # Fires in the Sky
    0x01013A40: "strike_up_the_band",  # Strike Up the Band
    0x01013A43: "curtain_call_at_the_tampico",  # Curtain Call at the Tampico
    0x01013A44: "last_luxuries",  # Last Luxuries
    0x01013AA5: "dlc01_enemy_test",  # DLC01 Enemy Test
    0x01013C18: "wake_up_the_sierra_madre",  # Wake Up the Sierra Madre
    0x01013C69: "return_to_the_fountain",  # Return to the Fountain
    # --- HonestHearts.esm ---
    0x02008891: "happy_trails_expedition",  # Happy Trails Expedition
    0x02008892: "supply_train",  # Supply Train
    0x02008893: "arrival_at_zion",  # Arrival at Zion
    0x02008894: "the_grand_staircase",  # The Grand Staircase
    0x02008A36: "crush_the_white_legs",  # Crush the White Legs
    0x02008A37: "flight_from_zion",  # Flight from Zion
    0x020094C3: "rite_of_passage",  # Rite of Passage
    0x0200A3B9: "bighorners_of_the_eastern_virgin",  # Bighorners of the Eastern Virgin
    0x0200AE9C: "chaos_in_zion",  # Chaos in Zion
    0x0200B4D1: "optional_retake_the_bridge",  # Optional: Retake the Bridge
    0x0200B4D2: "optional_sanctity_of_the_dead",  # Optional: Sanctity of the Dead
    0x0200B4D3: "optional_prisoners_of_war",  # Optional: Prisoners of War
    0x0200C7C0: "the_advance_scouts",  # The Advance Scouts
    0x0200C7C1: "the_treacherous_road",  # The Treacherous Road
    0x0200C7C2: "river_monsters",  # River Monsters
    0x0200F304: "gathering_storms",  # Gathering Storms
    0x0200F6EE: "roadside_attraction",  # Roadside Attraction
    0x0200F6EF: "gone_fishin",  # Gone Fishin'
    0x0200F6F0: "tourist_trap",  # Tourist Trap
    0x0200F708: "deliverer_of_sorrows",  # Deliverer of Sorrows
    0x02010C25: "departing_paradise",  # Departing Paradise
    0x02010C82: "a_family_affair",  # A Family Affair
    0x02010C83: "civilized_mans_burden",  # Civilized Man's Burden
    # --- OldWorldBlues.esm ---
    0x03002FCA: "midnight_sciencefiction_feature",  # Midnight Science-Fiction Feature!
    0x03002FCB: "welcome_to_the_big_empty",  # Welcome to the Big Empty
    0x03002FCC: "old_world_blues",  # Old World Blues
    0x03002FCD: "x2_strange_transmissions",  # X-2: Strange Transmissions!
    0x03002FCE: "x8_high_school_horror",  # X-8: High School Horror!
    0x03002FCF: "x13_attack_of_the_infiltrator",  # X-13: Attack of the Infiltrator!
    0x03006D8D: "project_x13",  # Project X-13
    0x0300A755: "nvdlc03enc",  # NVDLC03Enc
    0x0300DD5C: "x8_data_retrieval_test",  # X-8 Data Retrieval Test
    0x030112D6: "field_research",  # Field Research
    0x030112E3: "all_my_friends_have_off_switches",  # All My Friends Have Off Switches
    0x030112E5: "influencing_people",  # Influencing People
    0x030121E3: "picking_your_brains",  # Picking Your Brains
    0x03014BF8: "a_brains_best_friend",  # A Brain's Best Friend
    0x03014C2C: "coming_out_of_her_shell",  # Coming Out Of Her Shell
    0x03014C2D: "he_came_and_went",  # He Came... And Went
    0x03014C63: "on_the_same_wavelength",  # On The Same Wavelength
    0x03014CFB: "whats_in_a_name",  # What's In A Name?
    0x03014CFE: "when_visitors_attack",  # When Visitors Attack!
    0x030166E2: "sonic_emitter_upgrade",  # Sonic Emitter Upgrade
    # --- LonesomeRoad.esm ---
    0x04003603: "the_reunion",  # The Reunion
    0x0400360F: "the_job",  # The Job
    0x04003610: "the_divide",  # The Divide
    0x04003613: "the_tunnelers",  # The Tunnelers
    0x04003615: "the_end",  # The End
    0x04003616: "the_courier",  # The Courier
    0x04003617: "the_silo",  # The Silo
    0x040039E3: "the_launch",  # The Launch
    0x0400BF03: "the_apocalypse",  # The Apocalypse
    # --- Fallout3.esm ---
    0x06014E83: "baby_steps",  # Baby Steps
    0x06014E84: "growing_up_fast",  # Growing Up Fast
    0x06014E85: "future_imperfect",  # Future Imperfect
    0x06014E86: "escape",  # Escape!
    0x06014E87: "following_in_his_footsteps",  # Following in His Footsteps
    0x06014E88: "galaxy_news_radio",  # Galaxy News Radio
    0x06014E89: "scientific_pursuits",  # Scientific Pursuits
    0x06014E8A: "tranquility_lane",  # Tranquility Lane
    0x06014E8B: "the_waters_of_life",  # The Waters of Life
    0x06014E8C: "picking_up_the_trail",  # Picking Up the Trail
    0x06014E8D: "rescue_from_paradise",  # Rescue from Paradise
    0x06014E8E: "finding_the_garden_of_eden",  # Finding the Garden of Eden
    0x06014E8F: "the_american_dream",  # The American Dream
    0x06014E90: "infiltration",  # Infiltration
    0x06014E91: "take_it_back",  # Take it Back!
    0x06014E93: "project_impurity",  # Project Impurity
    0x06014E94: "big_trouble_in_big_town",  # Big Trouble in Big Town
    0x06014E95: "the_superhuman_gambit",  # The Superhuman Gambit
    0x06014E96: "wasteland_survival_guide",  # Wasteland Survival Guide
    0x06014E97: "those",  # Those!
    0x06014E98: "the_nukacola_challenge",  # The Nuka-Cola Challenge
    0x06014E99: "head_of_state",  # Head of State
    0x06014E9B: "the_replicated_man",  # The Replicated Man
    0x06014E9C: "blood_ties",  # Blood Ties
    0x06014E9F: "tenpenny_tower",  # Tenpenny Tower
    0x06014EA0: "strictly_business",  # Strictly Business
    0x06014EA1: "you_gotta_shoot_em_in_the_head",  # You Gotta Shoot 'Em in the Head
    0x06014EA2: "stealing_independence",  # Stealing Independence
    0x06014EA3: "trouble_on_the_homefront",  # Trouble on the Homefront
    0x06014EA4: "agathas_song",  # Agatha's Song
    0x06014EA5: "reillys_rangers",  # Reilly's Rangers
    0x060173D1: "dc_ruins",  # DC Ruins
    0x060173D8: "megaton",  # Megaton
    0x0602A274: "oasis",  # Oasis
    0x06038AEF: "goat_script_quest",  # G.O.A.T. script quest
    0x06040691: "my_house_in_megaton",  # My House in Megaton
    0x0606F1E7: "contract_killer",  # Contract Killer
    0x0606F1E8: "lawbringer",  # Lawbringer
    0x0607B234: "my_house_in_tenpenny_tower",  # My House in Tenpenny Tower
    0x060872E6: "the_search_continues",  # The Search Continues
    # --- Anchorage.esm ---
    0x070009BE: "aiding_the_outcasts",  # Aiding the Outcasts
    0x070009BF: "the_guns_of_anchorage",  # The Guns of Anchorage
    0x070009C0: "paving_the_way",  # Paving the Way
    0x070014F6: "operation_anchorage",  # Operation: Anchorage!
    0x07002D0A: "strike_team_quest",  # Strike Team Quest
    0x070034DA: "dlc02ff",  # DLC02FF
    # --- ThePitt.esm ---
    0x0800108B: "unsafe_working_conditions",  # Unsafe Working Conditions
    0x0800108C: "into_the_pitt",  # Into The Pitt
    0x0800108D: "free_labor",  # Free Labor
    0x080029B8: "free_form_game_play",  # Free Form Game Play
    0x0800A358: "find_wild_bill",  # Find Wild Bill
    # --- BrokenSteel.esm ---
    0x09000802: "death_from_above",  # Death From Above
    0x09000AFD: "shock_value",  # Shock Value
    0x090011AD: "who_dares_wins",  # Who Dares Wins
    0x090027F4: "dlc03_nonquest",  # DLC03 non-quest
    0x09003B42: "protecting_the_water_way",  # Protecting the Water Way
    0x09003B67: "the_amazing_aqua_cura",  # The Amazing Aqua Cura!
    0x09004C75: "holy_water",  # Holy Water
    0x09006231: "enclave_base_background_quest",  # Enclave Base Background Quest
    # --- PointLookout.esm ---
    0x0A002F18: "an_antique_land",  # An Antique Land
    0x0A002F47: "the_dark_heart_of_blackhall",  # The Dark Heart of Blackhall
    0x0A0035BF: "defending_the_mansion",  # Defending The Mansion
    0x0A003F70: "a_spoonful_of_whiskey",  # A Spoonful of Whiskey
    0x0A00436E: "the_velvet_curtain",  # The Velvet Curtain
    0x0A005846: "the_local_flavor",  # The Local Flavor
    0x0A005847: "walking_with_spirits",  # Walking With Spirits
    0x0A005848: "hearing_voices",  # Hearing Voices
    0x0A005849: "thought_control",  # Thought Control
    0x0A00584A: "a_meeting_of_the_minds",  # A Meeting Of The Minds
    0x0A00815C: "latchkey_kenny",  # Latchkey Kenny
    0x0A009B5E: "pliks_safari",  # Plik's Safari

    # --- TTW-remapped FormIDs (verified from saves) ---
    0x00014E84: "things_that_go_boom",  # TTW remap
    0x00072E30: "there_stands_the_grass",  # TTW remap
    0x00092C4F: "my_kind_of_town",  # TTW remap
    0x000C595E: "still_in_the_dark",  # TTW remap
    0x000E1B5A: "cold_cold_heart",  # TTW remap
    0x000E2C14: "wang_dang_atomic_tango",  # TTW remap
    0x001300F2: "talent_pool",  # TTW remap
    0x00130127: "young_hearts",  # TTW remap
    0x00135BB7: "for_the_republic_2",  # TTW remap
    0x0014B0EA: "birds_of_a_feather",  # TTW remap
    0x00154A69: "the_coyotes",  # TTW remap
    0x00168C40: "how_little_we_know",  # TTW remap
    0x00172516: "eyesight_to_the_blind",  # TTW remap
    0x00176455: "you_can_depend_on_me",  # TTW remap
    0x00032DEE: "the_house_always_wins_ii",  # TTW remap
    0x000E1A56: "cold_cold_heart",  # TTW remap (alt)
    0x000E684B: "gi_blues",  # TTW remap
    0x0010E195: "things_that_go_boom",  # TTW remap (alt)
    0x00125301: "nothin_but_a_hound_dog",  # TTW remap
    0x001349A3: "the_house_always_wins_i",  # TTW remap
    0x001475B8: "boulder_city_showdown",  # TTW remap
    0x00154415: "my_kind_of_town",  # TTW remap (alt)
    0x00161D86: "come_fly_with_me",  # TTW remap
    0x00161D96: "ghost_town_gunfight",  # TTW remap
    0x0017B7C1: "guess_who_i_saw_today",  # TTW remap
    0x00135BB7: "for_the_republic_part_2",  # TTW remap (fix key)

    # --- TTW-remapped HonestHearts (from quicksave analysis) ---
    0x02009DBE: "nvdlc02ms01",  # Rite of Passage
    0x0200B5F3: "nvdlc02mq03d",  # Gathering Storms
    0x0200BCB6: "nvdlc02mq02",  # Arrival at Zion
    0x0200F303: "nvdlc02mq04",  # Crush the White Legs
    0x0201195F: "nvdlc02mq05",  # Flight from Zion
    0x02011963: "nvdlc02mq00",  # Happy Trails Expedition

    # --- TTW-remapped Fallout 3 main quest ---
    0x06018612: "mq01",  # Following in His Footsteps
    0x06018D0B: "mq02",  # Galaxy News Radio
    0x060210E0: "mq03",  # Scientific Pursuits
    0x06027FA8: "mq04",  # Tranquility Lane
    0x0602CA89: "mq05",  # The Waters of Life
    0x0603052A: "mq06",  # Picking Up the Trail
    0x06046B25: "mq07",  # Rescue from Paradise
    0x0606D952: "mq08",  # Finding the Garden of Eden
    0x06072A16: "mq09",  # The American Dream
    0x0607870D: "mq11",  # Take it Back!

    # --- TTW-remapped Fallout 3 side quests ---
    0x0607870E: "ms08",  # The Replicated Man
    0x0608F0D0: "ms11",  # The Power of the Atom
    0x060B294F: "ms03",  # Wasteland Survival Guide
    0x060C989F: "ms06",  # Head of State

    # --- TTW-remapped FO3 DLC ---
    0x07007572: "dlc02oa2",  # The Guns of Anchorage
    0x08002BE4: "dlc01quest03",  # Free Labor
    0x09005C28: "dlc03bs3",  # Who Dares Wins
    0x09008C5E: "dlc03wq01",  # Protecting the Water Way
    0x0B005848: "dlc05mz1",  # Not of This World
    0x0B007425: "dlc05mz3",  # This Galaxy Ain't Big Enough
}


# =====================================================================
# Pipe-delimited reader
# =====================================================================
class PipeReader:
    """Read pipe-delimited (0x7C) binary data from FNV save files."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def read_uint8_pipe(self) -> int:
        val = self.data[self.pos]
        self.pos += 1
        if self.pos < len(self.data) and self.data[self.pos] == 0x7C:
            self.pos += 1
        return val

    def read_float32_pipe(self) -> float:
        val = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        if self.pos < len(self.data) and self.data[self.pos] == 0x7C:
            self.pos += 1
        return val

    def read_uint32_pipe(self) -> int:
        val = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        if self.pos < len(self.data) and self.data[self.pos] == 0x7C:
            self.pos += 1
        return val

    def read_log_data_pipe(self) -> tuple[int, int]:
        day = struct.unpack_from("<H", self.data, self.pos)[0]
        year = struct.unpack_from("<H", self.data, self.pos + 2)[0]
        self.pos += 4
        if self.pos < len(self.data) and self.data[self.pos] == 0x7C:
            self.pos += 1
        return day, year


# =====================================================================
# QUST change form parsing
# =====================================================================
def parse_quest_stages(record_data: bytes, change_flags: int):
    """Parse QUST change form data. Returns list of stage dicts."""
    r = PipeReader(record_data)
    stages = []

    try:
        if change_flags & CHANGE_FORM_FLAGS:
            r.read_uint32_pipe()
        if change_flags & CHANGE_QUEST_FLAGS:
            r.read_uint8_pipe()
        if change_flags & CHANGE_QUEST_SCRIPT_DELAY:
            r.read_float32_pipe()

        if change_flags & CHANGE_QUEST_STAGES:
            count_byte = r.read_uint8_pipe()
            num_stages = count_byte // 4

            for _ in range(num_stages):
                stage_id = r.read_uint8_pipe()
                status = r.read_uint8_pipe()
                log_count_byte = r.read_uint8_pipe()
                log_count = log_count_byte // 4

                for _ in range(log_count):
                    r.read_uint8_pipe()  # log entry ID
                    has_data = r.read_uint8_pipe()
                    if has_data:
                        r.read_log_data_pipe()

                stages.append({
                    "stage_id": stage_id,
                    "completed": bool(status & 0x01),
                })
    except (IndexError, struct.error):
        pass  # return whatever stages we parsed

    return stages


# =====================================================================
# Save file parsing
# =====================================================================
def parse_save(save_path: Path):
    """Parse an FNV .fos save file and extract quest state.

    Returns dict with header info and quest data keyed by resolved FormID.
    """
    data = save_path.read_bytes()

    header, offset = parse_header(data)
    plugins, form_version, offset = parse_plugins(data, offset)
    flt = parse_file_location_table(data, offset)

    # Parse formID array for resolving type-0 references
    fa_offset = flt["formIDArrayCountOffset"]
    fa_count = struct.unpack_from("<I", data, fa_offset)[0]
    formids = []
    fa_pos = fa_offset + 4
    for _ in range(fa_count):
        formids.append(struct.unpack_from("<I", data, fa_pos)[0])
        fa_pos += 4

    # Parse all change forms, extract QUST (type 9) records
    cf_count = flt["changeFormCount"]
    pos = flt["changeFormsOffset"]
    quests = {}

    for _ in range(cf_count):
        record, pos = parse_change_form(data, pos, len(plugins))

        if record["record_type"] != QUST_CHANGE_TYPE:
            continue
        if not (record["change_flags"] & CHANGE_QUEST_STAGES):
            continue

        # Resolve FormID
        fid_str = record["form_id_str"]
        resolved = None
        if fid_str.startswith("formIDArr["):
            idx = int(fid_str.split("[")[1].rstrip("]"))
            if idx < len(formids):
                resolved = formids[idx]
        elif "(FalloutNV)" in fid_str:
            resolved = int(fid_str.split("(")[0], 16)
        elif "plugin[" in fid_str:
            parts = fid_str.split(":")
            pidx = int(parts[0].split("[")[1].rstrip("]"), 16)
            oid = int(parts[1], 16)
            resolved = (pidx << 24) | oid

        if resolved is None:
            continue

        stages = parse_quest_stages(record["data"], record["change_flags"])
        if stages:
            quests[resolved] = {
                "stages": stages,
                "plugin_idx": (resolved >> 24) & 0xFF,
            }

    return {
        "header": header,
        "plugins": plugins,
        "quests": quests,
    }


# =====================================================================
# Seed data
# =====================================================================
def load_seed_data():
    """Load seed data quest definitions."""
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


# =====================================================================
# Quest state logic
# =====================================================================
def determine_quest_status(stages: list[dict]) -> str:
    """Determine overall quest status from stage completion data.

    - 'finished' if the highest-numbered stage is completed
      or all stages are completed
    - 'started' if any stage exists (quest is tracked)
    - 'unstarted' otherwise
    """
    if not stages:
        return "unstarted"

    completed = [s for s in stages if s["completed"]]
    if not completed:
        return "started"

    # If the last stage (by ID) is completed, quest is finished
    max_stage = max(stages, key=lambda s: s["stage_id"])
    if max_stage["completed"]:
        return "finished"

    return "started"


# =====================================================================
# Sync payload
# =====================================================================
def build_sync_payload(save_path: Path, username="default", playthrough_name=None,
                       auto_seed=True):
    """Build the full sync API payload from an FNV save file.

    Uses dynamic ESM resolution: scans the actual ESMs loaded by this save
    to resolve FormIDs to quest names. Falls back to the hardcoded mapping
    for any quests it can't find in ESMs.

    If auto_seed=True, also updates the seed data with newly discovered quests.
    """
    from esm_resolver import ESMResolver, build_dynamic_seed

    result = parse_save(save_path)
    header = result["header"]
    save_quests = result["quests"]
    plugins = result["plugins"]
    seed_quests = load_seed_data()

    # Build dynamic resolver from this save's plugin list
    resolver = ESMResolver(plugins)
    resolved = resolver.resolve_all_quests(save_quests)

    # Playthrough ID from player name in save
    if playthrough_name is None:
        playthrough_name = header.get("player_name", "Courier")

    display_name = (
        f"{header['player_name']} "
        f"(Level {header['player_level']}, {header['playtime']})"
    )

    # Map save data to quest_keys using:
    # 1. Dynamic ESM resolution (preferred — handles TTW, mods, any load order)
    # 2. Hardcoded FORMID_TO_QUEST_KEY (fallback for unresolvable FormIDs)
    active_quests = []
    new_quests_for_seed = []

    for formid, quest_data in save_quests.items():
        stages = quest_data["stages"]
        status = determine_quest_status(stages)
        if status == "unstarted":
            continue

        # Try dynamic resolution first
        esm_info = resolved.get(formid)
        quest_key = None
        quest_name = None

        if esm_info:
            quest_key = esm_info["quest_key"]
            quest_name = esm_info["name"]
        else:
            # Fallback to hardcoded table
            quest_key = FORMID_TO_QUEST_KEY.get(formid)

        if quest_key is None:
            continue

        # Build stage entries
        stage_entries = []
        if quest_key in seed_quests:
            # Match against seed data stages
            seed_stage_keys = set(seed_quests[quest_key]["stages"].keys())
            for s in stages:
                stage_key = f"stage_{s['stage_id']}"
                if stage_key in seed_stage_keys:
                    stage_entries.append({
                        "stage_key": stage_key,
                        "completed": s["completed"],
                    })
        else:
            # Quest not in seed data — use raw stages
            for s in stages:
                stage_entries.append({
                    "stage_key": f"stage_{s['stage_id']}",
                    "completed": s["completed"],
                })
            # Track for seed data generation
            if esm_info:
                new_quests_for_seed.append(esm_info)

        active_quests.append({
            "quest_key": quest_key,
            "status": status,
            "stages": stage_entries,
        })

    # Auto-update seed data with newly discovered quests
    if auto_seed and new_quests_for_seed:
        _update_seed_data(new_quests_for_seed)

    return {
        "username": username,
        "game_slug": "fallout_new_vegas",
        "playthrough": {
            "external_id": playthrough_name,
            "name": display_name,
        },
        "quests": active_quests,
    }


def _update_seed_data(new_quests: list[dict]):
    """Add newly discovered quests to the seed data file."""
    import json

    try:
        with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
            seed = json.load(f)
    except:
        return

    existing_keys = {q["quest_key"] for q in seed["quests"]}
    added = 0

    for info in new_quests:
        if info["quest_key"] in existing_keys:
            continue

        stages = []
        for stage_id in info.get("esm_stages", []):
            stages.append({
                "stage_key": f"stage_{stage_id}",
                "name": f"Stage {stage_id}",
                "sort_order": stage_id,
            })

        seed["quests"].append({
            "quest_key": info["quest_key"],
            "name": info["name"],
            "description": "",
            "category": info.get("category", "side"),
            "sort_order": 0,
            "guide_content": "",
            "stages": stages,
        })
        existing_keys.add(info["quest_key"])
        added += 1

    if added > 0:
        with open(SEED_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(seed, f, indent=2, ensure_ascii=False)
        print(f"Auto-added {added} new quests to seed data", file=sys.stderr)


# =====================================================================
# Save discovery
# =====================================================================
def find_saves(save_dir: Path = None) -> list[dict]:
    """Find all .fos save files in the save directory."""
    if save_dir is None:
        save_dir = DEFAULT_SAVE_DIR
    if not save_dir.exists():
        return []

    saves = []
    for f in save_dir.glob("*.fos"):
        if f.name.startswith("0xC0"):
            continue  # skip init saves
        try:
            data = f.read_bytes()
            header, _ = parse_header(data)
            saves.append({
                "path": str(f),
                "name": f.name,
                "player_name": header["player_name"],
                "level": header["player_level"],
                "location": header["player_location"],
                "playtime": header["playtime"],
                "save_number": header["save_number"],
            })
        except Exception:
            continue

    saves.sort(key=lambda s: s.get("save_number", 0), reverse=True)
    return saves


def find_latest_save(save_dir: Path = None) -> Path | None:
    """Find the most recently modified .fos save file."""
    if save_dir is None:
        save_dir = DEFAULT_SAVE_DIR
    if not save_dir.exists():
        return None

    fos_files = list(save_dir.glob("*.fos"))
    fos_files = [f for f in fos_files if not f.name.startswith("0xC0")]
    if not fos_files:
        return None

    fos_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return fos_files[0]


# =====================================================================
# CLI
# =====================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Extract Fallout: New Vegas save data for RPG Scribe"
    )
    parser.add_argument(
        "save_path", nargs="?",
        help="Path to .fos save file. If omitted, uses the most recent save.",
    )
    parser.add_argument("--list", action="store_true", help="List available saves")
    parser.add_argument("--username", default="default", help="Username for sync")
    parser.add_argument(
        "--playthrough",
        help="Override playthrough name (default: player name from save)",
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

    if args.list:
        saves = find_saves(save_dir)
        if not saves:
            print("No saves found.")
            sys.exit(1)
        print(f"Found {len(saves)} save(s):\n")
        for s in saves:
            print(f"  {s['name']:<55s}  {s['player_name']:<12s}  "
                  f"Level {s['level']:<3}  {s['location']:<25s}  {s['playtime']}")
        sys.exit(0)

    save_path = args.save_path
    if save_path is None:
        save_path = find_latest_save(save_dir)
        if save_path is None:
            print("ERROR: No saves found. Specify a save file or --save-dir.")
            sys.exit(1)
        print(f"Using latest save: {save_path}")
    save_path = Path(save_path)

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
            url, data=data,
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
