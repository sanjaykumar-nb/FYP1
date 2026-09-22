from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.organization import Organization
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskDependency
from app.models.role import Role, UserRole
from app.core.security import get_password_hash_async, verify_password_async
from app.core.exceptions import NotFoundError, ConflictError, ValidationError


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user or not await verify_password_async(password, user.password_hash):
            return None
        
        if not user.is_active:
            return None
        
        return user
    
    async def register_user(self, email: str, password: str, full_name: str = None, org_name: str = "My Organization") -> tuple[User, Organization]:
        # Check if email exists
        result = await self.db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ConflictError("Email already registered")
        
        # Create organization
        org_slug = org_name.lower().replace(" ", "-")[:100]
        result = await self.db.execute(select(Organization).where(Organization.slug == org_slug))
        if result.scalar_one_or_none():
            org_slug = f"{org_slug}-{uuid4().hex[:8]}"
        
        org = Organization(name=org_name, slug=org_slug)
        self.db.add(org)
        await self.db.flush()
        
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
        self.db.add_all(roles)
        await self.db.flush()
        
        # Create user
        user = User(
            organization_id=org.id,
            email=email,
            password_hash=await get_password_hash_async(password),
            full_name=full_name,
        )
        self.db.add(user)
        await self.db.flush()
        
        # Assign owner role
        owner_role = next(r for r in roles if r.name == "owner")
        user_role = UserRole(
            user_id=user.id,
            role_id=owner_role.id,
            organization_id=org.id,
        )
        self.db.add(user_role)
        
        await self.db.commit()
        await self.db.refresh(user)
        await self.db.refresh(org)
        
        return user, org


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_organization(self, org_id: UUID) -> Optional[Organization]:
        result = await self.db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()
    
    async def update_organization(self, org_id: UUID, data: dict) -> Organization:
        org = await self.get_organization(org_id)
        if not org:
            raise NotFoundError("Organization not found")
        
        for key, value in data.items():
            setattr(org, key, value)
        
        await self.db.commit()
        await self.db.refresh(org)
        return org
    
    async def list_user_organizations(self, user_id: UUID) -> list[Organization]:
        result = await self.db.execute(
            select(Organization)
            .join(User, User.organization_id == Organization.id)
            .where(User.id == user_id)
        )
        return result.scalars().all()


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_project(self, project_id: UUID, org_id: UUID) -> Optional[Project]:
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_projects(
        self,
        org_id: UUID,
        status: str = None,
        team_id: UUID = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Project], int]:
        query = select(Project).where(Project.organization_id == org_id)
        
        if status:
            query = query.where(Project.status == status)
        if team_id:
            query = query.where(Project.team_id == team_id)
        
        count_query = select(func.count(Project.id)).where(Project.organization_id == org_id)
        if status:
            count_query = count_query.where(Project.status == status)
        if team_id:
            count_query = count_query.where(Project.team_id == team_id)
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        query = query.order_by(Project.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        projects = result.scalars().all()
        
        return projects, total
    
    async def create_project(
        self,
        org_id: UUID,
        user_id: UUID,
        name: str,
        key: str,
        description: str = None,
        team_id: UUID = None,
        start_date: str = None,
        target_end_date: str = None,
    ) -> Project:
        result = await self.db.execute(
            select(Project).where(
                Project.organization_id == org_id,
                Project.key == key.upper(),
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError("Project key already exists")
        
        project = Project(
            organization_id=org_id,
            team_id=team_id,
            name=name,
            description=description,
            key=key.upper(),
        )
        self.db.add(project)
        await self.db.flush()
        
        member = ProjectMember(
            project_id=project.id,
            user_id=user_id,
            role="project_manager",
        )
        self.db.add(member)
        
        await self.db.commit()
        await self.db.refresh(project)
        return project
    
    async def update_project(self, project_id: UUID, org_id: UUID, data: dict) -> Project:
        project = await self.get_project(project_id, org_id)
        if not project:
            raise NotFoundError("Project not found")
        
        for key, value in data.items():
            setattr(project, key, value)
        
        await self.db.commit()
        await self.db.refresh(project)
        return project
    
    async def archive_project(self, project_id: UUID, org_id: UUID) -> Project:
        project = await self.get_project(project_id, org_id)
        if not project:
            raise NotFoundError("Project not found")
        
        project.status = "archived"
        await self.db.commit()
        await self.db.refresh(project)
        return project
    
    async def add_member(self, project_id: UUID, org_id: UUID, user_id: UUID, role: str = "developer") -> ProjectMember:
        project = await self.get_project(project_id, org_id)
        if not project:
            raise NotFoundError("Project not found")
        
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("User not found in organization")
        
        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError("User is already a member")
        
        member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member
    
    async def list_members(self, project_id: UUID, org_id: UUID, page: int = 1, page_size: int = 20) -> tuple[list, int]:
        project = await self.get_project(project_id, org_id)
        if not project:
            raise NotFoundError("Project not found")
        
        query = (
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
        )
        
        count_query = select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        members = result.all()
        
        return members, total


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_task(self, task_id: UUID, org_id: UUID) -> Optional[Task]:
        result = await self.db.execute(
            select(Task)
            .join(Project, Project.id == Task.project_id)
            .where(Task.id == task_id, Project.organization_id == org_id)
        )
        return result.scalar_one_or_none()
    
    async def list_tasks(
        self,
        project_id: UUID,
        org_id: UUID,
        status: str = None,
        assignee_id: UUID = None,
        milestone_id: UUID = None,
        priority: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Task], int]:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        query = select(Task).where(Task.project_id == project_id)
        
        if status:
            query = query.where(Task.status == status)
        if assignee_id:
            query = query.where(Task.assignee_id == assignee_id)
        if milestone_id:
            query = query.where(Task.milestone_id == milestone_id)
        if priority:
            query = query.where(Task.priority == priority)
        
        count_query = select(func.count(Task.id)).where(Task.project_id == project_id)
        if status:
            count_query = count_query.where(Task.status == status)
        if assignee_id:
            count_query = count_query.where(Task.assignee_id == assignee_id)
        if milestone_id:
            count_query = count_query.where(Task.milestone_id == milestone_id)
        if priority:
            count_query = count_query.where(Task.priority == priority)
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        query = query.order_by(Task.position).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        tasks = result.scalars().all()
        
        return tasks, total
    
    async def create_task(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        title: str,
        description: str = None,
        status: str = "backlog",
        priority: str = "medium",
        milestone_id: UUID = None,
        parent_task_id: UUID = None,
        assignee_id: UUID = None,
        story_points: int = None,
        estimated_hours: float = None,
        due_date: str = None,
        blocked_reason: str = None,
    ) -> Task:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        max_pos_result = await self.db.execute(
            select(func.max(Task.position)).where(
                Task.project_id == project_id,
                Task.status == status,
            )
        )
        max_position = max_pos_result.scalar() or 0
        
        task = Task(
            project_id=project_id,
            milestone_id=milestone_id,
            parent_task_id=parent_task_id,
            assignee_id=assignee_id,
            reporter_id=user_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            story_points=story_points,
            estimated_hours=estimated_hours,
            due_date=due_date,
            blocked_reason=blocked_reason,
            position=max_position + 1,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task
    
    async def update_task(self, task_id: UUID, org_id: UUID, data: dict) -> Task:
        task = await self.get_task(task_id, org_id)
        if not task:
            raise NotFoundError("Task not found")
        
        for key, value in data.items():
            setattr(task, key, value)
        
        await self.db.commit()
        await self.db.refresh(task)
        return task
    
    async def move_task(self, task_id: UUID, org_id: UUID, status: str = None, position: int = None, milestone_id: UUID = None) -> Task:
        task = await self.get_task(task_id, org_id)
        if not task:
            raise NotFoundError("Task not found")
        
        if position is not None:
            task.position = position
        
        if status and status != task.status:
            from datetime import datetime
            task.status = status
            if status == "in_progress" and not task.started_at:
                task.started_at = datetime.utcnow()
            elif status == "done" and not task.completed_at:
                task.completed_at = datetime.utcnow()
        
        if milestone_id is not None:
            task.milestone_id = milestone_id
        
        await self.db.commit()
        await self.db.refresh(task)
        return task
    
    async def add_dependency(self, blocking_task_id: UUID, blocked_task_id: UUID, org_id: UUID, dep_type: str = "blocks") -> TaskDependency:
        for tid in [blocking_task_id, blocked_task_id]:
            result = await self.db.execute(
                select(Task)
                .join(Project, Project.id == Task.project_id)
                .where(Task.id == tid, Project.organization_id == org_id)
            )
            if not result.scalar_one_or_none():
                raise NotFoundError(f"Task {tid} not found")
        
        if blocking_task_id == blocked_task_id:
            raise ValidationError("Cannot create dependency on self")
        
        project_result = await self.db.execute(select(Task.project_id).where(Task.id == blocking_task_id))
        project_id = project_result.scalar()
        
        dep = TaskDependency(
            project_id=project_id,
            blocking_task_id=blocking_task_id,
            blocked_task_id=blocked_task_id,
            dependency_type=dep_type,
        )
        self.db.add(dep)
        await self.db.commit()
        await self.db.refresh(dep)
        return dep
    
    async def remove_dependency(self, dep_id: UUID, org_id: UUID) -> bool:
        result = await self.db.execute(
            select(TaskDependency)
            .join(Project, Project.id == TaskDependency.project_id)
            .where(TaskDependency.id == dep_id, Project.organization_id == org_id)
        )
        dep = result.scalar_one_or_none()
        if not dep:
            raise NotFoundError("Dependency not found")
        
        await self.db.delete(dep)
        await self.db.commit()
        return True