# Orchestrator Plan: Antigravity Control Plane Refactor

## Objective
Build and verify the Antigravity Control Plane implementing the Hierarchical Supervisor Pattern in LangGraph at `C:\Users\noahp\teamwork_projects\antigravity_control_plane`.

## Phase 0: Survey & Scope Mapping (Current)
- Dispatch 3 parallel exploratory subagents:
  1. `spec_miner_routing`: Investigate LangGraph Hierarchical Supervisor pattern, `with_structured_output`, `Command(update=..., goto='supervisor')`, and `bind_tools` contracts.
  2. `spec_miner_state`: Investigate PostgreSQL state management with `psycopg_pool`, TypedDict state schemas, context pruning, and checkpointers.
  3. `spec_miner_subsystems`: Investigate existing Antigravity agent patterns (Social Deployer, Mobile Zero-Touch, Deep Research) and mock fixtures/test harness architecture.
- Aggregate findings into `PROJECT.md` (Architecture, Feature Inventory, Milestones, Interface Contracts, Code Layout) and `TEST_INFRA.md`.

## Phase 1: Test Infrastructure & Decomposition Setup
- Create `TEST_INFRA.md` with 4-tier test case methodology.
- Finalize `PROJECT.md` milestones:
  - M1: State Management & Checkpointer (`state.py`, PostgreSQL pool integration)
  - M2: Stateless Worker Subsystems (`workers/` with `bind_tools` and `Command` handoffs)
  - M3: Central Supervisor Orchestrator (`supervisor.py` with `with_structured_output` Decision-First routing)
  - M4: Deterministic End-to-End Test Suite (`test_orchestrator.py` and mock harness)
- Publish `TEST_READY.md`.

## Phase 2: Implementation & Verification Loops
- Execute Milestones M1 through M4 using the standard iteration cycle:
  - Worker implementation
  - Independent Reviewers (2)
  - Adversarial Challengers (2)
  - Forensic Integrity Auditor (1)
  - Gate evaluation

## Phase 3: Final Acceptance & Reporting
- Full E2E pytest execution verification (100% pass, no infinite loops, proper PostgreSQL checkpointer support).
- Report results to parent orchestrator.
