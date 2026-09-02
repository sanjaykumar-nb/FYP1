"""AI service services package.

Deliberately no eager re-exports here: app.services.agent_runner imports
app.agents.coordinator, which imports app.services.graph_pipeline — an eager
`from app.services.agent_runner import ...` at package-init time would make
that a circular import. Import submodules directly:
`from app.services.agent_runner import run_full_analysis`.
"""
