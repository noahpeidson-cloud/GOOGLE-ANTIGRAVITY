# Local copy of agent-ml-optimization-loop
Source: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\agent-ml-optimization-loop\SKILL.md`

## Core Philosophy
Subagents must not operate blindly. Execution metrics must be captured, analyzed via localized Machine Learning, and autonomously corrected when drift occurs, strictly adhering to the 'No Hallucinated Tooling' workspace mandate.

## Implementation Protocol
1. Localized Telemetry Hook
2. Pandas/NumPy-Native K-Means Evaluation (The Judge)
   - Vector Embeddings: Extract local embeddings (N, 5).
   - Semantic Clustering: Calculate Euclidean distances using numpy/pandas.
   - Hallucination / Drift Detection: Compute semantic entropy (intra-cluster dispersion). Must execute <5ms locally.
3. Autonomous Correction (ProTeGi Textual Gradients)
   - When cluster identifies semantic entropy, execute ProTeGi critique.
   - Generate actionable rule refinement advice (e.g. tuning context rot age thresholds, whitelist additions, socket cleanup hooks, manifest length guidelines).
