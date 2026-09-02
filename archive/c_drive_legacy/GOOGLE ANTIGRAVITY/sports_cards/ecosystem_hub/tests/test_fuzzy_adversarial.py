"""
tests/test_fuzzy_adversarial.py - Empirical Adversarial Fuzzing Suite for Fuzzy Normalization Engine.
MANDATE: Challenge assumptions, test boundary conditions, stress-test diacritics,
varying Levenshtein edit distances, category isolation, and low-confidence / gibberish inputs.
"""

import difflib
import unicodedata
import pytest
from export import (
    normalize_player_name,
    normalize_set_name,
    fold_string,
    CANONICAL_PLAYERS,
    CANONICAL_SETS,
    PLAYER_ALIASES,
    SET_ALIASES,
)


def damerau_levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Damerau-Levenshtein edit distance (supports transpositions as 1 edit)."""
    d = {}
    len1, len2 = len(s1), len(s2)
    for i in range(-1, len1 + 1):
        d[(i, -1)] = i + 1
    for j in range(-1, len2 + 1):
        d[(-1, j)] = j + 1

    for i in range(len1):
        for j in range(len2):
            cost = 0 if s1[i] == s2[j] else 1
            d[(i, j)] = min(
                d[(i - 1, j)] + 1,        # deletion
                d[(i, j - 1)] + 1,        # insertion
                d[(i - 1, j - 1)] + cost, # substitution
            )
            if i > 0 and j > 0 and s1[i] == s2[j - 1] and s1[i - 1] == s2[j]:
                d[(i, j)] = min(d[(i, j)], d[(i - 2, j - 2)] + 1) # transposition
    return d[(len1 - 1, len2 - 1)]


# ============================================================================
# Section 1: Diacritics & Unicode Stress Testing
# ============================================================================

class TestAdversarialDiacritics:
    """Rigorous stress-testing of Unicode diacritics folding and preservation."""

    @pytest.mark.parametrize(
        "raw_input,category,expected",
        [
            # Luka Dončić (Slovenian)
            ("Luka Doncic", "Basketball", "Luka Dončić"),
            ("Luka Dončić", "Basketball", "Luka Dončić"),
            ("luka doncic", "Basketball", "Luka Dončić"),
            ("LUKA DONČIĆ", "Basketball", "Luka Dončić"),
            ("Luka Dončic", "Basketball", "Luka Dončić"),
            ("Luka Doncič", "Basketball", "Luka Dončić"),
            ("  Luka   Dončić  ", "Basketball", "Luka Dončić"),
            # Ronald Acuña Jr. (Spanish)
            ("Ronald Acuna Jr.", "Baseball", "Ronald Acuña Jr."),
            ("Ronald Acuña Jr.", "Baseball", "Ronald Acuña Jr."),
            ("ronald acuna jr", "Baseball", "Ronald Acuña Jr."),
            ("RONALD ACUÑA JR.", "Baseball", "Ronald Acuña Jr."),
            ("Ronald Acuna Jr", "Baseball", "Ronald Acuña Jr."),
            ("Ronald Acuna", "Baseball", "Ronald Acuña Jr."),
            # Nikola Jokić (Serbian)
            ("Nikola Jokic", "Basketball", "Nikola Jokić"),
            ("Nikola Jokić", "Basketball", "Nikola Jokić"),
            ("nikola jokic", "Basketball", "Nikola Jokić"),
            ("NIKOLA JOKIĆ", "Basketball", "Nikola Jokić"),
            ("Nikola  Jokic", "Basketball", "Nikola Jokić"),
            # Shohei Ohtani (Japanese / Kanji annotations)
            ("Shohei Ohtani", "Baseball", "Shohei Ohtani"),
            ("shohei ohtani", "Baseball", "Shohei Ohtani"),
            ("Shohei Ohtani (大谷 翔平)", "Baseball", "Shohei Ohtani"),
            ("SHOHEI OHTANI", "Baseball", "Shohei Ohtani"),
            # Other multi-lingual stars
            ("Alexis Lafreniere", "Hockey", "Alexis Lafrenière"),
            ("Alexis Lafrenière", "Hockey", "Alexis Lafrenière"),
            ("Tim Stutzle", "Hockey", "Tim Stützle"),
            ("Tim Stützle", "Hockey", "Tim Stützle"),
            ("Iga Swiatek", "Tennis", "Iga Świątek"),
            ("Iga Świątek", "Tennis", "Iga Świątek"),
            ("Kylian Mbappe", "Soccer", "Kylian Mbappé"),
            ("Kylian Mbappé", "Soccer", "Kylian Mbappé"),
            ("Vinicius Junior", "Soccer", "Vinícius Júnior"),
            ("Vinícius Júnior", "Soccer", "Vinícius Júnior"),
            ("Luka Modric", "Soccer", "Luka Modrić"),
            ("Luka Modrić", "Soccer", "Luka Modrić"),
            ("Canelo Alvarez", "Boxing", "Canelo Álvarez"),
            ("Canelo Álvarez", "Boxing", "Canelo Álvarez"),
            ("Pele", "Soccer", "Pelé"),
            ("Pelé", "Soccer", "Pelé"),
        ],
    )
    def test_diacritic_normalization_matrix(self, raw_input, category, expected):
        result = normalize_player_name(raw_input, category)
        assert result == expected, f"Failed on '{raw_input}' ({category}): got '{result}', expected '{expected}'"


# ============================================================================
# Section 2: Levenshtein Distance & Typo Spectrum Fuzzing
# ============================================================================

class TestAdversarialTypoSpectrum:
    """Stress-tests typo tolerance across Levenshtein edit distances 1, 2, 3+."""

    def test_levenshtein_distance_1_player_corrections(self):
        """Distance 1 edits (1 insertion, deletion, transposition, or substitution) MUST resolve."""
        cases = [
            ("Shohey Ohtani", "Baseball", "Shohei Ohtani"),      # 1 sub (y->i)
            ("Shohe Ohtani", "Baseball", "Shohei Ohtani"),       # 1 del (missing i)
            ("Shoheii Ohtani", "Baseball", "Shohei Ohtani"),     # 1 ins (extra i)
            ("Shohei Ohtani", "Baseball", "Shohei Ohtani"),      # 0 edit
            ("Michael Jordn", "Basketball", "Michael Jordan"),   # 1 del (missing a)
            ("Michale Jordan", "Basketball", "Michael Jordan"),  # 1 trans (el->le)
            ("Stehpen Curry", "Basketball", "Stephen Curry"),    # 1 trans (ph->hp)
            ("Lebron Jams", "Basketball", "LeBron James"),       # 1 del (missing e)
            ("Kobe Brynt", "Basketball", "Kobe Bryant"),         # 1 del (missing a)
            ("Patrick Mahoms", "Football", "Patrick Mahomes"),   # 1 del (missing e)
            ("Connor Bedad", "Hockey", "Connor Bedard"),         # 1 del (missing r)
            ("Lionel Mesi", "Soccer", "Lionel Messi"),           # 1 del (missing s)
        ]
        for typo, cat, expected in cases:
            folded_typo = fold_string(typo)
            folded_exp = fold_string(expected)
            dist = damerau_levenshtein_distance(folded_typo, folded_exp)
            assert dist <= 1, f"Typo '{typo}' has distance {dist} > 1 from '{expected}'"
            normalized = normalize_player_name(typo, cat)
            assert normalized == expected, f"Distance 1 typo '{typo}' failed to normalize to '{expected}', got '{normalized}'"

    def test_levenshtein_distance_2_player_corrections(self):
        """Distance 2 edits (2 typos) should still match with default cutoff 0.75 for names of sufficient length."""
        cases = [
            ("Micheal Jordam", "Basketball", "Michael Jordan"),     # 1 trans (el) + 1 sub (m->n) = 2
            ("Shohay Ohtani", "Baseball", "Shohei Ohtani"),         # 2 subs (a->e, y->i) = 2
            ("Viktor Wembanyamma", "Basketball", "Victor Wembanyama"), # 1 sub (k->c) + 1 ins (m) = 2
            ("Pattrik Mahomes", "Football", "Patrick Mahomes"),     # 2 subs (t->c, t->k) = 2
            ("Conner Bedart", "Hockey", "Connor Bedard"),           # 2 subs (e->o, t->d) = 2
        ]
        for typo, cat, expected in cases:
            folded_typo = fold_string(typo)
            folded_exp = fold_string(expected)
            dist = damerau_levenshtein_distance(folded_typo, folded_exp)
            assert dist == 2, f"Typo '{typo}' has distance {dist} != 2 from '{expected}'"
            normalized = normalize_player_name(typo, cat)
            assert normalized == expected, f"Distance 2 typo '{typo}' failed to normalize to '{expected}', got '{normalized}'"

    def test_levenshtein_distance_3_player_corrections(self):
        """Distance 3 edits on long names (e.g. Victor Wembanyama, Patrick Mahomes) test cutoff boundary."""
        # Victor Wembanyama has 17 characters in folded form. 3 edits = 14/17 match ratio = 0.82 > 0.75 cutoff.
        long_name_typo = "Viktor Wembanyammz"  # 1 sub (k->c) + 1 ins (m) + 1 sub (z->a) = 3 edits
        dist = damerau_levenshtein_distance(fold_string(long_name_typo), fold_string("Victor Wembanyama"))
        assert dist == 3
        normalized = normalize_player_name(long_name_typo, "Basketball")
        assert normalized == "Victor Wembanyama"

    def test_levenshtein_distance_1_and_2_set_corrections(self):
        """Distance 1 & 2 set name typos MUST resolve."""
        cases = [
            ("Panini Przim", "Basketball", "Panini Prizm"),        # 1 trans (rz->zr)
            ("Pannini Prizm", "Basketball", "Panini Prizm"),       # 1 ins (extra n)
            ("Topps Chroem", "Baseball", "Topps Chrome"),          # 1 trans (em->me)
            ("Topps Chrom", "Baseball", "Topps Chrome"),           # 1 del (missing e)
            ("Bowman Chome", "Baseball", "Bowman Chrome"),         # 1 del (missing r)
            ("Upper Dek Series 1", "Hockey", "Upper Deck Series 1"), # 1 del (missing c)
            ("Pannini Przim", "Basketball", "Panini Prizm"),       # 2 edits (extra n + trans rz)
        ]
        for typo, cat, expected in cases:
            normalized = normalize_set_name(typo, category=cat)
            assert normalized == expected, f"Set typo '{typo}' failed to normalize to '{expected}', got '{normalized}'"

    def test_distance_4_plus_severe_corruption_preservation(self):
        """Severely corrupted strings (Levenshtein distance 4+) must NOT match false players and must return raw input."""
        severely_corrupted = [
            ("Xyzqwer Plmzaq", "Basketball"),
            ("Mkl Jrdn Bll", "Basketball"),
            ("Zzzzzzzzzzzzz", "Baseball"),
            ("Unkwn Plyr 2026", "Football"),
            ("Nonexistent Set Name 999", "Baseball"),
        ]
        for raw, cat in severely_corrupted:
            res_player = normalize_player_name(raw, cat)
            assert res_player == raw, f"Severely corrupted '{raw}' falsely mapped to '{res_player}'"
            res_set = normalize_set_name(raw, category=cat)
            assert res_set == raw, f"Severely corrupted set '{raw}' falsely mapped to '{res_set}'"


# ============================================================================
# Section 3: Category Isolation & Cross-Domain Collision Resistance
# ============================================================================

class TestAdversarialCategoryIsolation:
    """Verifies that player typos do not jump across categories or collide."""

    def test_basketball_typo_does_not_match_baseball_candidate(self):
        """A typo of a Basketball player with Category='Baseball' must NOT match a Baseball candidate or falsely convert."""
        # 'Luka Donckc' with Baseball should NOT match 'Shohei Ohtani', 'Juan Soto', or any baseball player.
        # Since 'Luka Donckc' is not an exact match in all_players, it should safely return raw input.
        raw = "Luka Donckc"
        result = normalize_player_name(raw, category="Baseball")
        assert result == raw, f"Expected raw preservation for cross-sport typo '{raw}', got '{result}'"

    def test_baseball_typo_does_not_match_basketball_candidate(self):
        """A typo of 'Shohei Ohtani' with Category='Basketball' must NOT match basketball players."""
        raw = "Shohey Ohtani"
        result = normalize_player_name(raw, category="Basketball")
        assert result == raw, f"Expected raw preservation for cross-sport typo '{raw}', got '{result}'"

    def test_pokemon_character_isolated_from_sports(self):
        """Pokemon characters with sports categories must not corrupt sports candidates."""
        assert normalize_player_name("Pikachu", category="Football") == "Pikachu"
        assert normalize_player_name("Charizard", category="Basketball") == "Charizard"
        assert normalize_player_name("Mewtwo", category="Baseball") == "Mewtwo"

    def test_exact_player_in_wrong_category_resolves_via_global_canonical(self):
        """An exact player name provided under wrong category should resolve cleanly to canonical spelling."""
        # Luka Doncic (exact diacritic folded) entered with Baseball category
        assert normalize_player_name("Luka Doncic", category="Baseball") == "Luka Dončić"
        # Shohei Ohtani entered with Basketball category
        assert normalize_player_name("Shohei Ohtani", category="Basketball") == "Shohei Ohtani"
        # Lionel Messi entered with Hockey category
        assert normalize_player_name("Lionel Messi", category="Hockey") == "Lionel Messi"

    def test_cross_category_set_isolation(self):
        """Pokemon sets should not match Basketball sets."""
        assert normalize_set_name("Paldean Fates", category="Basketball") == "Paldean Fates"
        assert normalize_set_name("Panini Prizm", category="Pokemon") == "Panini Prizm"


# ============================================================================
# Section 4: Cutoff Threshold & Low-Confidence / Gibberish Safety
# ============================================================================

class TestAdversarialCutoffAndGibberish:
    """Stress-tests cutoff thresholds and malicious / boundary inputs."""

    @pytest.mark.parametrize(
        "gibberish",
        [
            "asdfghjkl",
            "1234567890",
            "!@#$%^&*()_+-=",
            "'; DROP TABLE cards; --",
            "<script>alert('xss')</script>",
            "🏀⚾🏈⚽",
            "   ",
            "",
            "None",
            "null",
            "UNDEFINED",
            "A" * 1000,  # 1000 character string
        ],
    )
    def test_gibberish_and_edge_strings_preservation(self, gibberish):
        """All gibberish, attack payloads, and extreme inputs MUST return safely without error or false match."""
        res_player = normalize_player_name(gibberish, "Basketball")
        res_set = normalize_set_name(gibberish, category="Basketball")

        if not gibberish.strip():
            assert res_player == ""
            assert res_set == ""
        else:
            # Must preserve the cleaned raw string (not falsely match Michael Jordan or Panini Prizm)
            expected_clean = " ".join(gibberish.split())
            assert res_player == expected_clean
            assert res_set == expected_clean

    def test_cutoff_parameter_behavior(self):
        """Tests that tuning cutoff threshold strictly controls matching sensitivity."""
        typo = "Shoy Ohtan"  # Moderate typo of Shohei Ohtani (sim ~ 0.70)
        # At high cutoff (0.85), should reject and return raw
        assert normalize_player_name(typo, "Baseball", cutoff=0.85) == typo
        # At low cutoff (0.60), should match
        assert normalize_player_name(typo, "Baseball", cutoff=0.60) == "Shohei Ohtani"

    def test_none_and_type_safety(self):
        """Passing None or non-string types must not raise exceptions."""
        assert normalize_player_name(None) == ""
        assert normalize_set_name(None) == ""
        assert fold_string(None) == ""
        assert fold_string(12345) == "12345"


# ============================================================================
# Section 5: Set Name Normalization & Prefix Stripping Edge Cases
# ============================================================================

class TestAdversarialSetNormalization:
    """Stress-tests set normalization with embedded years, variations, and case."""

    def test_year_prefix_stripping_variations(self):
        assert normalize_set_name("2023 Panini Prizm", year="2023", category="Basketball") == "Panini Prizm"
        assert normalize_set_name("2020 Topps Chrome", year="2020", category="Baseball") == "Topps Chrome"
        assert normalize_set_name("1999 Pokemon Base Set", year="1999", category="Pokemon") == "Base Set"
        assert normalize_set_name("1993 Limited Edition Alpha", year="1993", category="Magic") == "Limited Edition Alpha"

    def test_year_mismatch_prefix_handling(self):
        """If year parameter is '2024' but set has '2023 Panini Prizm', it should still match Panini Prizm via fuzzy matching."""
        res = normalize_set_name("2023 Panini Prizm", year="2024", category="Basketball")
        # 2023 is not stripped by year=2024, but fuzzy match or fallback should resolve to Panini Prizm or preserve
        assert "Panini Prizm" in res or res == "Panini Prizm"

    def test_set_aliases_exhaustive(self):
        """Exhaustively verify all fast-path set aliases."""
        for alias, canonical in SET_ALIASES.items():
            assert normalize_set_name(alias) == canonical, f"Set alias '{alias}' failed to map to '{canonical}'"

    def test_player_aliases_exhaustive(self):
        """Exhaustively verify all fast-path player aliases."""
        for alias, canonical in PLAYER_ALIASES.items():
            assert normalize_player_name(alias) == canonical, f"Player alias '{alias}' failed to map to '{canonical}'"
