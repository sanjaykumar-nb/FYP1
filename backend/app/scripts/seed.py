"""Database seed script for demo data"""

import asyncio
from datetime import datetime, date, timedelta
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.config import get_settings
from app.database import Base
from app.models import (
    Organization, User, Role, UserRole, Team, TeamMember,
    Project, ProjectMember, Milestone, Task, TaskDependency,
    Meeting, MeetingParticipant, MeetingActionItem,
    CommunicationEvent, WorkloadSnapshot,
    RiskScore, Recommendation, AgentRun,
    OrganizationMemory, AuditLog, Notification
)

settings = get_settings()
# Use the application's own hashing helper rather than a second, separate
# CryptContext: passlib 1.7.4 cannot drive bcrypt 5.x and fails outright,
# and a seed that hashes differently from the app is a bug waiting to happen.
from app.core.security import get_password_hash

engine = create_async_engine(settings.DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _as_date(v):
    """date | datetime -> date, so the two can be compared safely."""
    return v.date() if isinstance(v, datetime) else v

async def seed_database():
    # The app creates its schema via init_db() on startup (there are no Alembic
    # revisions yet), so seeding a fresh database before the app has ever run
    # would fail on "no such table". Ensure the schema exists first so the seed
    # is self-sufficient and order-independent.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as db:
        print("Seeding database...")
        
        # Create demo organization
        org = Organization(
            name="Demo Company",
            slug="demo-company",
            settings={"theme": "system", "notifications": True}
        )
        db.add(org)
        await db.flush()
        
        # Create default roles
        roles = [
            Role(organization_id=org.id, name="owner", permissions=["*"]),
            Role(organization_id=org.id, name="admin", permissions=[
                "organization:read", "organization:update", "organization:delete",
                "project:create", "project:read", "project:update", "project:delete",
                "task:create", "task:read", "task:update", "task:delete",
                "member:invite", "member:remove", "member:update_role",
                "analytics:read", "settings:read", "settings:update",
            ]),
            Role(organization_id=org.id, name="project_manager", permissions=[
                "project:read", "project:update",
                "task:create", "task:read", "task:update", "task:delete",
                "member:invite", "member:update_role",
                "analytics:read", "meeting:create", "meeting:read", "meeting:update",
            ]),
            Role(organization_id=org.id, name="developer", permissions=[
                "project:read",
                "task:create", "task:read", "task:update",
                "meeting:read",
            ]),
            Role(organization_id=org.id, name="viewer", permissions=[
                "project:read",
                "task:read",
                "meeting:read",
            ]),
        ]
        db.add_all(roles)
        await db.flush()
        
        # Create demo users
        users_data = [
            {"email": "owner@demo.com", "full_name": "Alice Owner", "role": "owner"},
            {"email": "admin@demo.com", "full_name": "Bob Admin", "role": "admin"},
            {"email": "pm@demo.com", "full_name": "Carol PM", "role": "project_manager"},
            {"email": "dev1@demo.com", "full_name": "David Developer", "role": "developer"},
            {"email": "dev2@demo.com", "full_name": "Eve Developer", "role": "developer"},
            {"email": "viewer@demo.com", "full_name": "Frank Viewer", "role": "viewer"},
        ]
        
        users = []
        for u in users_data:
            user = User(
                organization_id=org.id,
                email=u["email"],
                password_hash=get_password_hash("password123"),
                full_name=u["full_name"],
                is_active=True,
            )
            db.add(user)
            users.append(user)
        
        await db.flush()
        
        # Assign roles
        for i, user in enumerate(users):
            role = next(r for r in roles if r.name == users_data[i]["role"])
            user_role = UserRole(
                user_id=user.id,
                role_id=role.id,
                organization_id=org.id,
            )
            db.add(user_role)
        
        # Create team
        team = Team(
            organization_id=org.id,
            name="Engineering Team",
            description="Core engineering team"
        )
        db.add(team)
        await db.flush()
        
        # Add all users to team
        for user in users:
            db.add(TeamMember(team_id=team.id, user_id=user.id))
        
        # Create demo projects
        projects_data = [
            {
                "name": "Website Redesign",
                "key": "WEB",
                "description": "Complete redesign of company website with new branding",
                "team_id": team.id,
                "start_date": date.today() - timedelta(days=30),
                "target_end_date": date.today() + timedelta(days=60),
                "health_score": 0.85,
                "risk_score": 0.15,
            },
            {
                "name": "Mobile App v2.0",
                "key": "MOB",
                "description": "Next version of mobile application with offline support",
                "team_id": team.id,
                "start_date": date.today() - timedelta(days=15),
                "target_end_date": date.today() + timedelta(days=90),
                "health_score": 0.72,
                "risk_score": 0.28,
            },
            {
                "name": "API Platform",
                "key": "API",
                "description": "Internal API platform modernization and documentation",
                "team_id": team.id,
                "start_date": date.today() - timedelta(days=5),
                "target_end_date": date.today() + timedelta(days=120),
                "health_score": 0.55,
                "risk_score": 0.45,
            },
        ]
        
        projects = []
        for p in projects_data:
            project = Project(
                organization_id=org.id,
                **p
            )
            db.add(project)
            projects.append(project)
        
        await db.flush()
        
        # Add project members
        for project in projects:
            # Owner and PM as project managers
            for i, user in enumerate(users[:3]):
                db.add(ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    role="project_manager" if i < 2 else "developer"
                ))
            # Developers
            for user in users[3:5]:
                db.add(ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    role="developer"
                ))
            # Viewer
            db.add(ProjectMember(
                project_id=project.id,
                user_id=users[5].id,
                role="viewer"
            ))
        
        await db.flush()
        
        # Create milestones for each project
        for project in projects:
            milestones = [
                Milestone(
                    project_id=project.id,
                    name="Planning Complete",
                    description="All planning and design finalized",
                    target_date=project.start_date + timedelta(days=14),
                    status="completed",
                    progress=1.0,
                    completed_at=datetime.utcnow() - timedelta(days=10),
                ),
                Milestone(
                    project_id=project.id,
                    name="MVP Development",
                    description="Core features implemented",
                    target_date=project.start_date + timedelta(days=45),
                    status="in_progress",
                    progress=0.6,
                ),
                Milestone(
                    project_id=project.id,
                    name="Testing & QA",
                    description="Testing, bug fixes, and quality assurance",
                    target_date=project.start_date + timedelta(days=75),
                    status="upcoming",
                    progress=0.0,
                ),
                Milestone(
                    project_id=project.id,
                    name="Launch",
                    description="Production deployment and launch",
                    target_date=project.target_end_date,
                    status="upcoming",
                    progress=0.0,
                ),
            ]
            db.add_all(milestones)
        
        await db.flush()
        
        # Create tasks for each project
        for project in projects:
            # Get project members for assignment
            members_result = await db.execute(
                select(ProjectMember.user_id).where(ProjectMember.project_id == project.id)
            )
            member_ids = [m[0] for m in members_result.all()]
            
            # Get milestones
            milestones_result = await db.execute(
                select(Milestone.id).where(Milestone.project_id == project.id)
            )
            milestone_ids = [m[0] for m in milestones_result.all()]
            
            tasks_data = [
                # Milestone 1 tasks (completed)
                {"title": "Requirements gathering", "status": "done", "priority": "high", "story_points": 5, "milestone_idx": 0, "assignee_idx": 0},
                {"title": "Design mockups", "status": "done", "priority": "high", "story_points": 8, "milestone_idx": 0, "assignee_idx": 1},
                {"title": "Technical architecture", "status": "done", "priority": "critical", "story_points": 5, "milestone_idx": 0, "assignee_idx": 0},
                
                # Milestone 2 tasks (in progress)
                {"title": "Frontend implementation", "status": "in_progress", "priority": "high", "story_points": 13, "milestone_idx": 1, "assignee_idx": 3},
                {"title": "Backend API development", "status": "in_progress", "priority": "high", "story_points": 13, "milestone_idx": 1, "assignee_idx": 4},
                {"title": "Database schema", "status": "done", "priority": "high", "story_points": 5, "milestone_idx": 1, "assignee_idx": 0},
                {"title": "Authentication system", "status": "in_progress", "priority": "critical", "story_points": 8, "milestone_idx": 1, "assignee_idx": 1},
                {"title": "Integration tests", "status": "planned", "priority": "medium", "story_points": 5, "milestone_idx": 1, "assignee_idx": 4},
                
                # Milestone 3 tasks (planned)
                {"title": "Unit testing", "status": "planned", "priority": "high", "story_points": 8, "milestone_idx": 2, "assignee_idx": 3},
                {"title": "E2E testing", "status": "planned", "priority": "high", "story_points": 8, "milestone_idx": 2, "assignee_idx": 4},
                {"title": "Performance testing", "status": "planned", "priority": "medium", "story_points": 5, "milestone_idx": 2, "assignee_idx": 0},
                {"title": "Security audit", "status": "planned", "priority": "critical", "story_points": 5, "milestone_idx": 2, "assignee_idx": 1},
                
                # Milestone 4 tasks (planned)
                {"title": "Production deployment", "status": "planned", "priority": "critical", "story_points": 8, "milestone_idx": 3, "assignee_idx": 0},
                {"title": "Monitoring setup", "status": "planned", "priority": "high", "story_points": 5, "milestone_idx": 3, "assignee_idx": 1},
                {"title": "Documentation", "status": "planned", "priority": "medium", "story_points": 3, "milestone_idx": 3, "assignee_idx": 3},
            ]
            
            for i, task_data in enumerate(tasks_data):
                milestone_id = milestone_ids[task_data["milestone_idx"]] if task_data["milestone_idx"] < len(milestone_ids) else None
                assignee_id = member_ids[task_data["assignee_idx"]] if task_data["assignee_idx"] < len(member_ids) else None
                
                task = Task(
                    project_id=project.id,
                    milestone_id=milestone_id,
                    assignee_id=assignee_id,
                    reporter_id=users[0].id,  # Owner as reporter
                    title=task_data["title"],
                    description=f"Task for {project.name}: {task_data['title']}",
                    status=task_data["status"],
                    priority=task_data["priority"],
                    story_points=task_data["story_points"],
                    estimated_hours=task_data["story_points"] * 2,
                    due_date=project.start_date + timedelta(days=14 * (task_data["milestone_idx"] + 1)),
                    position=i,
                )
                if task_data["status"] == "in_progress":
                    task.started_at = datetime.utcnow() - timedelta(days=2)
                elif task_data["status"] == "done":
                    task.started_at = datetime.utcnow() - timedelta(days=5)
                    task.completed_at = datetime.utcnow() - timedelta(days=1)
                    task.actual_hours = task_data["story_points"] * 1.5
                
                db.add(task)
        
        await db.flush()
        
        # Create task dependencies
        for project in projects:
            tasks_result = await db.execute(
                select(Task.id).where(Task.project_id == project.id).order_by(Task.created_at)
            )
            task_ids = [t[0] for t in tasks_result.all()]
            
            # Create some dependencies
            if len(task_ids) >= 4:
                db.add(TaskDependency(
                    project_id=project.id,
                    blocking_task_id=task_ids[0],
                    blocked_task_id=task_ids[3],
                    dependency_type="blocks"
                ))
                db.add(TaskDependency(
                    project_id=project.id,
                    blocking_task_id=task_ids[1],
                    blocked_task_id=task_ids[4],
                    dependency_type="blocks"
                ))
                db.add(TaskDependency(
                    project_id=project.id,
                    blocking_task_id=task_ids[2],
                    blocked_task_id=task_ids[5],
                    dependency_type="blocks"
                ))
        
        # Create sample meetings
        for project in projects:
            meeting = Meeting(
                project_id=project.id,
                organizer_id=users[2].id,  # PM
                title=f"Weekly Sync - {project.name}",
                description=f"Weekly team sync for {project.name}",
                meeting_type="standup",
                started_at=datetime.utcnow() - timedelta(days=2),
                ended_at=datetime.utcnow() - timedelta(days=2, hours=-1),
                transcript="Team discussed progress on current sprint. Frontend implementation is 60% complete. Backend API development has some blockers with authentication. Need to schedule a follow-up for integration testing.",
                summary="Sprint progress review. Frontend at 60%, backend auth blocked. Action items assigned.",
                source="manual",
            )
            db.add(meeting)
            await db.flush()
            
            # Add participants
            members_result = await db.execute(
                select(ProjectMember.user_id).where(ProjectMember.project_id == project.id)
            )
            member_ids = [m[0] for m in members_result.all()]
            
            for member_id in member_ids[:4]:  # First 4 members
                db.add(MeetingParticipant(meeting_id=meeting.id, user_id=member_id))
            
            # Add action items
            action_items = [
                {"description": "Resolve authentication blocker", "assignee_idx": 1, "due_days": 2},
                {"description": "Schedule integration testing session", "assignee_idx": 0, "due_days": 5},
                {"description": "Update API documentation", "assignee_idx": 3, "due_days": 7},
            ]
            
            for ai in action_items:
                assignee_id = member_ids[ai["assignee_idx"]] if ai["assignee_idx"] < len(member_ids) else None
                db.add(MeetingActionItem(
                    meeting_id=meeting.id,
                    assignee_id=assignee_id,
                    description=ai["description"],
                    due_date=datetime.utcnow() + timedelta(days=ai["due_days"]),
                    status="pending",
                    extracted_by_ai=True,
                    confidence=0.85,
                ))
        
        # Create communication events
        for project in projects:
            members_result = await db.execute(
                select(ProjectMember.user_id).where(ProjectMember.project_id == project.id)
            )
            member_ids = [m[0] for m in members_result.all()]
            
            for i, user_id in enumerate(member_ids):
                # Create some communication events
                for j in range(5):
                    db.add(CommunicationEvent(
                        project_id=project.id,
                        user_id=user_id,
                        event_type="message",
                        channel="slack",
                        content=f"Message {j+1} from user {i+1}",
                        response_time_seconds=300 + (j * 600) if j < 4 else None,
                        is_question=j % 3 == 0,
                        is_blocker_mention=j == 2,
                        created_at=datetime.utcnow() - timedelta(days=j, hours=i),
                    ))
        
        # Create workload snapshots
        for project in projects:
            members_result = await db.execute(
                select(ProjectMember.user_id).where(ProjectMember.project_id == project.id)
            )
            member_ids = [m[0] for m in members_result.all()]
            
            for user_id in member_ids:
                tasks_result = await db.execute(
                    select(Task).where(Task.project_id == project.id, Task.assignee_id == user_id)
                )
                user_tasks = tasks_result.scalars().all()
                
                assigned = sum(t.story_points or 0 for t in user_tasks)
                completed = sum(t.story_points or 0 for t in user_tasks if t.status == "done")
                in_progress = sum(t.story_points or 0 for t in user_tasks if t.status == "in_progress")
                blocked = sum(t.story_points or 0 for t in user_tasks if t.status == "blocked")
                
                db.add(WorkloadSnapshot(
                    project_id=project.id,
                    user_id=user_id,
                    snapshot_date=date.today(),
                    assigned_story_points=assigned,
                    completed_story_points=completed,
                    in_progress_story_points=in_progress,
                    blocked_story_points=blocked,
                    active_task_count=len([t for t in user_tasks if t.status in ["in_progress", "planned"]]),
                    # Task.due_date is a DateTime column, but these objects are
                    # still session-resident with whatever Python type was
                    # assigned (a date, above). Normalise both sides so the
                    # comparison holds for either type.
                    overdue_task_count=len([t for t in user_tasks
                                            if t.due_date and _as_date(t.due_date) < date.today()
                                            and t.status != "done"]),
                    utilization_score=min(assigned / 40, 1.0) if assigned > 0 else 0,
                ))
        
        # Create risk scores
        risk_types = ["delay", "coordination", "workload", "dependency", "knowledge", "silent_member"]
        for project in projects:
            for risk_type in risk_types:
                db.add(RiskScore(
                    project_id=project.id,
                    risk_type=risk_type,
                    score=0.2 + (hash(f"{project.id}{risk_type}") % 50) / 100,
                    level="low",
                    factors=["Sample factor 1", "Sample factor 2"],
                    evidence=[{"source": "task", "reference_id": "sample", "excerpt": "Sample evidence", "relevance": 0.8}],
                    trend="stable",
                ))
        
        # Create sample recommendations
        rec_types = ["split_task", "reassign", "schedule_meeting", "transfer_knowledge", "add_docs", "redistribute", "escalate"]
        for project in projects:
            for i, rec_type in enumerate(rec_types[:3]):
                db.add(Recommendation(
                    project_id=project.id,
                    type=rec_type,
                    title=f"{rec_type.replace('_', ' ').title()} for {project.name}",
                    description=f"This is a sample {rec_type} recommendation",
                    reasoning=f"Based on analysis of {risk_types[i]} risk factors",
                    confidence=0.8,
                    priority="medium",
                    status="pending",
                ))
        
        # Create organizational memory
        memory_entries = [
            {"title": "Chose React for frontend", "content": "Team decided to use React with Next.js for the frontend based on team expertise and ecosystem.", "type": "decision"},
            {"title": "PostgreSQL for primary database", "content": "Selected PostgreSQL for its reliability, JSON support, and team familiarity.", "type": "decision"},
            {"title": "Authentication blocker resolution", "content": "Resolved JWT refresh token issue by implementing sliding window expiration.", "type": "blocker_resolution"},
            {"title": "Weekly standups improved coordination", "content": "Introducing 15-minute daily standups reduced coordination friction by 40%.", "type": "lesson_learned"},
        ]
        
        for mem in memory_entries:
            db.add(OrganizationMemory(
                organization_id=org.id,
                project_id=projects[0].id,
                memory_type=mem["type"],
                title=mem["title"],
                content=mem["content"],
                context={"tags": ["architecture", "team"]},
                source="manual",
                confidence=0.9,
                created_by=users[0].id,
            ))
        
        # Create audit log entries
        db.add(AuditLog(
            organization_id=org.id,
            user_id=users[0].id,
            action="create",
            entity_type="organization",
            entity_id=org.id,
            new_values={"name": org.name, "slug": org.slug},
            metadata={"source": "seed"},
        ))
        
        # Create notifications
        for user in users[:3]:
            db.add(Notification(
                organization_id=org.id,
                user_id=user.id,
                type="welcome",
                title="Welcome to TeamSync AI!",
                message="Your organization has been set up. Start by creating your first project.",
                priority="medium",
            ))
        
        await db.commit()
        print("Database seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())