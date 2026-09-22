import pytest
from uuid import uuid4
from app.models.agent_base import (
    PlanningInput, ProgressInput, MeetingIntelInput,
    CommIntelInput, WorkloadIntelInput, RiskInput, RecommendationInput,
    AgentSignal, AgentEvidence, AgentRecommendation, AgentOutput,
)
from app.llm.fallback import RuleBasedFallback


@pytest.fixture
def fallback():
    return RuleBasedFallback()


@pytest.mark.mvp
class TestPlanningFallback:
    def test_planning_with_milestones_and_tasks(self, fallback):
        input_data = PlanningInput(
            project_id=uuid4(),
            milestones=[
                {"id": "m1", "name": "Sprint 1", "target_date": "2024-02-01"},
                {"id": "m2", "name": "Sprint 2", "target_date": "2024-03-01"},
            ],
            tasks=[
                {"id": "t1", "milestone_id": "m1", "story_points": 5, "status": "backlog"},
                {"id": "t2", "milestone_id": "m1", "story_points": 3, "status": "backlog"},
                {"id": "t3", "milestone_id": "m2", "story_points": 8, "status": "backlog"},
            ],
            team_capacity={"total_points": 20},
        )
        result = fallback.planning_analysis(input_data)

        assert isinstance(result.summary, str)
        assert result.risk_level in ["low", "medium", "high", "critical"]
        assert 0 <= result.confidence <= 1
        assert result.sprint_readiness == 1.0  # All milestones have tasks
        assert len(result.capacity_gaps) == 0  # 16 points <= 20 capacity

    def test_planning_capacity_gap(self, fallback):
        input_data = PlanningInput(
            project_id=uuid4(),
            milestones=[{"id": "m1", "name": "Sprint 1"}],
            tasks=[{"id": "t1", "milestone_id": "m1", "story_points": 30, "status": "backlog"}],
            team_capacity={"total_points": 20},
        )
        result = fallback.planning_analysis(input_data)

        assert result.risk_level == "high"  # 30 points is 1.5x the capacity of 20
        assert len(result.capacity_gaps) == 1
        assert "Gap of 10 points" in result.capacity_gaps[0]
        # The warning cites the sprint it is about, as a knowledge-graph node.
        assert [e.reference_id for e in result.evidence] == ["milestone:m1"]
        assert result.recommendations[0].type == "replan_sprint"

    def test_planning_slightly_over_capacity_is_medium(self, fallback):
        input_data = PlanningInput(
            project_id=uuid4(),
            milestones=[{"id": "m1", "name": "Sprint 1"}],
            tasks=[{"id": "t1", "milestone_id": "m1", "story_points": 24, "status": "backlog"}],
            team_capacity={"total_points": 20, "source": "average completed in the last 3 sprints"},
        )
        result = fallback.planning_analysis(input_data)

        assert result.risk_level == "medium"
        assert "Capacity: 20 points per sprint (average completed in the last 3 sprints)" in result.summary
        assert "Largest plan: 24 points, over capacity." in result.summary

    def test_planning_without_capacity_makes_no_warning(self, fallback):
        # No capacity set and no finished sprint: nothing to compare the plan against.
        input_data = PlanningInput(
            project_id=uuid4(),
            milestones=[{"id": "m1", "name": "Sprint 1"}],
            tasks=[{"id": "t1", "milestone_id": "m1", "story_points": 300, "status": "backlog"}],
            team_capacity={},
        )
        result = fallback.planning_analysis(input_data)

        assert result.risk_level == "low"
        assert result.capacity_gaps == []
        assert "Capacity unknown" in result.summary

    def test_planning_ignores_finished_sprints(self, fallback):
        # A sprint that has ended is history; only the one still running is judged.
        input_data = PlanningInput(
            project_id=uuid4(),
            milestones=[
                {"id": "old", "name": "Sprint 1", "target_date": "2024-02-01"},
                {"id": "done", "name": "Sprint 2", "status": "completed"},
                {"id": "now", "name": "Sprint 3"},
            ],
            tasks=[
                {"id": "t1", "milestone_id": "old", "story_points": 50, "status": "done"},
                {"id": "t2", "milestone_id": "done", "story_points": 50, "status": "done"},
                {"id": "t3", "milestone_id": "now", "story_points": 15, "status": "planned"},
            ],
            team_capacity={"total_points": 20},
        )
        result = fallback.planning_analysis(input_data)

        assert result.risk_level == "low"
        assert result.milestone_feasibility["now"] == {"feasible": True, "planned_points": 15, "capacity_points": 20}

    def test_planning_no_milestones(self, fallback):
        input_data = PlanningInput(
            project_id=uuid4(),
            milestones=[],
            tasks=[{"id": "t1", "story_points": 5}],
            team_capacity={},
        )
        result = fallback.planning_analysis(input_data)

        assert result.sprint_readiness == 0.5

    def test_planning_tolerates_unestimated_tasks(self, fallback):
        # Real trackers are full of issues with no estimate; they must not crash the agent.
        input_data = PlanningInput(
            project_id=uuid4(),
            milestones=[{"id": "m1", "name": "Sprint 1"}],
            tasks=[
                {"id": "t1", "milestone_id": "m1", "story_points": None, "status": "backlog"},
                {"id": "t2", "milestone_id": "m1", "story_points": 30, "status": "backlog"},
            ],
            team_capacity={"total_points": 20},
        )
        result = fallback.planning_analysis(input_data)

        assert "Gap of 10 points" in result.capacity_gaps[0]


@pytest.mark.mvp
class TestProgressFallback:
    def test_progress_with_completed_tasks(self, fallback):
        input_data = ProgressInput(
            project_id=uuid4(),
            tasks=[
                {"id": "t1", "status": "done", "story_points": 5},
                {"id": "t2", "status": "done", "story_points": 3},
                {"id": "t3", "status": "in_progress", "story_points": 8},
                {"id": "t4", "status": "blocked", "story_points": 2},
            ],
            velocity_history=[10, 12, 11],
        )
        result = fallback.progress_analysis(input_data)

        assert result.completion_rate == 0.5
        assert result.velocity_trend == "stable"
        assert len(result.stalled_work) == 1
        assert result.risk_level == "medium"

    def test_progress_improving_velocity(self, fallback):
        input_data = ProgressInput(
            project_id=uuid4(),
            tasks=[{"id": "t1", "status": "done"}],
            velocity_history=[5, 8, 12, 15],
        )
        result = fallback.progress_analysis(input_data)
        assert result.velocity_trend == "improving"

    def test_progress_declining_velocity(self, fallback):
        input_data = ProgressInput(
            project_id=uuid4(),
            tasks=[{"id": "t1", "status": "done"}],
            velocity_history=[20, 15, 10, 5],
        )
        result = fallback.progress_analysis(input_data)
        assert result.velocity_trend == "declining"


@pytest.mark.deferred  # Meeting Intelligence: no transcript source in-product yet
class TestMeetingIntelFallback:
    def test_meeting_with_action_items(self, fallback):
        input_data = MeetingIntelInput(
            meeting_id=uuid4(),
            transcript="We need to action this item. John will follow up on the API. Deadline is Friday.",
            participants=[{"id": "u1", "name": "John"}, {"id": "u2", "name": "Jane"}],
        )
        result = fallback.meeting_intel_analysis(input_data)

        assert len(result.action_items) > 0
        assert len(result.decisions) >= 0
        assert result.risk_level in ["low", "medium"]

    def test_meeting_with_blockers(self, fallback):
        input_data = MeetingIntelInput(
            meeting_id=uuid4(),
            transcript="We are blocked on the database migration. This is a blocker for the team.",
            participants=[],
        )
        result = fallback.meeting_intel_analysis(input_data)

        assert len(result.blockers) > 0
        assert result.risk_level == "medium"


@pytest.mark.deferred  # Communication Intelligence: no comm-event source in-product yet
class TestCommIntelFallback:
    def test_comm_with_unanswered_questions(self, fallback):
        input_data = CommIntelInput(
            project_id=uuid4(),
            events=[
                {"user_id": "u1", "is_question": True, "response_time_seconds": None},
                {"user_id": "u2", "is_question": True, "response_time_seconds": 7200},
                {"user_id": "u1", "is_question": False},
            ],
            timeframe_days=14,
        )
        result = fallback.comm_intel_analysis(input_data)

        assert result.unanswered_questions[0]["count"] >= 1
        assert result.risk_level == "high"

    def test_comm_slow_response(self, fallback):
        input_data = CommIntelInput(
            project_id=uuid4(),
            events=[
                {"user_id": "u1", "response_time_seconds": 10000},
                {"user_id": "u2", "response_time_seconds": 15000},
            ],
            timeframe_days=14,
        )
        result = fallback.comm_intel_analysis(input_data)

        assert result.risk_level == "high"
        assert result.response_delays[0]["avg_hours"] > 2


@pytest.mark.mvp
class TestWorkloadFallback:
    def test_workload_overloaded_member(self, fallback):
        input_data = WorkloadIntelInput(
            project_id=uuid4(),
            assignments=[
                {"assignee_id": "u1", "story_points": 20},
                {"assignee_id": "u1", "story_points": 15},
                {"assignee_id": "u2", "story_points": 5},
            ],
            story_points={},
        )
        result = fallback.workload_intel_analysis(input_data)

        assert len(result.overloaded_members) == 1
        assert result.overloaded_members[0]["user_id"] == "u1"
        assert result.risk_level == "high"

    def test_workload_balanced(self, fallback):
        input_data = WorkloadIntelInput(
            project_id=uuid4(),
            assignments=[
                {"assignee_id": "u1", "story_points": 10},
                {"assignee_id": "u2", "story_points": 10},
                {"assignee_id": "u3", "story_points": 10},
            ],
            story_points={},
        )
        result = fallback.workload_intel_analysis(input_data)

        assert len(result.overloaded_members) == 0
        assert len(result.underutilized_members) == 0
        assert result.risk_level == "low"

    def test_workload_tolerates_unestimated_assignments(self, fallback):
        input_data = WorkloadIntelInput(
            project_id=uuid4(),
            assignments=[
                {"assignee_id": "u1", "story_points": None},
                {"assignee_id": "u1", "story_points": 20},
                {"assignee_id": "u2", "story_points": 5},
            ],
            story_points={},
        )
        result = fallback.workload_intel_analysis(input_data)

        assert result.overloaded_members[0]["user_id"] == "u1"


@pytest.mark.mvp
class TestRiskFallback:
    def test_risk_aggregation(self, fallback):
        input_data = RiskInput(
            project_id=uuid4(),
            specialist_outputs={
                "planning": {"risk_level": "medium"},
                "progress": {"risk_level": "high"},
                "workload": {"risk_level": "low"},
            },
        )
        result = fallback.risk_prediction(input_data)

        assert result.risk_level == "high"
        assert "delay" in result.risk_scores
        assert "workload" in result.risk_scores


@pytest.mark.mvp
class TestRecommendationFallback:
    def test_recommendations_from_high_risks(self, fallback):
        input_data = RecommendationInput(
            project_id=uuid4(),
            risk_scores={"delay": "high", "workload": "critical", "coordination": "low"},
            specialist_outputs={},
        )
        result = fallback.recommendation_generation(input_data)

        assert len(result.recommendations) >= 2
        rec_types = [r.type for r in result.recommendations]
        assert "split_task" in rec_types or "redistribute" in rec_types