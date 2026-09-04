"""
E2E Integration Test Entrypoint
Omnichannel Triage Hub

Supports `pytest tests/e2e_integration_test.py` as specified in TEST_INFRA.md and PROJECT.md.
Imports full 4-tier integration test suite from test_e2e_integration.py.
"""

from test_e2e_integration import (
    TestTier1FeatureCoverage,
    TestTier2BoundaryCases,
    TestTier3CrossFeatureCombinations,
    TestTier4RealWorldWorkloads,
    api_client,
)

__all__ = [
    "TestTier1FeatureCoverage",
    "TestTier2BoundaryCases",
    "TestTier3CrossFeatureCombinations",
    "TestTier4RealWorldWorkloads",
    "api_client",
]
