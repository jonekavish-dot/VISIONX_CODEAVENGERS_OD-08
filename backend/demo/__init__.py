"""
IVACS V-TRACE Demo Scenario Engine
Provides deterministic hackathon scenarios for evaluating vehicle visual fingerprinting,
identity consistency, mismatch detection, and plate swapping.
"""

from backend.demo.scenarios import DEMO_SCENARIOS, ScenarioDefinition
from backend.demo.scenario_manager import ScenarioManager

__all__ = ["DEMO_SCENARIOS", "ScenarioDefinition", "ScenarioManager"]
