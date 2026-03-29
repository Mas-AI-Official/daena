"""Tests for Conversation Phase Detector -- per-turn tool optimization.

Simulates real Daena build sessions to prove token savings.
The key test: simulate the Build 1->2->3->4->Ship conversation
and verify tools switch intelligently per phase.
"""

from __future__ import annotations

import pytest

from app.services.tool_lifecycle.phase_detector import (
    AdaptiveToolSelector,
    ConversationPhaseDetector,
    PhaseDetection,
)


@pytest.fixture
def detector() -> ConversationPhaseDetector:
    return ConversationPhaseDetector()


@pytest.fixture
def selector() -> AdaptiveToolSelector:
    return AdaptiveToolSelector()


# ── Phase Detection Tests ─────────────────────────────────────

class TestPhaseDetection:
    def test_frontend_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Fix the React component styling with Tailwind CSS")
        assert d.phase == "frontend"
        assert "terminal" in d.recommended_tools
        assert "browser" in d.recommended_tools

    def test_backend_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Create a new FastAPI endpoint for the Python service")
        assert d.phase == "backend"
        assert "terminal" in d.recommended_tools
        assert "browser" not in d.recommended_tools

    def test_testing_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Run pytest and verify all 1347 tests pass")
        assert d.phase == "testing"
        assert "terminal" in d.recommended_tools

    def test_deploy_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Build the Docker container and deploy to GCP Cloud Run")
        assert d.phase == "deploy"
        assert "terminal" in d.recommended_tools

    def test_research_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Research the competitive landscape for AI platforms")
        assert d.phase == "research"
        assert "web_search" in d.recommended_tools

    def test_conversation_no_tools(self, detector: ConversationPhaseDetector):
        d = detector.detect("Hi, how are you?")
        assert d.phase == "conversation"
        assert d.recommended_tools == []

    def test_git_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Commit these changes and create a pull request on GitHub")
        assert d.phase == "git"
        assert "terminal" in d.recommended_tools
        assert "github" in d.recommended_tools

    def test_writing_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Write a marketing email for the product launch")
        assert d.phase == "writing"
        assert "email" in d.recommended_tools

    def test_data_detected(self, detector: ConversationPhaseDetector):
        d = detector.detect("Analyze the billing data and create a cost report in Excel")
        assert d.phase == "data"
        assert "spreadsheet" in d.recommended_tools


# ── Deactivation Tests ────────────────────────────────────────

class TestDeactivation:
    def test_switching_from_frontend_to_testing_deactivates_browser(self, detector):
        # Phase 1: frontend (browser active)
        d1 = detector.detect("Fix the React CSS layout")
        assert "browser" in d1.recommended_tools

        # Phase 2: testing (browser not needed)
        d2 = detector.detect("Run pytest to check all tests", active_tools=["terminal", "browser", "file_system"])
        assert "browser" in d2.deactivate_tools

    def test_switching_from_coding_to_deploy_deactivates_browser(self, detector):
        d1 = detector.detect("Debug this React component")
        d2 = detector.detect("Deploy to Docker and Cloud Run", active_tools=["terminal", "browser", "file_system"])
        assert "browser" in d2.deactivate_tools

    def test_no_deactivation_when_tools_still_needed(self, detector):
        d = detector.detect("Run the test suite", active_tools=["terminal", "file_system"])
        # testing needs terminal and file_system, so nothing to deactivate
        assert "terminal" not in d.deactivate_tools
        assert "file_system" not in d.deactivate_tools


# ── Phase History Tests ───────────────────────────────────────

class TestPhaseHistory:
    def test_history_tracks_transitions(self, detector):
        detector.detect("Build the React component")
        detector.detect("Write the Python backend")
        detector.detect("Run all tests")
        history = detector.get_phase_history()
        assert history == ["frontend", "backend", "testing"]

    def test_no_duplicate_consecutive_phases(self, detector):
        detector.detect("Fix React styling")
        detector.detect("Update the React component")  # same phase
        history = detector.get_phase_history()
        assert history == ["frontend"]  # not ["frontend", "frontend"]

    def test_reset_clears_history(self, detector):
        detector.detect("Fix React component")
        detector.reset()
        assert detector.get_phase_history() == []


# ── THE REAL TEST: Simulate Daena Build Session ───────────────

class TestDaenaBuildSimulation:
    """Simulate the ACTUAL Daena build conversation (Build 1->2->3->4->Ship)
    and verify tools switch intelligently per phase, with token savings."""

    def test_full_build_session_simulation(self, selector: AdaptiveToolSelector):
        """Walk through the real Daena build session phases."""

        # ── Build 1: TLM (Backend Python) ──
        d = selector.select_tools_for_turn(
            "Create the Tool Lifecycle Manager with 6 Python modules in backend/app/services/tool_lifecycle/"
        )
        assert d.phase == "backend"
        assert "terminal" in d.recommended_tools
        assert "browser" not in d.recommended_tools  # no browser needed for Python

        d = selector.select_tools_for_turn(
            "Write pytest tests for ToolRegistry, SessionManager, ActivationProxy"
        )
        assert d.phase == "testing"

        d = selector.select_tools_for_turn(
            "Run the full test suite: python -m pytest backend/tests/"
        )
        assert d.phase == "testing"

        # ── Build 2: Execution Layer Tests ──
        d = selector.select_tools_for_turn(
            "Create execution layer smoke tests with mock LLM stream"
        )
        assert d.phase == "testing"

        d = selector.select_tools_for_turn(
            "Test the FastAPI endpoints for security gate and governance"
        )
        assert d.phase in ("backend", "testing")

        # ── Build 3: Mobile + Remote ──
        d = selector.select_tools_for_turn(
            "Build the FastAPI mobile API endpoints for phone control"
        )
        assert d.phase == "backend"

        d = selector.select_tools_for_turn(
            "Write the stay-awake Python service and PowerShell script"
        )
        assert d.phase in ("backend", "deploy") or "terminal" in d.recommended_tools

        # ── Build 4: Ship ──
        d = selector.select_tools_for_turn(
            "Version bump to v3.6.0, update CHANGELOG.md, tag and commit"
        )
        assert d.phase in ("deploy", "git")

        d = selector.select_tools_for_turn(
            "Build Docker container and deploy to GCP Cloud Run"
        )
        assert d.phase == "deploy"

        # ── Wrap up: simple chat ──
        d = selector.select_tools_for_turn("Thanks, that looks great!")
        assert d.recommended_tools == [] or len(d.recommended_tools) <= 2

        # ── Verify efficiency ──
        report = selector.get_efficiency_report()
        assert report["turns"] == 10
        assert report["avg_tools_per_turn"] < 4  # much less than 20 baseline
        assert report["token_reduction_percent"] > 70  # >70% token savings
        assert len(report["phase_transitions"]) >= 3  # multiple phase changes

    def test_mixed_frontend_backend_session(self, selector: AdaptiveToolSelector):
        """User alternates between frontend and backend in one session."""

        selector.select_tools_for_turn("Fix the React ConnectionsPage component")
        selector.select_tools_for_turn("Now fix the Python chat_orchestrator.py backend")
        selector.select_tools_for_turn("Check the TypeScript build: npx tsc --noEmit")
        selector.select_tools_for_turn("Run pytest backend/tests/ to verify")
        selector.select_tools_for_turn("Update the frontend Settings page ordering")

        report = selector.get_efficiency_report()
        assert report["turns"] == 5
        # Phase transitions: frontend -> backend -> frontend/testing -> testing -> frontend
        assert len(report["phase_transitions"]) >= 3
        assert report["token_reduction_percent"] > 60

    def test_research_to_code_to_deploy_pipeline(self, selector: AdaptiveToolSelector):
        """Real workflow: research -> implement -> test -> deploy."""

        selector.select_tools_for_turn("Research how Cloudflare Tunnels work for remote access")
        selector.select_tools_for_turn("Write the RemoteGateway Python service")
        selector.select_tools_for_turn("Write tests for the gateway command queue")
        selector.select_tools_for_turn("Run pytest and check all pass")
        selector.select_tools_for_turn("Commit and tag v3.6.0")
        selector.select_tools_for_turn("Deploy to GCP Cloud Run")

        report = selector.get_efficiency_report()
        transitions = report["phase_transitions"]
        assert transitions[0] == "research"
        assert "testing" in transitions
        assert report["token_reduction_percent"] > 65


# ── Efficiency Metrics Tests ──────────────────────────────────

class TestEfficiencyMetrics:
    def test_zero_turns_report(self, selector: AdaptiveToolSelector):
        report = selector.get_efficiency_report()
        assert report["turns"] == 0
        assert report["token_reduction_percent"] == 0

    def test_pure_conversation_maximal_savings(self, selector: AdaptiveToolSelector):
        """10 turns of pure chat = no tools loaded = 100% savings."""
        messages = [
            "Hello!", "How are you?", "Tell me about Daena",
            "What is governance?", "Explain NBMF",
            "Thanks!", "Got it", "That makes sense",
            "Can you explain more?", "Perfect",
        ]
        for msg in messages:
            selector.select_tools_for_turn(msg)

        report = selector.get_efficiency_report()
        assert report["avg_tools_per_turn"] == 0
        assert report["token_reduction_percent"] == 100.0

    def test_all_coding_moderate_savings(self, selector: AdaptiveToolSelector):
        """10 turns of backend coding = 2 tools per turn vs 20 baseline."""
        messages = [
            "Write a Python class for UserService",
            "Add a FastAPI endpoint for /users",
            "Create the Pydantic schema for UserCreate",
            "Implement the database query with SQLAlchemy",
            "Add error handling for duplicate emails",
        ]
        for msg in messages:
            selector.select_tools_for_turn(msg)

        report = selector.get_efficiency_report()
        assert report["avg_tools_per_turn"] <= 3
        assert report["token_reduction_percent"] > 80

    def test_reset_clears_metrics(self, selector: AdaptiveToolSelector):
        selector.select_tools_for_turn("Write Python code")
        selector.reset()
        report = selector.get_efficiency_report()
        assert report["turns"] == 0


# ── Token Savings Math Tests ──────────────────────────────────

class TestTokenSavingsMath:
    def test_savings_math_correct(self, selector: AdaptiveToolSelector):
        """Verify the token savings math is internally consistent."""
        for msg in ["Hello", "Write Python code", "Run pytest"]:
            selector.select_tools_for_turn(msg)

        report = selector.get_efficiency_report()
        expected_savings = report["baseline_tokens"] - report["total_tokens_loaded"]
        assert report["tokens_saved"] == expected_savings

    def test_100_turn_session_savings(self, selector: AdaptiveToolSelector):
        """100-turn mixed session should save >200K tokens vs baseline."""
        messages = (
            ["Write Python code"] * 30
            + ["Run pytest"] * 20
            + ["Hello, thanks"] * 20
            + ["Fix React component"] * 15
            + ["Deploy to Docker"] * 10
            + ["Research AI trends"] * 5
        )
        for msg in messages:
            selector.select_tools_for_turn(msg)

        report = selector.get_efficiency_report()
        assert report["turns"] == 100
        # Baseline: 100 * 20 * 210 = 420,000 tokens
        assert report["baseline_tokens"] == 420_000
        # With adaptive: should save at least 300K
        assert report["tokens_saved"] > 300_000
        assert report["token_reduction_percent"] > 70
