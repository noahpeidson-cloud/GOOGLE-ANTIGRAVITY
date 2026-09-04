# Project: Antigravity-Native AI Harness (Anti-Drift & Anti-Hallucination)

## Architecture
- **Root Manifest & Router**: G:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md
  - Global steering & workspace routing
  - System role & context caching boundaries
  - Ambiguity circuit breaker (/grill-me) trigger
  - Workflow distillation trigger (workflow-skill-creator)
  - Terminal-anchored Confidence Metric & Anti-Drift Guardrails
- **Domain-Scoped Rule Isolation**:
  - G:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\GEMINI.md: 21-variable sports card schema, Card Ladder ETL, SQLite/Pandas
  - G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\GEMINI.md: Media engineering, 9:16 vertical MP4, H.265/AV1, two-pass loudnorm, FFmpeg
  - G:\My Drive\GOOGLE ANTIGRAVITY\apps\GEMINI.md: Clean architecture, frontend/backend modularity
- **Custom Skills**:
  - G:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\grill-me\SKILL.md: Ambiguity Circuit Breaker interrogation protocol
- **Adversarial Verification & Test Harness**:
  - Automated test runner verifying Ambiguity (/grill-me trigger on 'build an app'), Confidence Mechanism ('I don't know' on non-HIGH), and Directory Isolation.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | R1: Directory Rule Isolation | Create /sports_cards, /content_creation, /apps directories with localized GEMINI.md files + root routing | M1 | ORIGINAL_REQUEST §R1 |
| 2 | R2: Ambiguity Circuit Breaker | Implement /grill-me skill and root GEMINI.md circuit breaker protocol | M1 | ORIGINAL_REQUEST §R2 |
| 3 | R3: Workflow Distillation | Proactive suggestion of workflow-skill-creator for novel multi-step tasks | M1 | ORIGINAL_REQUEST §R3 |
| 4 | R4: Confidence Mechanism | Terminal-anchored Confidence Metric & mandatory 'I don't know' halt policy | M1 | ORIGINAL_REQUEST §R4 |
| 5 | Standards Compliance | Anthropic bottom-anchoring & XML tags, OpenAI chaining & system role, Gemini caching structure | M1 | ORIGINAL_REQUEST §Standards |
| 6 | Adversarial Evaluation Suite | Automated judge harness validating vague prompt handling, confidence metric, and domain isolation | M2 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | AI Harness Implementation | Root GEMINI.md, directory GEMINI.md files, grill-me SKILL.md, rule isolation | Survey Complete | DONE |
| 2 | Review, Forensic Audit & Adversarial Verification | 2 Reviewers, 1 Forensic Auditor, 2 Adversarial Challengers validating all Acceptance Criteria | M1 | DONE |

## Code Layout
- GEMINI.md (Project root)
- sports_cards/GEMINI.md
- content_creation/GEMINI.md
- pps/GEMINI.md
- .agents/skills/grill-me/SKILL.md
- 	ests/test_harness_adversarial.py
- 	ests/test_challenger_stress.py
- 	ests/test_harness_stress_challenger.py
