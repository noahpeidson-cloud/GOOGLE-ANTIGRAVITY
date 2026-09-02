# Milestone M3: Central Supervisor Orchestrator — Test Architecture & Edge Case Analysis

## Executive Summary
This analysis establishes the comprehensive testing architecture, mock LLM structured output fixtures, and edge-case resilience strategies for Milestone M3 (**Central Supervisor Orchestrator**) of the Antigravity Control Plane.

Milestone M3 consolidates isolated worker subsystems (`social_worker`, `mobile_worker`, `research_worker`) under a canonical entrypoint (`supervisor.py`) implementing the **Decision-First Hybrid Routing Pattern** via `with_structured_output(RoutingDecision)` and LangGraph's dynamic `Command` handoff mechanism.

This report formulates:
1. **The 5-Tier Test Suite Specification for `tests/test_supervisor.py`** covering `schemas.py` and `supervisor.py`.
2. **Deterministic Mock LLM Structured Output Fixtures in `tests/conftest.py`** supporting `with_structured_output(RoutingDecision)`, sequential response queues, dynamic dispatch callbacks, and adversarial fault injection.
3. **Comprehensive Edge Case & Boundary Coverage Matrix** detailing concrete handling and testing for malformed LLM payloads, empty user requests, recursion limit exhaustion, and dual sync/async checkpointer compilation.

---

## 1. Architectural Blueprint: `schemas.py` & `supervisor.py`

### 1.1 Decision Schema (`schemas.py`)
The routing engine strictly uses Pydantic structured output models rather than tool calling for intent routing:

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

class RoutingDecision(BaseModel):
    """
    Structured classification decision produced by the Supervisor routing model.
    """
    next_node: Literal["social_worker", "mobile_worker", "research_worker", "FINISH"] = Field(
        description="Target worker node or FINISH to conclude execution."
    )
    reasoning: str = Field(
        default="",
        description="Justification and explanation of why this routing decision was selected."
    )
    instructions: str = Field(
        default="",
        description="Specific instructions or context to forward to the target worker node or user summary."
    )
```

### 1.2 Supervisor Orchestrator (`supervisor.py`)
The supervisor node acts as the central hub:
- Validates iteration boundaries (`iteration_count < max_iterations`).
- Increments `iteration_count` by 1.
- Classifies user intent and context using `llm.with_structured_output(RoutingDecision)` (or deterministic regex heuristics if LLM is omitted).
- Returns LangGraph `Command(goto=target, update={...})` where target is either a registered worker node or `END`.
- Implements catch-all exception shields for malformed LLM responses, invalid destinations, or API errors, transitioning cleanly to `END` with `status="FAILED"` rather than crashing.

---

## 2. Mock LLM Structured Output Fixtures (`tests/conftest.py`)

### 2.1 `MockStructuredChatModel` Design
To achieve zero network flakiness and sub-2-second deterministic test runs, `tests/conftest.py` will provide `MockStructuredChatModel`.

```python
from typing import Any, Callable, List, Optional, Sequence, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable

from schemas import RoutingDecision

class MockStructuredChatModel(BaseChatModel):
    """
    Deterministic mock chat model supporting `with_structured_output` and `bind_tools`.
    Supports FIFO response queuing, dynamic response callbacks, and exception injection.
    """
    responses: List[Any] = []
    dynamic_responder: Optional[Callable[[List[BaseMessage]], Any]] = None

    @property
    def _llm_type(self) -> str:
        return "mock-structured-chat"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if not self.responses:
            msg = AIMessage(content="Default mock text response")
            return ChatResult(generations=[ChatGeneration(message=msg)])

        resp = self.responses.pop(0) if self.responses else "Default mock text"
        if isinstance(resp, Exception):
            raise resp
        if isinstance(resp, BaseMessage):
            msg = resp
        elif isinstance(resp, dict):
            msg = AIMessage(content=resp.get("content", ""), tool_calls=resp.get("tool_calls", []))
        else:
            msg = AIMessage(content=str(resp))
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable:
        parent = self

        class StructuredMockRunnable(Runnable):
            def invoke(self, input_val: Any, config: Optional[Any] = None) -> Any:
                if parent.dynamic_responder is not None:
                    msgs = input_val if isinstance(input_val, list) else [input_val]
                    return parent.dynamic_responder(msgs)

                if not parent.responses:
                    return RoutingDecision(
                        next_node="FINISH",
                        reasoning="Default mock completion",
                        instructions="Task finished",
                    )

                resp = parent.responses.pop(0)
                if isinstance(resp, Exception):
                    raise resp
                if isinstance(resp, dict):
                    return schema(**resp)
                return resp

            async def ainvoke(self, input_val: Any, config: Optional[Any] = None) -> Any:
                return self.invoke(input_val, config)

        return StructuredMockRunnable()
```

### 2.2 Pytest Fixtures in `tests/conftest.py`
1. `mock_structured_llm`: Standard mock LLM producing `FINISH` decision.
2. `mock_supervisor_llm_factory`: Callable fixture generating configured `MockStructuredChatModel` instances from response lists or functions.
3. `mock_multi_turn_llm`: Multi-step routing model (`research_worker` -> `social_worker` -> `FINISH`).
4. `mock_failing_llm`: Model configured to throw `RuntimeError("LLM API 503 Overloaded")`.

---

## 3. Comprehensive 5-Tier Unit Test Suite (`tests/test_supervisor.py`)

The test suite will contain 35+ test cases partitioned across 5 rigorous quality tiers.

### 3.1 Tier 1: Feature Coverage (Happy Path & Schema Validation)
- **`test_routing_decision_schema_valid_nodes()`**: Validates Pydantic instantiation and serialization for `"social_worker"`, `"mobile_worker"`, `"research_worker"`, and `"FINISH"`.
- **`test_routing_decision_defaults_and_serialization()`**: Validates default values (`reasoning=""`, `instructions=""`), `model_dump()`, and `model_dump_json()`.
- **`test_supervisor_node_routes_to_social_worker()`**: Verifies `supervisor_node` returns `Command(goto="social_worker")`, sets `status="RUNNING"`, `next_worker="social_worker"`, and increments `iteration_count`.
- **`test_supervisor_node_routes_to_mobile_worker()`**: Verifies routing to `mobile_worker`.
- **`test_supervisor_node_routes_to_research_worker()`**: Verifies routing to `research_worker`.
- **`test_supervisor_node_finishes_to_end()`**: Verifies classification of `FINISH` returns `Command(goto=END)`, sets `status="COMPLETED"`, and clears `next_worker=None`.
- **`test_supervisor_audit_history_logging()`**: Verifies structured ISO-timestamped records appended to `execution_history`.
- **`test_supervisor_deterministic_fallback_no_llm()`**: Verifies regex/keyword intent classification when `llm=None`.
- **`test_create_control_plane_graph_structure()`**: Verifies compiled `StateGraph` contains all worker nodes, supervisor node, and entry edge `START -> supervisor`.

### 3.2 Tier 2: Boundary & Corner Cases
- **`test_max_iterations_exhaustion_halts_execution()`**: Verifies when `iteration_count >= max_iterations`, supervisor triggers recursion guard, sets `status="TERMINATED_LOOP_LIMIT"`, and transitions to `END` without invoking LLM or workers.
- **`test_single_iteration_max_limit_boundary()`**: Verifies execution with `max_iterations=1` executes exactly one turn and terminates.
- **`test_corrupted_counter_overflow_boundary()`**: Verifies when `iteration_count > max_iterations` in input state, guard halts immediately.
- **`test_empty_user_request_and_minimal_state()`**: Verifies `create_initial_state("")` with empty messages is safely handled without raising `KeyError` or `IndexError`.
- **`test_whitespace_only_user_prompt()`**: Verifies inputs like `"   \n\t   "` are normalized without crash.
- **`test_massive_prompt_context_assembly()`**: Verifies state with large message payloads (50KB+) builds supervisor prompt cleanly.
- **`test_malformed_llm_payload_missing_fields()`**: Verifies missing `next_node` in LLM output is caught and handled safely.
- **`test_invalid_destination_node_rejection()`**: Verifies LLM output specifying nonexistent worker (e.g. `"database_worker"`) is rejected and transitions to `FAILED`.

### 3.3 Tier 3: Cross-Feature Combinations & Checkpointers
- **`test_hub_and_spoke_worker_isolation()`**: Verifies workers cannot route to each other and strictly return to `supervisor` via `Command(goto="supervisor")`.
- **`test_pairwise_routing_sequence_social_mobile()`**: Verifies sequential dispatch `supervisor -> social_worker -> supervisor -> mobile_worker -> supervisor -> FINISH -> END`.
- **`test_pairwise_routing_sequence_research_social()`**: Verifies sequential dispatch `supervisor -> research_worker -> supervisor -> social_worker -> supervisor -> FINISH -> END`.
- **`test_full_pipeline_traversal_all_workers()`**: Verifies traversal across all 3 workers in a single graph invocation.
- **`test_sync_checkpointer_memory_saver_persistence()`**: Verifies `MemorySaver` saves checkpoint state between nodes and state can be inspected with `graph.get_state(config)`.
- **`test_sync_checkpointer_postgres_saver_mock()`**: Verifies graph compilation and invocation with mock `PostgresSaver`.
- **`test_async_checkpointer_ainvoke_persistence()`**: Verifies `graph.ainvoke()` with `MemorySaver` and state retrieval via `graph.aget_state(config)`.
- **`test_async_checkpointer_async_postgres_saver_mock()`**: Verifies graph compilation and async execution with mock `AsyncPostgresSaver`.

### 3.4 Tier 4: Real-World Application Scenarios
- **`test_scenario_social_media_campaign_dispatch()`**:
  - Prompt: `"Publish our new marketing video to Facebook and verify ADB metrics."`
  - Verifies: Supervisor -> `social_worker` -> Tool execution -> Handoff -> Supervisor -> `FINISH` (status `COMPLETED`).
- **`test_scenario_mobile_termux_automation()`**:
  - Prompt: `"Launch Termux on connected Android device, inject update script, and tap confirmation."`
  - Verifies: Supervisor -> `mobile_worker` -> Termux/ADB tools -> Handoff -> Supervisor -> `FINISH`.
- **`test_scenario_deep_architectural_rule_validation()`**:
  - Prompt: `"Audit the workspace architecture against global steering rules and compile research report."`
  - Verifies: Supervisor -> `research_worker` -> Rule search & evaluation -> Handoff -> Supervisor -> `FINISH`.
- **`test_scenario_multi_step_hybrid_orchestration()`**:
  - Prompt: `"Research the top trending sports cards, generate social assets, and verify on mobile device."`
  - Verifies: Supervisor -> `research_worker` -> Supervisor -> `social_worker` -> Supervisor -> `mobile_worker` -> Supervisor -> `FINISH`.
- **`test_scenario_degraded_worker_loop_exhaustion()`**:
  - Simulates non-converging worker loop; verifies recursion guard cleanly halts at `iteration_count == max_iterations` with `status="TERMINATED_LOOP_LIMIT"`.

### 3.5 Tier 5: Adversarial Hardening & Stress Testing
- **`test_adversarial_llm_api_exception_handling()`**: LLM throws `503 Service Unavailable`; supervisor catches error, records failure in `execution_history`, sets `status="FAILED"`, and returns `Command(goto=END)`.
- **`test_adversarial_corrupted_state_missing_keys()`**: State dictionary with missing keys (no `iteration_count`, no `messages`) is handled gracefully with defaults.
- **`test_adversarial_corrupted_execution_history()`**: State with malformed `execution_history` (strings instead of dicts) does not crash reducers.
- **`test_adversarial_concurrent_thread_isolation()`**: Runs multiple simultaneous graph invocations with different `thread_id` values and verifies zero state cross-talk.
- **`test_adversarial_rapid_state_graph_recompilation()`**: Compiles 50 graphs concurrently to verify memory stability and no thread leaks.

---

## 4. Edge Case Handling & Mitigation Matrix

| Category | Edge Case Condition | Potential Failure Mode | Supervisor Mitigation Strategy | Test Verification Method |
|---|---|---|---|---|
| **Payload Integrity** | LLM outputs unknown destination (e.g. `"hacker_node"`, `""`, `123`) | Routing error or graph routing failure | Destination whitelist check against `{"social_worker", "mobile_worker", "research_worker", "FINISH"}`. Reject invalid with `status="FAILED"`. | `test_invalid_destination_node_rejection` |
| **Payload Integrity** | LLM throws `pydantic.ValidationError` or non-JSON output | Unhandled crash during `with_structured_output` | Wrapped in try-except block; records error to `execution_history` and returns `Command(goto=END, update={"status": "FAILED"})`. | `test_malformed_llm_payload_missing_fields` |
| **Recursion Guard** | Endless worker loop failing to finish | Infinite execution loop / graph hanging | `iteration_count = state.get("iteration_count", 0) + 1`. If `iteration_count > max_iterations`, force `goto=END` with `status="TERMINATED_LOOP_LIMIT"`. | `test_max_iterations_exhaustion_halts_execution` |
| **User Input** | User passes empty string or `messages=[]` | IndexError / KeyError / Prompt assembly failure | Fallback default prompt (`"Evaluate current state and determine next action."`) and graceful routing to `FINISH`. | `test_empty_user_request_and_minimal_state` |
| **State Reducers** | State with `execution_history` list merging | History overwritten or lost | Uses `Annotated[List[Dict[str, Any]], operator.add]` in `AgentState` so every node handoff appends history entries. | `test_supervisor_audit_history_logging` |
| **Checkpointers** | Synchronous vs Asynchronous checkpointer mismatch | `TypeError` or `RuntimeError` during execution | `create_control_plane_graph` accepts any `BaseCheckpointSaver` (sync/async/MemorySaver); graph supports `invoke` and `ainvoke`. | `test_sync_checkpointer_memory_saver_persistence`, `test_async_checkpointer_ainvoke_persistence` |
| **Worker Isolation** | Worker attempting to transition to peer worker directly | State divergence / bypassed audit logs | Workers strictly configure `goto="supervisor"`; StateGraph registers no inter-worker edges. | `test_hub_and_spoke_worker_isolation` |

---

## 5. Verification Commands

To verify the test suite once implemented:
1. Run all unit tests: `python -m pytest tests/test_supervisor.py -v`
2. Run full test suite: `python -m pytest tests/`
3. Assert 100% test pass rate with execution time under 5.0 seconds.
