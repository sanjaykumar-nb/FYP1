from typing import Optional
from ai_service.app.models.agent_base import (
    PlanningInput, PlanningOutput,
    ProgressInput, ProgressOutput,
    MeetingIntelInput, MeetingIntelOutput,
    CommIntelInput, CommIntelOutput,
    WorkloadIntelInput, WorkloadIntelOutput,
    RiskInput, RiskOutput,
    RecommendationInput, RecommendationOutput,
    AgentOutput, AgentSignal, AgentEvidence, AgentRecommendation,
)
from uuid import uuid4


class RuleBasedFallback:
    """Deterministic rule-based fallback when LLM is unavailable"""
    
    def _create_base_output(self, summary: str, risk_level: str = "low") -> AgentOutput:
        return AgentOutput(
            summary=summary,
            risk_level=risk_level,
            confidence=0.6,
            signals=[],
            evidence=[],
            recommendations=[],
            next_action="Review manually",
            metadata={"fallback": True}
        )
    
    def planning_analysis(self, input_data: PlanningInput) -> PlanningOutput:
        milestones = input_data.milestones or []
        tasks = input_data.tasks or []
        team_capacity = input_data.team_capacity or {}
        
        # Simple heuristic: check if milestones have tasks assigned
        milestones_with_tasks = sum(1 for m in milestones if any(t.get('milestone_id') == m.get('id') for t in tasks))
        sprint_readiness = milestones_with_tasks / max(len(milestones), 1) if milestones else 0.5
        
        # Check capacity
        total_points = sum(t.get('story_points', 0) for t in tasks)
        capacity = team_capacity.get('total_points', total_points * 1.2)
        capacity_gap = max(0, total_points - capacity)
        
        return PlanningOutput(
            summary=f"Planning analysis: {len(milestones)} milestones, {len(tasks)} tasks. Sprint readiness: {sprint_readiness:.0%}",
            risk_level="medium" if capacity_gap > 0 else "low",
            confidence=0.6,
            signals=[
                AgentSignal(name="milestone_coverage", value=sprint_readiness, weight=0.5),
                AgentSignal(name="capacity_utilization", value=min(total_points/capacity, 1.0) if capacity > 0 else 0.5, weight=0.5),
            ],
            evidence=[],
            recommendations=[
                AgentRecommendation(
                    type="replan_sprint",
                    title="Adjust sprint scope",
                    description=f"Capacity gap of {capacity_gap} points detected",
                    reasoning="Team capacity insufficient for planned work",
                    priority="high" if capacity_gap > 0 else "low",
                    confidence=0.7,
                )
            ] if capacity_gap > 0 else [],
            next_action="Review sprint planning with team",
            sprint_readiness=sprint_readiness,
            milestone_feasibility={m.get('id', 'unknown'): {'feasible': True} for m in milestones},
            capacity_gaps=[f"Gap of {capacity_gap} points"] if capacity_gap > 0 else [],
        )
    
    def progress_analysis(self, input_data: ProgressInput) -> ProgressOutput:
        tasks = input_data.tasks or []
        velocity_history = input_data.velocity_history or []
        
        done_tasks = [t for t in tasks if t.get('status') == 'done']
        in_progress_tasks = [t for t in tasks if t.get('status') == 'in_progress']
        blocked_tasks = [t for t in tasks if t.get('status') == 'blocked']
        
        completion_rate = len(done_tasks) / max(len(tasks), 1)
        
        # Velocity trend
        if len(velocity_history) >= 2:
            recent_avg = sum(velocity_history[-2:]) / 2
            older_avg = sum(velocity_history[:-2]) / max(len(velocity_history) - 2, 1) if len(velocity_history) > 2 else recent_avg
            if recent_avg > older_avg * 1.1:
                trend = "improving"
            elif recent_avg < older_avg * 0.9:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return ProgressOutput(
            summary=f"Progress: {len(done_tasks)}/{len(tasks)} tasks done ({completion_rate:.0%}). Velocity {trend}.",
            risk_level="high" if completion_rate < 0.3 and len(in_progress_tasks) == 0 else "medium" if completion_rate < 0.5 else "low",
            confidence=0.6,
            signals=[
                AgentSignal(name="completion_rate", value=completion_rate, weight=0.6),
                AgentSignal(name="blocked_ratio", value=len(blocked_tasks)/max(len(tasks), 1), weight=0.4),
            ],
            evidence=[],
            recommendations=[
                AgentRecommendation(
                    type="unblock_work",
                    title="Address blocked tasks",
                    description=f"{len(blocked_tasks)} tasks are blocked",
                    reasoning="Blocked tasks prevent progress",
                    priority="high",
                    confidence=0.8,
                )
            ] if blocked_tasks else [],
            next_action="Review blocked tasks in standup",
            velocity_trend=trend,
            completion_forecast=f"Estimated completion: {100*completion_rate:.0f}% at current pace",
            stalled_work=[{"task_id": t.get('id'), "reason": "blocked"} for t in blocked_tasks],
        )
    
    def meeting_intel_analysis(self, input_data: MeetingIntelInput) -> MeetingIntelOutput:
        transcript = input_data.transcript or ""
        participants = input_data.participants or []
        
        # Simple keyword extraction
        action_keywords = ["action", "todo", "follow up", "assign", "owner", "deadline", "due"]
        decision_keywords = ["decide", "decision", "agree", "approved", "reject", "choose"]
        blocker_keywords = ["block", "blocked", "blocker", "impediment", "stuck", "waiting"]
        
        transcript_lower = transcript.lower()
        
        action_items = []
        for kw in action_keywords:
            if kw in transcript_lower:
                action_items.append({"keyword": kw, "context": "found in transcript"})
        
        decisions = []
        for kw in decision_keywords:
            if kw in transcript_lower:
                decisions.append({"keyword": kw, "context": "found in transcript"})
        
        blockers = []
        for kw in blocker_keywords:
            if kw in transcript_lower:
                blockers.append({"keyword": kw, "context": "found in transcript"})
        
        return MeetingIntelOutput(
            summary=f"Meeting analysis: {len(action_items)} potential actions, {len(decisions)} decisions, {len(blockers)} blockers mentioned.",
            risk_level="medium" if blockers else "low",
            confidence=0.5,
            signals=[
                AgentSignal(name="action_item_count", value=len(action_items), weight=0.4),
                AgentSignal(name="blocker_count", value=len(blockers), weight=0.6),
            ],
            evidence=[],
            recommendations=[
                AgentRecommendation(
                    type="create_tasks",
                    title="Convert action items to tasks",
                    description=f"Found {len(action_items)} potential action items",
                    reasoning="Action items need tracking",
                    priority="medium",
                    confidence=0.6,
                )
            ] if action_items else [],
            next_action="Review extracted items with team",
            decisions=decisions,
            action_items=action_items,
            blockers=blockers,
            owners=[],
            deadlines=[],
            unresolved_issues=[],
        )
    
    def comm_intel_analysis(self, input_data: CommIntelInput) -> CommIntelOutput:
        events = input_data.events or []
        
        # Analyze response times
        response_times = [e.get('response_time_seconds', 0) for e in events if e.get('response_time_seconds')]
        avg_response = sum(response_times) / max(len(response_times), 1)
        
        # Find unanswered questions
        questions = [e for e in events if e.get('is_question')]
        unanswered = [q for q in questions if q.get('response_time_seconds') is None or q.get('response_time_seconds', 0) > 3600]
        
        # Participation
        participants = set(e.get('user_id') for e in events if e.get('user_id'))
        participation_rate = len(participants) / max(10, 1)  # Assume team of 10
        
        return CommIntelOutput(
            summary=f"Communication analysis: {len(events)} events, avg response {avg_response/60:.0f}min, {len(unanswered)} unanswered questions.",
            risk_level="high" if len(unanswered) > 3 else "medium" if avg_response > 7200 else "low",
            confidence=0.5,
            signals=[
                AgentSignal(name="avg_response_hours", value=avg_response/3600, weight=0.5),
                AgentSignal(name="unanswered_questions", value=len(unanswered), weight=0.5),
            ],
            evidence=[],
            recommendations=[
                AgentRecommendation(
                    type="follow_up",
                    title="Follow up on unanswered questions",
                    description=f"{len(unanswered)} questions need responses",
                    reasoning="Unanswered questions block progress",
                    priority="high",
                    confidence=0.7,
                )
            ] if unanswered else [],
            next_action="Check in with team on communication",
            response_delays=[{"avg_hours": avg_response/3600}],
            unanswered_questions=[{"count": len(unanswered)}],
            participation_gaps=[{"rate": participation_rate}],
            friction_points=[],
        )
    
    def workload_intel_analysis(self, input_data: WorkloadIntelInput) -> WorkloadIntelOutput:
        assignments = input_data.assignments or []
        
        # Calculate load per person
        user_loads = {}
        for a in assignments:
            user_id = a.get('assignee_id')
            points = a.get('story_points', 0)
            if user_id:
                user_loads[user_id] = user_loads.get(user_id, 0) + points
        
        if not user_loads:
            return WorkloadIntelOutput(
                summary="No assignments to analyze",
                risk_level="low",
                confidence=0.5,
                signals=[],
                evidence=[],
                recommendations=[],
                next_action="Assign tasks to team",
                overloaded_members=[],
                underutilized_members=[],
                dependency_concentration=[],
                single_points_of_failure=[],
            )
        
        avg_load = sum(user_loads.values()) / len(user_loads)
        overloaded = [{"user_id": u, "load": l} for u, l in user_loads.items() if l > avg_load * 1.5]
        underutilized = [{"user_id": u, "load": l} for u, l in user_loads.items() if l < avg_load * 0.5]
        
        return WorkloadIntelOutput(
            summary=f"Workload: {len(user_loads)} members, avg {avg_load:.0f} pts. {len(overloaded)} overloaded, {len(underutilized)} underutilized.",
            risk_level="high" if overloaded else "medium" if underutilized else "low",
            confidence=0.6,
            signals=[
                AgentSignal(name="load_variance", value=len(overloaded) + len(underutilized), weight=0.7),
            ],
            evidence=[],
            recommendations=[
                AgentRecommendation(
                    type="redistribute_workload",
                    title="Redistribute workload",
                    description=f"{len(overloaded)} members overloaded",
                    reasoning="Uneven workload causes burnout and delays",
                    priority="high",
                    confidence=0.7,
                )
            ] if overloaded else [],
            next_action="Rebalance task assignments",
            overloaded_members=overloaded,
            underutilized_members=underutilized,
            dependency_concentration=[],
            single_points_of_failure=[],
        )
    
    def risk_prediction(self, input_data: RiskInput) -> RiskOutput:
        specialist_outputs = input_data.specialist_outputs or {}
        
        # Aggregate risk from specialist outputs
        risk_scores = {}
        for name, output in specialist_outputs.items():
            if hasattr(output, 'risk_level'):
                risk_scores[name] = output.risk_level
        
        # Default risk levels
        default_risks = {
            "delay": "medium",
            "coordination": "low",
            "workload": "low",
            "dependency": "low",
            "knowledge": "low",
            "silent_member": "low",
        }
        
        # Override with specialist data
        for risk_type, level in default_risks.items():
            if risk_type in specialist_outputs:
                default_risks[risk_type] = specialist_outputs[risk_type].get('risk_level', level)
        
        return RiskOutput(
            summary=f"Risk assessment: {default_risks}",
            risk_level=max(default_risks.values(), key=lambda x: {"critical":4,"high":3,"medium":2,"low":1}.get(x,0)),
            confidence=0.5,
            signals=[
                AgentSignal(name=k, value={"critical":4,"high":3,"medium":2,"low":1}.get(v,1), weight=1.0/len(default_risks))
                for k, v in default_risks.items()
            ],
            evidence=[],
            recommendations=[],
            next_action="Review risk mitigation strategies",
            risk_scores=default_risks,
        )
    
    def recommendation_generation(self, input_data: RecommendationInput) -> RecommendationOutput:
        risk_scores = input_data.risk_scores or {}
        specialist_outputs = input_data.specialist_outputs or {}
        
        recommendations = []
        
        # Generate recommendations based on risk levels
        for risk_type, level in risk_scores.items():
            if level in ["high", "critical"]:
                if risk_type == "delay":
                    recommendations.append(AgentRecommendation(
                        type="split_task",
                        title="Split large tasks",
                        description="Break down large tasks to reduce delay risk",
                        reasoning="Large tasks have higher uncertainty and delay risk",
                        priority="high",
                        confidence=0.7,
                    ))
                elif risk_type == "workload":
                    recommendations.append(AgentRecommendation(
                        type="redistribute",
                        title="Redistribute workload",
                        description="Move tasks from overloaded to underutilized members",
                        reasoning="Uneven workload increases delay and burnout risk",
                        priority="high",
                        confidence=0.8,
                    ))
                elif risk_type == "coordination":
                    recommendations.append(AgentRecommendation(
                        type="schedule_meeting",
                        title="Schedule sync meeting",
                        description="Address coordination gaps with team sync",
                        reasoning="Poor coordination leads to duplicated work and blockers",
                        priority="medium",
                        confidence=0.7,
                    ))
                elif risk_type == "dependency":
                    recommendations.append(AgentRecommendation(
                        type="reassign",
                        title="Reassign blocking tasks",
                        description="Move critical path tasks to available members",
                        reasoning="Dependency concentration creates single points of failure",
                        priority="high",
                        confidence=0.7,
                    ))
        
        return RecommendationOutput(
            summary=f"Generated {len(recommendations)} recommendations based on risk profile",
            risk_level=max(risk_scores.values(), key=lambda x: {"critical":4,"high":3,"medium":2,"low":1}.get(x,0)) if risk_scores else "low",
            confidence=0.6,
            signals=[],
            evidence=[],
            recommendations=recommendations,
            next_action="Review and prioritize recommendations",
            prioritized_actions=recommendations,
        )
    
    def frontend_review(self, input_data: dict) -> AgentOutput:
        return self._create_base_output(
            "Frontend review (fallback): UI/UX considerations noted",
            "low"
        )
    
    def backend_review(self, input_data: dict) -> AgentOutput:
        return self._create_base_output(
            "Backend review (fallback): Scalability and security considered",
            "low"
        )
    
    def ai_ml_review(self, input_data: dict) -> AgentOutput:
        return self._create_base_output(
            "AI/ML review (fallback): Model and data requirements assessed",
            "low"
        )