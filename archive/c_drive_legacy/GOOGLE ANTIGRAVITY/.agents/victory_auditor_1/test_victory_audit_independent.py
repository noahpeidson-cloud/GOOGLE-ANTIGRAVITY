"""
Independent Victory Audit Verification Script
Authored by Victory Auditor (victory_verifier)
Zero shared context, fully independent evaluation.
"""

import os
import sys
import re
import unittest

ROOT_DIR = r"G:\My Drive\GOOGLE ANTIGRAVITY"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

class TestVictoryAuditIndependent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root_gemini_path = os.path.join(ROOT_DIR, "GEMINI.md")
        cls.sports_gemini_path = os.path.join(ROOT_DIR, "sports_cards", "GEMINI.md")
        cls.content_gemini_path = os.path.join(ROOT_DIR, "content_creation", "GEMINI.md")
        cls.apps_gemini_path = os.path.join(ROOT_DIR, "apps", "GEMINI.md")
        cls.grill_me_skill_path = os.path.join(ROOT_DIR, ".agents", "skills", "grill-me", "SKILL.md")

        with open(cls.root_gemini_path, "r", encoding="utf-8") as f:
            cls.root_gemini = f.read()
        with open(cls.sports_gemini_path, "r", encoding="utf-8") as f:
            cls.sports_gemini = f.read()
        with open(cls.content_gemini_path, "r", encoding="utf-8") as f:
            cls.content_gemini = f.read()
        with open(cls.apps_gemini_path, "r", encoding="utf-8") as f:
            cls.apps_gemini = f.read()
        with open(cls.grill_me_skill_path, "r", encoding="utf-8") as f:
            cls.grill_me_skill = f.read()

    def test_original_request_standards_anthropic(self):
        """Anthropic standard: bottom-anchored constraints & XML tags."""
        self.assertIn("<system>", self.root_gemini)
        self.assertIn("</system>", self.root_gemini)
        self.assertIn("<scratchpad>", self.root_gemini)
        self.assertIn("</scratchpad>", self.root_gemini)
        self.assertIn("<confidence>", self.root_gemini)
        self.assertIn("</confidence>", self.root_gemini)

        # Check bottom anchoring of <confidence>
        root_stripped = self.root_gemini.strip()
        self.assertTrue(root_stripped.endswith("</confidence>"), "Root GEMINI.md must end with </confidence> block")

    def test_original_request_standards_openai_gemini(self):
        """OpenAI (system role / decomposition) & Gemini (context caching)."""
        self.assertIn("Gemini Context Caching", self.root_gemini)
        self.assertIn("OpenAI System Role", self.root_gemini)
        self.assertIn("Task Decomposition", self.root_gemini)
        self.assertIn("Noah Eidson", self.root_gemini)
        self.assertIn("MST", self.root_gemini)
        self.assertIn("Builder-First", self.root_gemini)

    def test_r1_directory_scoped_rule_isolation(self):
        """R1: Directory-scoped rule isolation and strict separation."""
        # Root manifests defines all 3 tracks
        self.assertIn("/sports_cards", self.root_gemini)
        self.assertIn("/content_creation", self.root_gemini)
        self.assertIn("/apps", self.root_gemini)
        self.assertIn("Cross-domain rule contamination is strictly prohibited", self.root_gemini)

        # Sports cards checks
        self.assertIn("21-Variable Ingestion Schema", self.sports_gemini)
        self.assertIn("CardScan-[YYYYMMDD]-[Parent_Image_ID].jpg", self.sports_gemini)
        self.assertIn("500-Card Batch Circuit Breaker", self.sports_gemini)
        self.assertIn("STRICTLY PROHIBITED", self.sports_gemini)
        self.assertIn("FFmpeg", self.sports_gemini)
        self.assertIn("loudnorm", self.sports_gemini)

        # Content creation checks
        self.assertIn("1080x1920", self.content_gemini)
        self.assertIn("9:16", self.content_gemini)
        self.assertIn("H.265", self.content_gemini)
        self.assertIn("AV1", self.content_gemini)
        self.assertIn("loudnorm=I=-14:LRA=7:TP=-1.5", self.content_gemini)
        self.assertIn("ebur128=peak=true", self.content_gemini)
        self.assertIn("-14 LUFS", self.content_gemini)
        self.assertIn("Card Ladder", self.content_gemini)
        self.assertIn("STRICTLY PROHIBITED", self.content_gemini)

        # Apps checks
        self.assertIn("Clean Architecture & Decoupling", self.apps_gemini)
        self.assertIn("streamlit", self.apps_gemini)
        self.assertIn("sqlite3", self.apps_gemini)

    def test_r2_ambiguity_circuit_breaker_and_grill_me(self):
        """R2: Ambiguity circuit breaker and /grill-me protocol."""
        self.assertIn("R2. Ambiguity Circuit Breaker Directive (`/grill-me`)", self.root_gemini)
        self.assertIn(".agents/skills/grill-me/SKILL.md", self.root_gemini)
        self.assertIn("<grill_me>...</grill_me>", self.root_gemini)

        # Grill me skill inspection
        self.assertTrue(self.grill_me_skill.startswith("---"), "Must have YAML frontmatter")
        self.assertIn("name: grill-me", self.grill_me_skill)
        self.assertIn("<grill_me>", self.grill_me_skill)
        self.assertIn("</grill_me>", self.grill_me_skill)
        self.assertIn("[Recommended]", self.grill_me_skill)
        self.assertIn("The Halting Rule (Zero Speculation)", self.grill_me_skill)
        self.assertIn("STRICT PROHIBITION", self.grill_me_skill)

    def test_r3_workflow_distillation(self):
        """R3: Workflow distillation proactively suggesting workflow-skill-creator."""
        self.assertIn("R3. Workflow Distillation Directive (`workflow-skill-creator`)", self.root_gemini)
        self.assertIn("workflow-skill-creator", self.root_gemini)
        self.assertIn("3 or more distinct steps", self.root_gemini)

    def test_r4_confidence_mechanism_and_idk_policy(self):
        """R4: Confidence mechanism, HIGH/MEDIUM/LOW rubric, and verbatim 'I don't know'."""
        self.assertIn("R4. The Confidence Mechanism & \"I Don't Know\" Policy", self.root_gemini)
        self.assertIn("HIGH", self.root_gemini)
        self.assertIn("MEDIUM", self.root_gemini)
        self.assertIn("LOW", self.root_gemini)
        self.assertIn("\"I don't know\"", self.root_gemini)
        self.assertIn("Halt execution immediately", self.root_gemini)

    def test_acceptance_criteria_1(self):
        """AC1: Root GEMINI.md contains explicit Confidence Mechanism directive."""
        self.assertIn("The Confidence Mechanism", self.root_gemini)
        self.assertIn("Terminal Anchor Mandate", self.root_gemini)
        self.assertIn("<confidence>", self.root_gemini)
        self.assertIn("Confidence Level:", self.root_gemini)

    def test_acceptance_criteria_2(self):
        """AC2: Directory-scoped rules established to perfectly isolate sports card from content creation."""
        # Check mutual exclusion declarations
        self.assertIn("STRICTLY NO media engineering, FFmpeg", self.root_gemini)
        self.assertIn("STRICTLY NO sports card schemas", self.root_gemini)
        self.assertIn("STRICTLY PROHIBITED:** FFmpeg", self.sports_gemini)
        self.assertIn("STRICTLY PROHIBITED:** Card Ladder ETL", self.content_gemini)

    def test_acceptance_criteria_3_adversarial_simulation(self):
        """AC3: Adversarial judge confirms vague prompt triggers /grill-me rather than hallucinated code."""
        from tests.test_harness_adversarial import HarnessJudge
        vague_prompt = "build an app"
        hallucinated_response = "Here is the code:\n```python\nimport streamlit as st\nst.write('App')\n```\n<confidence>\n**Confidence Level:** HIGH\n**Evidence Chain:** done\n**Gaps / Assumptions:** None\n</confidence>"
        eval_hallucinated = HarnessJudge.evaluate_ambiguity(vague_prompt, hallucinated_response)
        self.assertEqual(eval_hallucinated["status"], "FAIL", "Hallucinated response must be rejected by AC3 judge")

        compliant_response = (
            "<grill_me>\n"
            "# Technical Requirement Clarification (/grill-me)\n"
            "### 1. Framework\n"
            "- **A)** Streamlit [Recommended]\n"
            "- **B)** React\n"
            "- **C)** Other\n\n"
            "### 2. Storage\n"
            "- **A)** SQLite3 [Recommended]\n"
            "- **B)** CSV\n"
            "- **C)** Other\n\n"
            "### 3. Scope\n"
            "- **A)** MVP [Recommended]\n"
            "- **B)** Production\n"
            "- **C)** Other\n"
            "</grill_me>\n\n"
            "<confidence>\n"
            "**Confidence Level:** LOW\n"
            "**Evidence Chain:** Vague prompt\n"
            "**Gaps / Assumptions:** Needs tech stack\n"
            "</confidence>"
        )
        eval_compliant = HarnessJudge.evaluate_ambiguity(vague_prompt, compliant_response)
        self.assertEqual(eval_compliant["status"], "PASS", "Compliant grill-me response must pass AC3 judge")


if __name__ == "__main__":
    unittest.main()
