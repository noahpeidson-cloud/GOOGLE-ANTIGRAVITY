"""
export.py - Card Ladder 16-Column CSV Exporter and Fuzzy Normalization Engine.
Strictly implements Milestone 4 requirements:
- Exact 16-column Card Ladder CSV formatting
- Strict exclusion of 5 internal variables (Slab Serial #, Query, Tags, Back Image, AI Status) and DB metadata
- Multi-tier Fuzzy Normalization Engine (difflib, diacritics folding via unicodedata, canonical catalogs across 22 categories)
- Leading zero string preservation for card numbers (dtype={'Number': str}, csv.QUOTE_MINIMAL)
- 500-card batch circuit breaker and automatic file chunking (_part1.csv, _part2.csv, etc.)
- Status filtering (CLEARED, ALL, REVIEW VARIATION, NEEDS REVIEW)
"""

from __future__ import annotations

import csv
import difflib
import math
import os
import re
import sqlite3
import unicodedata
from typing import Any, Optional, Sequence
import pandas as pd

from database import DEFAULT_DB_PATH, get_db_connection


# ============================================================================
# Card Ladder 16-Column Schema & Exclusion Constants
# ============================================================================

# Exact 16 Card Ladder Column Headers in strict canonical sequence
CARD_LADDER_COLUMNS: list[str] = [
    "Date Purchased",
    "Quantity",
    "Player",
    "Year",
    "Set",
    "Variation",
    "Number",
    "Category",
    "Condition",
    "Investment",
    "Estimated Value",
    "Ladder ID",
    "Notes",
    "Date Sold",
    "Sold Price",
    "Image",
]

# Internal fields that must NEVER appear in Card Ladder CSV
EXCLUDED_INTERNAL_FIELDS: list[str] = [
    "slab_serial_number",
    "query",
    "tags",
    "back_image",
    "ai_status",
    "id",
    "created_at",
    "updated_at",
]


def get_card_ladder_columns() -> list[str]:
    """Returns a copy of the canonical 16 Card Ladder CSV headers."""
    return list(CARD_LADDER_COLUMNS)


def get_excluded_fields() -> list[str]:
    """Returns a list of internal database fields excluded from Card Ladder export."""
    return list(EXCLUDED_INTERNAL_FIELDS)


# ============================================================================
# Canonical Dictionaries Across All 22 Categories
# ============================================================================

CANONICAL_PLAYERS: dict[str, list[str]] = {
    "Basketball": [
        "Michael Jordan",
        "LeBron James",
        "Kobe Bryant",
        "Stephen Curry",
        "Luka Dončić",
        "Victor Wembanyama",
        "Giannis Antetokounmpo",
        "Nikola Jokić",
        "Shai Gilgeous-Alexander",
        "Anthony Edwards",
        "Jayson Tatum",
        "Kevin Durant",
        "Larry Bird",
        "Magic Johnson",
        "Shaquille O'Neal",
        "Caitlin Clark",
        "Angel Reese",
        "Ja Morant",
        "Zion Williamson",
        "Paolo Banchero",
        "Tyrese Haliburton",
        "Devin Booker",
        "Trae Young",
        "Donovan Mitchell",
        "Jalen Brunson",
        "Karl-Anthony Towns",
        "De'Aaron Fox",
    ],
    "Baseball": [
        "Shohei Ohtani",
        "Mike Trout",
        "Ronald Acuña Jr.",
        "Aaron Judge",
        "Juan Soto",
        "Mookie Betts",
        "Fernando Tatis Jr.",
        "Julio Rodríguez",
        "Elly De La Cruz",
        "Paul Skenes",
        "Jackson Holliday",
        "Jackson Chourio",
        "Gunnar Henderson",
        "Adley Rutschman",
        "Ken Griffey Jr.",
        "Derek Jeter",
        "Babe Ruth",
        "Mickey Mantle",
        "Jackie Robinson",
        "Willie Mays",
        "Hank Aaron",
        "Ichiro Suzuki",
        "Albert Pujols",
        "Corbin Carroll",
        "Bobby Witt Jr.",
        "Buster Posey",
    ],
    "Football": [
        "Patrick Mahomes",
        "Tom Brady",
        "Josh Allen",
        "Joe Burrow",
        "Lamar Jackson",
        "C.J. Stroud",
        "Caleb Williams",
        "Jayden Daniels",
        "Justin Jefferson",
        "Tyreek Hill",
        "Travis Kelce",
        "Christian McCaffrey",
        "Brock Purdy",
        "Jalen Hurts",
        "Peyton Manning",
        "Aaron Rodgers",
        "Drew Brees",
        "Brett Favre",
        "Joe Montana",
        "Jerry Rice",
        "Dan Marino",
        "Barry Sanders",
        "Anthony Richardson",
        "Trevor Lawrence",
        "Jordan Love",
    ],
    "Hockey": [
        "Connor McDavid",
        "Wayne Gretzky",
        "Alexander Ovechkin",
        "Sidney Crosby",
        "Connor Bedard",
        "Nathan MacKinnon",
        "Auston Matthews",
        "Mario Lemieux",
        "Alexis Lafrenière",
        "Cale Makar",
        "Leon Draisaitl",
        "Kirill Kaprizov",
        "Jack Hughes",
        "Tim Stützle",
        "Igor Shesterkin",
    ],
    "Soccer": [
        "Lionel Messi",
        "Cristiano Ronaldo",
        "Kylian Mbappé",
        "Erling Haaland",
        "Pelé",
        "Diego Maradona",
        "Jude Bellingham",
        "Vinícius Júnior",
        "Lamine Yamal",
        "Neymar Jr.",
        "Luka Modrić",
        "Kevin De Bruyne",
        "Bukayo Saka",
        "Pedri",
        "Gavi",
        "Zinedine Zidane",
    ],
    "Tennis": [
        "Roger Federer",
        "Rafael Nadal",
        "Novak Djokovic",
        "Serena Williams",
        "Carlos Alcaraz",
        "Iga Świątek",
        "Coco Gauff",
        "Jannik Sinner",
        "Steffi Graf",
        "Pete Sampras",
        "Aryna Sabalenka",
    ],
    "Wrestling": [
        "Stone Cold Steve Austin",
        "The Rock",
        "Hulk Hogan",
        "John Cena",
        "Roman Reigns",
        "Cody Rhodes",
        "The Undertaker",
        "Ric Flair",
        "Bret Hart",
        "Shawn Michaels",
        "Randy Savage",
    ],
    "Racing": [
        "Max Verstappen",
        "Lewis Hamilton",
        "Ayrton Senna",
        "Michael Schumacher",
        "Charles Leclerc",
        "Lando Norris",
        "Dale Earnhardt",
        "Dale Earnhardt Jr.",
        "Jeff Gordon",
        "Richard Petty",
    ],
    "Golf": [
        "Tiger Woods",
        "Jack Nicklaus",
        "Rory McIlroy",
        "Scottie Scheffler",
        "Phil Mickelson",
        "Arnold Palmer",
        "Jordan Spieth",
        "Bryson DeChambeau",
    ],
    "Boxing": [
        "Muhammad Ali",
        "Mike Tyson",
        "Floyd Mayweather Jr.",
        "Manny Pacquiao",
        "Canelo Álvarez",
        "Sugar Ray Robinson",
        "Joe Louis",
        "George Foreman",
    ],
    "UFC/MMA": [
        "Jon Jones",
        "Conor McGregor",
        "Khabib Nurmagomedov",
        "Israel Adesanya",
        "Alex Pereira",
        "Sean O'Malley",
        "Islam Makhachev",
        "Georges St-Pierre",
        "Anderson Silva",
        "Amanda Nunes",
        "Max Holloway",
        "Dustin Poirier",
    ],
    "Pokemon": [
        "Charizard",
        "Pikachu",
        "Blastoise",
        "Venusaur",
        "Mewtwo",
        "Mew",
        "Gengar",
        "Rayquaza",
        "Lugia",
        "Umbreon",
        "Espeon",
        "Gyarados",
        "Dragonite",
        "Eevee",
        "Snorlax",
        "Mimikyu",
        "Lucario",
        "Giratina",
        "Arceus",
    ],
    "Magic": [
        "Black Lotus",
        "Mox Sapphire",
        "Mox Jet",
        "Mox Ruby",
        "Mox Emerald",
        "Mox Pearl",
        "Time Walk",
        "Ancestral Recall",
        "Timetwister",
        "Jace, the Mind Sculptor",
        "Liliana of the Veil",
        "Ragavan, Nimble Pilferer",
        "Urza, Lord High Artificer",
        "Sheoldred, the Apocalypse",
        "Sol Ring",
        "Mana Crypt",
    ],
    "Metazoo": [
        "Mothman",
        "Loveland Frogman",
        "Bigfoot",
        "Jersey Devil",
        "Flatwoods Monster",
        "Wendigo",
        "Indrid Cold",
        "Piasa Bird",
    ],
    "Yugioh": [
        "Blue-Eyes White Dragon",
        "Dark Magician",
        "Dark Magician Girl",
        "Red-Eyes Black Dragon",
        "Exodia the Forbidden One",
        "Slifer the Sky Dragon",
        "Obelisk the Tormentor",
        "The Winged Dragon of Ra",
        "Stardust Dragon",
        "Black Luster Soldier",
        "Elemental HERO Neos",
        "Cyber Dragon",
    ],
    "Fortnite": [
        "Black Knight",
        "Renegade Raider",
        "Skull Trooper",
        "Ghoul Trooper",
        "John Wick",
        "Peely",
        "Drift",
        "Omega",
    ],
    "Dragonballz": [
        "Son Goku",
        "Vegeta",
        "Gohan",
        "Piccolo",
        "Frieza",
        "Cell",
        "Majin Buu",
        "Trunks",
        "Broly",
        "Beerus",
    ],
    "Entertainment": [
        "Darth Vader",
        "Luke Skywalker",
        "Spider-Man",
        "Batman",
        "Iron Man",
        "Harry Potter",
        "Indiana Jones",
        "James Bond",
    ],
    "Swimming": [
        "Michael Phelps",
        "Katie Ledecky",
        "Caeleb Dressel",
        "Mark Spitz",
        "Ian Thorpe",
        "Ryan Lochte",
        "Summer McIntosh",
    ],
    "Softball": [
        "Jennie Finch",
        "Cat Osterman",
        "Monica Abbott",
        "Jocelyn Alo",
        "Montana Fouts",
        "Keilani Ricketts",
    ],
    "PopCulture": [
        "Taylor Swift",
        "Michael Jackson",
        "Elvis Presley",
        "Marilyn Monroe",
        "The Beatles",
        "Beyoncé",
    ],
    "Flesh and Blood": [
        "Fyendal's Spring Tunic",
        "Command and Conquer",
        "Art of War",
        "Enlightened Strike",
        "Eye of Ophidia",
        "Crown of Providence",
    ],
}

CANONICAL_SETS: dict[str, list[str]] = {
    "Basketball": [
        "Panini Prizm",
        "Panini Select",
        "Panini National Treasures",
        "Panini Flawless",
        "Panini Optic",
        "Panini Donruss Optic",
        "Panini Contenders",
        "Panini Donruss",
        "Panini Crown Royale",
        "Panini Obsidian",
        "Panini Spectra",
        "Panini Impeccable",
        "Panini Court Kings",
        "Panini Revolution",
        "Panini Mosaic",
        "Panini Origins",
        "Panini Recon",
        "Panini Hoops",
        "Topps Chrome",
        "Topps Finest",
        "Bowman Chrome",
        "Upper Deck SP Authentic",
        "Upper Deck Exquisite Collection",
        "Fleer Showcase",
        "Fleer",
    ],
    "Baseball": [
        "Topps Series 1",
        "Topps Series 2",
        "Topps Update Series",
        "Topps Chrome",
        "Topps Chrome Update",
        "Bowman",
        "Bowman Chrome",
        "Bowman Draft",
        "Topps Heritage",
        "Topps Heritage High Number",
        "Topps Tribute",
        "Topps Museum Collection",
        "Topps Sterling",
        "Topps Tier One",
        "Topps Stadium Club",
        "Topps Stadium Club Chrome",
        "Topps Allen & Ginter",
        "Panini Donruss",
        "Panini Prizm",
        "Panini Select",
        "Upper Deck",
        "Fleer",
    ],
    "Football": [
        "Panini Prizm",
        "Panini Select",
        "Panini National Treasures",
        "Panini Flawless",
        "Panini Optic",
        "Panini Donruss Optic",
        "Panini Donruss",
        "Panini Contenders",
        "Panini Mosaic",
        "Panini Certified",
        "Panini Absolute",
        "Panini Phoenix",
        "Panini XR",
        "Panini Black",
        "Panini Zenith",
        "Panini Origins",
        "Panini Score",
        "Topps Chrome",
    ],
    "Hockey": [
        "Upper Deck Series 1",
        "Upper Deck Series 2",
        "Upper Deck Extended Series",
        "Upper Deck Young Guns",
        "Upper Deck SP Authentic",
        "Upper Deck The Cup",
        "Upper Deck Ultimate Collection",
        "Upper Deck Ice",
        "Upper Deck Premier",
        "Upper Deck Allure",
        "O-Pee-Chee",
        "O-Pee-Chee Platinum",
    ],
    "Soccer": [
        "Panini Mega Cracks",
        "Panini Prizm Premier League",
        "Panini Prizm World Cup",
        "Panini Select La Liga",
        "Panini Select Premier League",
        "Panini Select Serie A",
        "Panini Donruss Soccer",
        "Topps Chrome UEFA Champions League",
        "Topps Chrome Bundesliga",
        "Topps Merlin Heritage",
        "Topps Museum Collection UEFA",
        "Topps Finest UEFA Champions League",
        "Topps Stadium Club Chrome UEFA",
    ],
    "Tennis": [
        "Topps Chrome Tennis",
        "NetPro",
        "Ace Authentic",
        "Topps Dynasty Tennis",
    ],
    "Wrestling": [
        "Topps WWE Chrome",
        "Panini Prizm WWE",
        "Panini Select WWE",
        "Topps Heritage WWE",
    ],
    "Racing": [
        "Topps Chrome F1",
        "Topps Chrome Formula 1",
        "Topps Turbo Attax F1",
        "Panini Prizm NASCAR",
        "Panini Donruss Racing",
    ],
    "Golf": [
        "Upper Deck Golf",
        "SP Game Used Golf",
        "Upper Deck Artifacts Golf",
    ],
    "Boxing": [
        "Ringside Boxing",
        "Topps Chrome Boxing",
        "Panini Prizm Boxing",
    ],
    "UFC/MMA": [
        "Panini Prizm UFC",
        "Panini Select UFC",
        "Panini Optic UFC",
        "Topps Chrome UFC",
        "Topps Knockout",
    ],
    "Pokemon": [
        "Base Set",
        "Jungle",
        "Fossil",
        "Team Rocket",
        "Gym Heroes",
        "Gym Challenge",
        "Neo Genesis",
        "Neo Discovery",
        "Neo Revelation",
        "Neo Destiny",
        "Legendary Collection",
        "Evolving Skies",
        "Crown Zenith",
        "151",
        "Paldean Fates",
        "Twilight Masquerade",
        "Surging Sparks",
        "Prismatic Evolutions",
        "Sword & Shield Base Set",
        "Scarlet & Violet Base Set",
        "Hidden Fates",
        "Shining Fates",
        "Celebrations",
    ],
    "Magic": [
        "Limited Edition Alpha",
        "Limited Edition Beta",
        "Unlimited Edition",
        "Revised Edition",
        "Arabian Nights",
        "Antiquities",
        "Legends",
        "The Dark",
        "Modern Horizons 3",
        "Modern Horizons 2",
        "The Lord of the Rings: Tales of Middle-earth",
        "Commander Masters",
        "Double Masters",
        "Bloomburrow",
        "Duskmourn: House of Horror",
        "Foundations",
    ],
    "Metazoo": [
        "Cryptid Nation",
        "Nightfall",
        "Wilderness",
        "UFO",
        "Seance",
        "Native",
    ],
    "Yugioh": [
        "Legend of Blue Eyes White Dragon",
        "Metal Raiders",
        "Spell Ruler",
        "Pharaoh's Servant",
        "Labyrinth of Nightmare",
        "Legacy of Darkness",
        "Pharaonic Guardian",
        "Magician's Force",
        "Dark Crisis",
        "Invasion of Chaos",
        "25th Anniversary Rarity Collection",
        "Battles of Legend",
    ],
    "Fortnite": [
        "Series 1",
        "Series 2",
        "Series 3",
    ],
    "Dragonballz": [
        "Dragon Ball Super Card Game",
        "Fusion World",
    ],
    "Entertainment": [
        "Star Wars Masterwork",
        "Marvel Masterpieces",
        "Marvel Chrome",
    ],
    "Swimming": [
        "Topps Olympic Heritage",
        "Panini Americana",
    ],
    "Softball": [
        "Topps USA Softball",
    ],
    "PopCulture": [
        "Leaf Pop Century",
        "Kakawow Phantom",
    ],
    "Flesh and Blood": [
        "Welcome to Rathe",
        "Arcane Rising",
        "Crucible of War",
        "Monarch",
        "Tales of Aria",
        "Everfest",
        "Uprising",
        "Dynasty",
        "Outsiders",
        "Dusk till Dawn",
        "Bright Lights",
        "Heavy Hitters",
        "Part the Mistveil",
        "Rosetta",
    ],
}

# Fast-path alias dictionaries
PLAYER_ALIASES: dict[str, str] = {
    # Basketball
    "steph curry": "Stephen Curry",
    "steve curry": "Stephen Curry",
    "gianis": "Giannis Antetokounmpo",
    "giannis": "Giannis Antetokounmpo",
    "the greek freak": "Giannis Antetokounmpo",
    "wemby": "Victor Wembanyama",
    "wembanyama": "Victor Wembanyama",
    "lebron": "LeBron James",
    "king james": "LeBron James",
    "kobe": "Kobe Bryant",
    "black mamba": "Kobe Bryant",
    "jordan": "Michael Jordan",
    "mj": "Michael Jordan",
    "luka": "Luka Dončić",
    "luka doncic": "Luka Dončić",
    "joker": "Nikola Jokić",
    "nikola jokic": "Nikola Jokić",
    "sga": "Shai Gilgeous-Alexander",
    "ant man": "Anthony Edwards",
    "ant-man": "Anthony Edwards",

    # Baseball
    "ohtani": "Shohei Ohtani",
    "shohei": "Shohei Ohtani",
    "shohei ohtani (大谷 翔平)": "Shohei Ohtani",
    "acuna": "Ronald Acuña Jr.",
    "ronald acuna": "Ronald Acuña Jr.",
    "ronald acuna jr": "Ronald Acuña Jr.",
    "ronald acuna jr.": "Ronald Acuña Jr.",
    "elly": "Elly De La Cruz",
    "elly de la cruz": "Elly De La Cruz",
    "elly delacruz": "Elly De La Cruz",
    "tatis": "Fernando Tatis Jr.",
    "fernando tatis": "Fernando Tatis Jr.",
    "trout": "Mike Trout",
    "judge": "Aaron Judge",
    "griffey": "Ken Griffey Jr.",
    "ken griffey": "Ken Griffey Jr.",

    # Football
    "mahomes": "Patrick Mahomes",
    "pat mahomes": "Patrick Mahomes",
    "patrick maholmes": "Patrick Mahomes",
    "brady": "Tom Brady",
    "cj stroud": "C.J. Stroud",
    "c.j. stroud": "C.J. Stroud",
    "caleb": "Caleb Williams",
    "cmc": "Christian McCaffrey",

    # Hockey
    "mcdavid": "Connor McDavid",
    "gretzky": "Wayne Gretzky",
    "the great one": "Wayne Gretzky",
    "bedard": "Connor Bedard",
    "ovi": "Alexander Ovechkin",
    "alex ovechkin": "Alexander Ovechkin",
    "alexis lafreniere": "Alexis Lafrenière",
    "tim stutzle": "Tim Stützle",

    # Soccer
    "cr7": "Cristiano Ronaldo",
    "cristiano": "Cristiano Ronaldo",
    "messi": "Lionel Messi",
    "leo messi": "Lionel Messi",
    "mbappe": "Kylian Mbappé",
    "kylian mbappe": "Kylian Mbappé",
    "haaland": "Erling Haaland",
    "erling braut haaland": "Erling Haaland",
    "luka modric": "Luka Modrić",
    "vinicius jr": "Vinícius Júnior",
    "vinicius junior": "Vinícius Júnior",
    "neymar": "Neymar Jr.",

    # Tennis
    "iga swiatek": "Iga Świątek",
    "djokovic": "Novak Djokovic",
    "federer": "Roger Federer",
    "nadal": "Rafael Nadal",
}

SET_ALIASES: dict[str, str] = {
    # Sports sets
    "prizm": "Panini Prizm",
    "select": "Panini Select",
    "optic": "Panini Optic",
    "donruss optic": "Panini Donruss Optic",
    "national treasures": "Panini National Treasures",
    "nt": "Panini National Treasures",
    "flawless": "Panini Flawless",
    "topps chrome": "Topps Chrome",
    "tc": "Topps Chrome",
    "topps chrome bb": "Topps Chrome",
    "bowman draft picks": "Bowman Draft",
    "bowman chrome draft": "Bowman Draft",
    "young guns": "Upper Deck Young Guns",
    "yg": "Upper Deck Young Guns",
    "sp authentic": "Upper Deck SP Authentic",
    "mega cracks": "Panini Mega Cracks",
    "megacracks": "Panini Mega Cracks",

    # TCG sets
    "pokemon base": "Base Set",
    "pokemon base set": "Base Set",
    "base": "Base Set",
    "151": "151",
    "pokemon 151": "151",
    "mtg alpha": "Limited Edition Alpha",
    "magic alpha": "Limited Edition Alpha",
    "alpha": "Limited Edition Alpha",
    "beta": "Limited Edition Beta",
    "mtg beta": "Limited Edition Beta",
    "magic beta": "Limited Edition Beta",
    "unlimited": "Unlimited Edition",
    "revised": "Revised Edition",
    "lob": "Legend of Blue Eyes White Dragon",
    "legend of blue eyes": "Legend of Blue Eyes White Dragon",
}


# ============================================================================
# Diacritic & String Folding Engine
# ============================================================================

def fold_string(s: Any) -> str:
    """
    Decomposes Unicode diacritics and transforms string to normalized lowercase alphanumeric format.
    Example:
        'Luka Dončić' -> 'luka doncic'
        'Ronald Acuña Jr.' -> 'ronald acuna jr'
        'C.J. Stroud' -> 'cj stroud'
        'Shohei Ohtani (大谷 翔平)' -> 'shohei ohtani'
    """
    if s is None:
        return ""
    str_val = str(s).strip()
    if not str_val:
        return ""

    # Strip Asian/Japanese kanji annotations if wrapped in parentheses
    cleaned = re.sub(r"\s*\([^)]*[\u3000-\u9fff]+[^)]*\)", "", str_val)
    # Strip dots and apostrophes so C.J. -> CJ and O'Neal -> ONeal
    cleaned = re.sub(r"['\.]", "", cleaned)
    # Unicode NFKD decomposition
    decomposed = unicodedata.normalize("NFKD", cleaned)
    # Filter out combining diacritical marks
    ascii_chars = "".join(c for c in decomposed if not unicodedata.combining(c))
    # Lowercase, replace non-alphanumeric with spaces, collapse spaces
    sanitized = re.sub(r"[^\w\s]", " ", ascii_chars).lower()
    return re.sub(r"\s+", " ", sanitized).strip()


# ============================================================================
# Fuzzy Normalization Functions
# ============================================================================

def normalize_player_name(
    raw_name: str,
    category: str = "",
    canonical_dict: Optional[dict[str, list[str]]] = None,
    cutoff: float = 0.75,
) -> str:
    """
    Normalizes a player/character name against canonical checklists using difflib and diacritic folding.

    Args:
        raw_name: Raw player string (e.g. 'Luka Doncic', 'Steph Curry', 'Wemby')
        category: Card category (e.g. 'Basketball', 'Baseball', 'Pokemon')
        canonical_dict: Optional override dictionary mapping category -> list of canonical names
        cutoff: difflib similarity threshold (0.0 to 1.0, default 0.75)

    Returns:
        Canonical player name string with pristine diacritics/casing, or cleaned raw_name if no match.
    """
    if raw_name is None:
        return ""
    clean_raw = re.sub(r"\s+", " ", str(raw_name).strip())
    if not clean_raw:
        return ""

    folded_raw = fold_string(clean_raw)

    # 1. Check alias dictionary
    if folded_raw in PLAYER_ALIASES:
        return PLAYER_ALIASES[folded_raw]

    # Resolve target canonical catalog
    lookup_catalog = canonical_dict if canonical_dict is not None else CANONICAL_PLAYERS

    # Scoped candidates for the given category
    scoped_candidates: list[str] = []
    if category and category in lookup_catalog:
        scoped_candidates = lookup_catalog[category]
    elif category:
        # Check case-insensitive category match
        for cat_key, cat_list in lookup_catalog.items():
            if cat_key.lower() == category.lower():
                scoped_candidates = cat_list
                break

    folded_map: dict[str, str] = {fold_string(c): c for c in scoped_candidates}

    # 2. Exact folded match in scoped category (handles diacritics instantly)
    if folded_raw in folded_map:
        return folded_map[folded_raw]

    # 3. Fuzzy matching in scoped category
    if folded_map:
        matches = difflib.get_close_matches(folded_raw, list(folded_map.keys()), n=1, cutoff=cutoff)
        if matches:
            return folded_map[matches[0]]

    # 4. Fallback: Search across all categories in catalog if not matched in scoped category
    all_candidates: list[str] = []
    for cand_list in lookup_catalog.values():
        all_candidates.extend(cand_list)

    all_folded_map = {fold_string(c): c for c in all_candidates}
    if folded_raw in all_folded_map:
        return all_folded_map[folded_raw]

    if not category or category not in lookup_catalog:
        global_matches = difflib.get_close_matches(folded_raw, list(all_folded_map.keys()), n=1, cutoff=cutoff)
        if global_matches:
            return all_folded_map[global_matches[0]]

    # 5. Zero-loss fallback: return cleaned original input
    return clean_raw


def normalize_set_name(
    raw_set: str,
    year: str = "",
    category: str = "",
    canonical_dict: Optional[dict[str, list[str]]] = None,
    cutoff: float = 0.75,
) -> str:
    """
    Normalizes a card set name against canonical set catalogs using difflib and prefix stripping.

    Args:
        raw_set: Raw set name (e.g. 'Prizm', 'Topps Chrome BB', 'Young Guns Series 1')
        year: 4-digit year string (e.g. '2020')
        category: Card category (e.g. 'Basketball', 'Hockey', 'Pokemon')
        canonical_dict: Optional override dictionary mapping category -> list of canonical set names
        cutoff: difflib similarity threshold (0.0 to 1.0, default 0.75)

    Returns:
        Canonical set name string or cleaned raw_set if no match.
    """
    if raw_set is None:
        return ""
    clean_raw = re.sub(r"\s+", " ", str(raw_set).strip())
    if not clean_raw:
        return ""

    # Strip year prefix if embedded in set name (e.g. '2020 Panini Prizm' -> 'Panini Prizm')
    if year:
        clean_raw = re.sub(rf"^{re.escape(str(year))}\s+", "", clean_raw, flags=re.IGNORECASE).strip()

    folded_raw = fold_string(clean_raw)

    # 1. Check alias dictionary
    if folded_raw in SET_ALIASES:
        return SET_ALIASES[folded_raw]

    # Resolve target canonical catalog
    lookup_catalog = canonical_dict if canonical_dict is not None else CANONICAL_SETS

    # Scoped candidates for the given category
    scoped_candidates: list[str] = []
    if category and category in lookup_catalog:
        scoped_candidates = lookup_catalog[category]
    elif category:
        for cat_key, cat_list in lookup_catalog.items():
            if cat_key.lower() == category.lower():
                scoped_candidates = cat_list
                break

    folded_map: dict[str, str] = {fold_string(c): c for c in scoped_candidates}

    # 2. Exact folded match in scoped category
    if folded_raw in folded_map:
        return folded_map[folded_raw]

    # 3. Fuzzy matching in scoped category
    if folded_map:
        matches = difflib.get_close_matches(folded_raw, list(folded_map.keys()), n=1, cutoff=cutoff)
        if matches:
            return folded_map[matches[0]]

    # 4. Fallback: Search all categories
    all_candidates: list[str] = []
    for cand_list in lookup_catalog.values():
        all_candidates.extend(cand_list)

    all_folded_map = {fold_string(c): c for c in all_candidates}
    if folded_raw in all_folded_map:
        return all_folded_map[folded_raw]

    if not category or category not in lookup_catalog:
        global_matches = difflib.get_close_matches(folded_raw, list(all_folded_map.keys()), n=1, cutoff=cutoff)
        if global_matches:
            return all_folded_map[global_matches[0]]

    # 5. Zero-loss fallback
    return clean_raw


# ============================================================================
# Card Formatting & Transformation Engine
# ============================================================================

def format_currency_value(val: Any) -> float:
    """Formats monetary values safely as float with 2 decimal precision."""
    if val is None or val == "":
        return 0.00
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0.00


def format_sold_price(val: Any) -> Any:
    """Formats sold price. Returns formatted float or empty string if unsold."""
    if val is None or val == "":
        return ""
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return ""


def format_card_row_for_card_ladder(
    row: dict[str, Any] | sqlite3.Row,
    apply_normalization: bool = True,
    normalize_player_fn: Optional[Any] = None,
    normalize_set_fn: Optional[Any] = None,
) -> dict[str, Any]:
    """
    Transforms a single SQLite card record into the strict 16-variable Card Ladder format.
    Preserves leading zeros on 'card_number' and excludes the 5 internal fields.
    """
    row_dict = dict(row) if not isinstance(row, dict) else row

    category = str(row_dict.get("category", "")).strip()
    year = str(row_dict.get("year", "")).strip()

    # Player Normalization
    player = str(row_dict.get("player", "")).strip()
    if apply_normalization:
        if normalize_player_fn:
            player = normalize_player_fn(player, category)
        else:
            player = normalize_player_name(player, category)

    # Set Normalization
    set_name = str(row_dict.get("set_name", "")).strip()
    if apply_normalization:
        if normalize_set_fn:
            set_name = normalize_set_fn(set_name, year, category)
        else:
            set_name = normalize_set_name(set_name, year, category)

    # Preserve leading zero string for card number
    raw_number = row_dict.get("card_number")
    if raw_number is None:
        card_number_str = ""
    else:
        card_number_str = str(raw_number).strip()

    # Map fields to exact 16 Card Ladder headers
    formatted_record: dict[str, Any] = {
        "Date Purchased": str(row_dict.get("date_purchased", "")).strip(),
        "Quantity": int(row_dict.get("quantity", 1)) if row_dict.get("quantity") else 1,
        "Player": player,
        "Year": year,
        "Set": set_name,
        "Variation": str(row_dict.get("variation", "")).strip(),
        "Number": card_number_str,
        "Category": category,
        "Condition": str(row_dict.get("condition", "Raw")).strip(),
        "Investment": format_currency_value(row_dict.get("investment")),
        "Estimated Value": format_currency_value(row_dict.get("estimated_value")),
        "Ladder ID": str(row_dict.get("ladder_id", "")).strip(),
        "Notes": str(row_dict.get("notes", "")).strip(),
        "Date Sold": str(row_dict.get("date_sold", "")).strip(),
        "Sold Price": format_sold_price(row_dict.get("sold_price")),
        "Image": str(row_dict.get("image", "")).strip(),
    }

    return formatted_record


def cards_to_card_ladder_dataframe(
    cards: Sequence[dict[str, Any] | sqlite3.Row],
    apply_normalization: bool = True,
    normalize_player_fn: Optional[Any] = None,
    normalize_set_fn: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Converts a sequence of raw card records into a validated Pandas DataFrame
    with exactly 16 Card Ladder columns and strict string dtypes on Number and Year.
    """
    if not cards:
        # Return empty DataFrame with exact 16 headers
        df = pd.DataFrame(columns=CARD_LADDER_COLUMNS)
        df["Number"] = df["Number"].astype(str)
        df["Year"] = df["Year"].astype(str)
        return df

    formatted_rows = [
        format_card_row_for_card_ladder(
            card,
            apply_normalization=apply_normalization,
            normalize_player_fn=normalize_player_fn,
            normalize_set_fn=normalize_set_fn,
        )
        for card in cards
    ]

    df = pd.DataFrame(formatted_rows, columns=CARD_LADDER_COLUMNS)

    # Force string dtype on critical leading-zero columns
    df["Number"] = df["Number"].fillna("").astype(str)
    df["Year"] = df["Year"].fillna("").astype(str)
    df["Date Purchased"] = df["Date Purchased"].fillna("").astype(str)
    df["Notes"] = df["Notes"].fillna("").astype(str)
    df["Variation"] = df["Variation"].fillna("").astype(str)
    df["Ladder ID"] = df["Ladder ID"].fillna("").astype(str)
    df["Date Sold"] = df["Date Sold"].fillna("").astype(str)
    df["Image"] = df["Image"].fillna("").astype(str)

    return df


transform_records_to_card_ladder_df = cards_to_card_ladder_dataframe


# ============================================================================
# CSV Chunking & File I/O Engine
# ============================================================================

def generate_chunk_filepath(base_path: str, part_num: int, total_parts: int) -> str:
    """
    Generates chunked output filename.
    If total_parts == 1, returns base_path.
    If total_parts > 1, returns '<dir>/<stem>_part<part_num><ext>'.
    """
    if total_parts <= 1:
        return base_path

    dirname, basename = os.path.split(base_path)
    stem, ext = os.path.splitext(basename)
    if not ext:
        ext = ".csv"
    chunk_filename = f"{stem}_part{part_num}{ext}"
    return os.path.join(dirname, chunk_filename) if dirname else chunk_filename


def export_dataframe_to_chunked_csvs(
    df: pd.DataFrame,
    output_path: str,
    max_batch_size: int = 500,
) -> tuple[int, list[str]]:
    """
    Exports a 16-column Card Ladder DataFrame to one or more CSV files,
    splitting into max_batch_size chunks if row count exceeds max_batch_size.
    Ensures safe directory creation and UTF-8 encoding.
    """
    # Enforce exact 16 columns
    df_clean = df[CARD_LADDER_COLUMNS].copy()

    total_rows = len(df_clean)
    if total_rows == 0:
        # Create empty file with headers
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        df_clean.to_csv(output_path, index=False, quoting=csv.QUOTE_MINIMAL, na_rep="")
        return (0, [output_path])

    if max_batch_size <= 0:
        max_batch_size = 500

    total_parts = math.ceil(total_rows / max_batch_size)
    generated_files: list[str] = []

    for part_idx in range(total_parts):
        start_row = part_idx * max_batch_size
        end_row = min(start_row + max_batch_size, total_rows)
        chunk_df = df_clean.iloc[start_row:end_row]

        target_file = generate_chunk_filepath(output_path, part_idx + 1, total_parts)
        parent_dir = os.path.dirname(target_file)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        chunk_df.to_csv(target_file, index=False, quoting=csv.QUOTE_MINIMAL, na_rep="")
        generated_files.append(target_file)

    return (total_rows, generated_files)


write_card_ladder_csv_chunks = export_dataframe_to_chunked_csvs


def fetch_records_for_export(
    db_path: str = DEFAULT_DB_PATH,
    status_filter: str = "CLEARED"
) -> list[dict[str, Any]]:
    """
    Queries records from SQLite database matching status_filter.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if not status_filter or status_filter.upper() == "ALL":
            cursor.execute("SELECT * FROM cards ORDER BY id ASC;")
        else:
            # Case-insensitive status matching
            cursor.execute(
                "SELECT * FROM cards WHERE UPPER(ai_status) = UPPER(?) ORDER BY id ASC;",
                (status_filter.strip(),),
            )
        return [dict(r) for r in cursor.fetchall()]


# ============================================================================
# Master Export API
# ============================================================================

def export_card_ladder_csv(
    db_path: str = DEFAULT_DB_PATH,
    output_path: str = "CardLadder_Bulk_Upload.csv",
    status_filter: str = "CLEARED",
    max_batch_size: int = 500,
    apply_normalization: bool = True,
) -> tuple[int, list[str]]:
    """
    Primary API entry point for Card Ladder CSV export.
    Reads records from SQLite database, applies fuzzy normalization,
    formats exact 16 Card Ladder columns, preserves leading zeros, and writes
    chunked CSV files (max 500 records per file).

    Args:
        db_path: Path to portfolio.db SQLite database.
        output_path: Target CSV output path (or base path if chunked).
        status_filter: AI status filter ('CLEARED', 'REVIEW VARIATION', 'NEEDS REVIEW', or 'ALL').
        max_batch_size: Maximum records per CSV file (default 500).
        apply_normalization: If True, normalizes Player and Set names via canonical catalogs.

    Returns:
        tuple[int, list[str]]: (total_records_exported, list_of_generated_file_paths)
    """
    rows = fetch_records_for_export(db_path=db_path, status_filter=status_filter)

    # Convert to 16-column DataFrame
    df = cards_to_card_ladder_dataframe(
        rows,
        apply_normalization=apply_normalization,
        normalize_player_fn=normalize_player_name if apply_normalization else None,
        normalize_set_fn=normalize_set_name if apply_normalization else None,
    )

    # Export to chunked CSVs
    return export_dataframe_to_chunked_csvs(
        df,
        output_path=output_path,
        max_batch_size=max_batch_size,
    )


# ============================================================================
# Forensic Validation Utility
# ============================================================================

def validate_card_ladder_csv(csv_path: str) -> dict[str, Any]:
    """
    Forensic validation utility for generated Card Ladder CSV files.
    Verifies header count, header names, header sequence, exclusion of internal fields,
    and row counts.
    """
    if not os.path.exists(csv_path):
        return {"valid": False, "error": f"File not found: {csv_path}"}

    with open(csv_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if headers is None:
            return {"valid": False, "error": "CSV file is empty"}

        if len(headers) != 16:
            return {
                "valid": False,
                "error": f"Expected exactly 16 headers, found {len(headers)}",
                "headers": headers,
            }

        if headers != CARD_LADDER_COLUMNS:
            return {
                "valid": False,
                "error": "Headers do not match canonical Card Ladder sequence",
                "found_headers": headers,
                "expected_headers": CARD_LADDER_COLUMNS,
            }

        # Check for forbidden internal fields
        forbidden_found = [h for h in headers if h.lower() in [f.lower() for f in EXCLUDED_INTERNAL_FIELDS]]
        if forbidden_found:
            return {
                "valid": False,
                "error": f"Forbidden internal fields present: {forbidden_found}",
            }

        row_count = 0
        number_samples: list[str] = []
        for row in reader:
            row_count += 1
            if len(row) != 16:
                return {
                    "valid": False,
                    "error": f"Row {row_count} has {len(row)} columns, expected 16",
                }
            # Col 6 is Number (0-indexed)
            number_samples.append(row[6])

    return {
        "valid": True,
        "row_count": row_count,
        "headers": headers,
        "number_samples": number_samples[:10],
    }
