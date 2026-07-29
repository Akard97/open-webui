import asyncio
import re
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
    select,
    delete,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


def _now() -> int:
    return int(time.time() * 1000)


# Process-local writer locks for a task's assignee-invariant sections (parent
# merge, removal cascade, subtask assignee writes). SQLite — the default
# backend — has no row locks (with_for_update() is a no-op there), so these
# read-modify-write sections serialize through this lock instead; on Postgres
# the retained with_for_update() row locks additionally protect across
# processes. On SQLite the supported topology is a single app process.
# Entries are never evicted: locks are tiny, keyed by task id, and eviction
# races (two coroutines holding different Lock objects for the same task)
# would silently break mutual exclusion.
_task_write_locks: dict[str, asyncio.Lock] = {}


def _task_write_lock(task_id: str) -> asyncio.Lock:
    lock = _task_write_locks.get(task_id)
    if lock is None:
        lock = _task_write_locks.setdefault(task_id, asyncio.Lock())
    return lock


def _id() -> str:
    return str(uuid.uuid4())


# ──────────────────────────── Tables ────────────────────────────


class WorkosTeam(Base):
    __tablename__ = 'workos_team'

    id = Column(Text, primary_key=True, unique=True)
    key = Column(Text, unique=True)
    name = Column(Text)
    icon = Column(Text, nullable=True)
    task_seq = Column(BigInteger, default=0)
    archived = Column(Boolean, default=False)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


TEAM_ROLES = {'owner', 'admin', 'member'}
WORKSPACE_ROLES = {'admin', 'member'}


def _validate_role(role: str, allowed: set) -> None:
    if role not in allowed:
        raise ValueError(f'invalid role: {role!r}')


class WorkosTeamMember(Base):
    __tablename__ = 'workos_team_member'
    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='uq_workos_team_member'),)

    id = Column(Text, primary_key=True, unique=True)
    team_id = Column(Text)
    user_id = Column(Text)
    role = Column(Text)  # owner | admin | member (validated in the DAO)
    created_at = Column(BigInteger)


class WorkosWorkspace(Base):
    __tablename__ = 'workos_workspace'

    id = Column(Text, primary_key=True, unique=True)
    team_id = Column(Text)
    name = Column(Text)
    icon = Column(Text, nullable=True)
    visibility = Column(Text, default='team')  # team | restricted
    archived = Column(Boolean, default=False)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class WorkosWorkspaceMember(Base):
    __tablename__ = 'workos_workspace_member'
    __table_args__ = (UniqueConstraint('workspace_id', 'user_id', name='uq_workos_workspace_member'),)

    id = Column(Text, primary_key=True, unique=True)
    workspace_id = Column(Text)
    user_id = Column(Text)
    role = Column(Text)  # admin | member (validated in the DAO)
    created_at = Column(BigInteger)


class WorkosWorkstream(Base):
    __tablename__ = 'workos_workstream'

    id = Column(Text, primary_key=True, unique=True)
    workspace_id = Column(Text)
    name = Column(Text)
    icon = Column(Text, nullable=True)
    archived = Column(Boolean, default=False)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ──────────────────────────── Pydantic ────────────────────────────


class TeamModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    key: str
    name: str
    icon: Optional[str] = None
    task_seq: int
    archived: bool
    created_by_id: Optional[str] = None
    created_at: int
    updated_at: int


class TeamMemberModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    team_id: str
    user_id: str
    role: str
    created_at: int


class WorkspaceModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    team_id: str
    name: str
    icon: Optional[str] = None
    visibility: str
    archived: bool
    created_by_id: Optional[str] = None
    created_at: int
    updated_at: int


class WorkspaceMemberModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    user_id: str
    role: str
    created_at: int


class WorkstreamModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    name: str
    icon: Optional[str] = None
    archived: bool
    created_by_id: Optional[str] = None
    created_at: int
    updated_at: int


# ──────────────────────────── DAO ────────────────────────────


class TeamsDao:
    async def insert(
        self, name: str, key: str, icon: Optional[str], created_by_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> TeamModel:
        async with get_async_db_context(db) as db:
            row = WorkosTeam(
                id=_id(), key=key, name=name, icon=icon, task_seq=0, archived=False,
                created_by_id=created_by_id, created_at=_now(), updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return TeamModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=id))
            row = res.scalars().first()
            return TeamModel.model_validate(row) if row else None

    async def get_by_key(self, key: str, db: Optional[AsyncSession] = None) -> Optional[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(key=key))
            row = res.scalars().first()
            return TeamModel.model_validate(row) if row else None

    async def list_all(self, db: Optional[AsyncSession] = None) -> list[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).order_by(WorkosTeam.created_at.desc()))
            return [TeamModel.model_validate(r) for r in res.scalars().all()]

    async def list_for_user(self, user_id: str, db: Optional[AsyncSession] = None) -> list[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosTeam)
                .join(WorkosTeamMember, WorkosTeamMember.team_id == WorkosTeam.id)
                .filter(WorkosTeamMember.user_id == user_id)
                .order_by(WorkosTeam.created_at.desc())
            )
            return [TeamModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return TeamModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosTeam).filter_by(id=id))
            await db.commit()
            return True

    async def next_task_number(self, team_id: str, db: Optional[AsyncSession] = None) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=team_id).with_for_update())
            row = res.scalars().first()
            if not row:
                raise ValueError('team not found')
            row.task_seq = (row.task_seq or 0) + 1
            new_value = row.task_seq
            await db.commit()
            return new_value


class TeamMembersDao:
    async def add(self, team_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None) -> TeamMemberModel:
        _validate_role(role, TEAM_ROLES)
        async with get_async_db_context(db) as db:
            row = WorkosTeamMember(id=_id(), team_id=team_id, user_id=user_id, role=role, created_at=_now())
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return TeamMemberModel.model_validate(row)

    async def get(self, team_id: str, user_id: str, db: Optional[AsyncSession] = None) -> Optional[TeamMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            row = res.scalars().first()
            return TeamMemberModel.model_validate(row) if row else None

    async def list_for_team(self, team_id: str, db: Optional[AsyncSession] = None) -> list[TeamMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id))
            return [TeamMemberModel.model_validate(r) for r in res.scalars().all()]

    async def list_for_user(self, user_id: str, db: Optional[AsyncSession] = None) -> list[TeamMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(user_id=user_id))
            return [TeamMemberModel.model_validate(r) for r in res.scalars().all()]

    async def update_role(
        self, team_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None
    ) -> Optional[TeamMemberModel]:
        _validate_role(role, TEAM_ROLES)
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            row = res.scalars().first()
            if not row:
                return None
            row.role = role
            await db.commit()
            await db.refresh(row)
            return TeamMemberModel.model_validate(row)

    async def remove(self, team_id: str, user_id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            await db.commit()
            return True


class WorkspacesDao:
    async def insert(
        self, team_id: str, name: str, icon: Optional[str], visibility: str,
        created_by_id: Optional[str], db: Optional[AsyncSession] = None,
    ) -> WorkspaceModel:
        async with get_async_db_context(db) as db:
            row = WorkosWorkspace(
                id=_id(), team_id=team_id, name=name, icon=icon, visibility=visibility,
                archived=False, created_by_id=created_by_id, created_at=_now(), updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return WorkspaceModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[WorkspaceModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspace).filter_by(id=id))
            row = res.scalars().first()
            return WorkspaceModel.model_validate(row) if row else None

    async def list_for_team(self, team_id: str, db: Optional[AsyncSession] = None) -> list[WorkspaceModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosWorkspace).filter_by(team_id=team_id).order_by(WorkosWorkspace.created_at.asc())
            )
            return [WorkspaceModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[WorkspaceModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspace).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return WorkspaceModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspace).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosWorkspace).filter_by(id=id))
            await db.commit()
            return True


class WorkspaceMembersDao:
    async def add(
        self, workspace_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None
    ) -> WorkspaceMemberModel:
        _validate_role(role, WORKSPACE_ROLES)
        async with get_async_db_context(db) as db:
            row = WorkosWorkspaceMember(
                id=_id(), workspace_id=workspace_id, user_id=user_id, role=role, created_at=_now()
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return WorkspaceMemberModel.model_validate(row)

    async def get(
        self, workspace_id: str, user_id: str, db: Optional[AsyncSession] = None
    ) -> Optional[WorkspaceMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            row = res.scalars().first()
            return WorkspaceMemberModel.model_validate(row) if row else None

    async def list_for_workspace(
        self, workspace_id: str, db: Optional[AsyncSession] = None
    ) -> list[WorkspaceMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id))
            return [WorkspaceMemberModel.model_validate(r) for r in res.scalars().all()]

    async def update_role(
        self, workspace_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None
    ) -> Optional[WorkspaceMemberModel]:
        _validate_role(role, WORKSPACE_ROLES)
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            row = res.scalars().first()
            if not row:
                return None
            row.role = role
            await db.commit()
            await db.refresh(row)
            return WorkspaceMemberModel.model_validate(row)

    async def remove(self, workspace_id: str, user_id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            await db.commit()
            return True


class WorkstreamsDao:
    async def insert(
        self, workspace_id: str, name: str, icon: Optional[str], created_by_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> WorkstreamModel:
        async with get_async_db_context(db) as db:
            row = WorkosWorkstream(
                id=_id(), workspace_id=workspace_id, name=name, icon=icon, archived=False,
                created_by_id=created_by_id, created_at=_now(), updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return WorkstreamModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[WorkstreamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkstream).filter_by(id=id))
            row = res.scalars().first()
            return WorkstreamModel.model_validate(row) if row else None

    async def list_for_workspace(self, workspace_id: str, db: Optional[AsyncSession] = None) -> list[WorkstreamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosWorkstream).filter_by(workspace_id=workspace_id).order_by(WorkosWorkstream.created_at.asc())
            )
            return [WorkstreamModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[WorkstreamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkstream).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return WorkstreamModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkstream).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosWorkstream).filter_by(id=id))
            await db.commit()
            return True


Teams = TeamsDao()
TeamMembers = TeamMembersDao()
Workspaces = WorkspacesDao()
WorkspaceMembers = WorkspaceMembersDao()
Workstreams = WorkstreamsDao()


# ──────────────────────────── Label + Task Tables ────────────────────────────


class WorkosLabel(Base):
    __tablename__ = 'workos_label'

    id = Column(Text, primary_key=True, unique=True)
    team_id = Column(Text)
    name = Column(Text)
    color = Column(Text)
    created_at = Column(BigInteger)


class WorkosTask(Base):
    __tablename__ = 'workos_task'

    id = Column(Text, primary_key=True, unique=True)
    workstream_id = Column(Text)
    team_id = Column(Text)
    number = Column(BigInteger)
    key = Column(Text)
    title = Column(Text)
    description = Column(Text, nullable=True)
    status = Column(Text, default='backlog')
    priority = Column(Text, nullable=True)
    assignee_ids = Column(JSON, default=list)
    start_date = Column(BigInteger, nullable=True)
    due_date = Column(BigInteger, nullable=True)
    progress = Column(Integer, default=0)
    attachment_required = Column(Boolean, default=False)
    labels = Column(JSON, default=list)
    sort_key = Column(Float, default=0.0)
    created_by_id = Column(Text, nullable=True)
    completed_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class WorkosSubtask(Base):
    __tablename__ = 'workos_subtask'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    title = Column(Text)
    completed = Column(Boolean, default=False)
    assignee_ids = Column(JSON, default=list)
    sort_key = Column(Float, default=0.0)
    created_by_id = Column(Text, nullable=True)
    completed_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ──────────────────────────── Label + Task Pydantic ────────────────────────────


class LabelModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    team_id: str
    name: str
    color: str
    created_at: int


class TaskModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workstream_id: str
    team_id: str
    number: int
    key: str
    title: str
    description: Optional[str] = None
    status: str
    priority: Optional[str] = None
    assignee_ids: list = []
    start_date: Optional[int] = None
    due_date: Optional[int] = None
    progress: int
    attachment_required: bool = False
    subtask_total: int = 0
    subtask_completed: int = 0
    labels: list = []
    sort_key: float
    created_by_id: Optional[str] = None
    completed_at: Optional[int] = None
    created_at: int
    updated_at: int


class SubtaskModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    title: str
    completed: bool = False
    assignee_ids: list = []
    sort_key: float
    created_by_id: Optional[str] = None
    completed_at: Optional[int] = None
    created_at: int
    updated_at: int


# ──────────────────────────── Label + Task DAO ────────────────────────────


class LabelsDao:
    async def insert(self, team_id: str, name: str, color: str, db: Optional[AsyncSession] = None) -> LabelModel:
        async with get_async_db_context(db) as db:
            row = WorkosLabel(id=_id(), team_id=team_id, name=name, color=color, created_at=_now())
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return LabelModel.model_validate(row)

    async def list_for_team(self, team_id: str, db: Optional[AsyncSession] = None) -> list[LabelModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosLabel).filter_by(team_id=team_id).order_by(WorkosLabel.created_at.asc()))
            return [LabelModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[LabelModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosLabel).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            await db.commit()
            await db.refresh(row)
            return LabelModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosLabel).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosLabel).filter_by(id=id))
            await db.commit()
            return True

    async def prune_unused(
        self, team_id: str, candidate_ids: list[str], db: Optional[AsyncSession] = None
    ) -> list[str]:
        """Delete any of ``candidate_ids`` no longer referenced by a task in the team.

        Drives auto-cleanup of tags that become orphaned when unassigned from a task
        or when a task is deleted. One scan of the team's task-label arrays (bounded by
        team size, portable across SQLite/Postgres) decides which candidates survive.
        Returns the ids actually deleted.
        """
        candidates = [c for c in dict.fromkeys(candidate_ids) if c]
        if not candidates:
            return []
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTask.labels).filter_by(team_id=team_id))
            used: set = set()
            for labels in res.scalars().all():
                if labels:
                    used.update(labels)
            orphans = [c for c in candidates if c not in used]
            if orphans:
                await db.execute(
                    delete(WorkosLabel).where(
                        WorkosLabel.id.in_(orphans), WorkosLabel.team_id == team_id
                    )
                )
                await db.commit()
            return orphans


class TasksDao:
    async def _with_counts(self, rows: list[WorkosTask], db: AsyncSession) -> list[TaskModel]:
        if not rows:
            return []
        ids = [r.id for r in rows]
        res = await db.execute(
            select(
                WorkosSubtask.task_id,
                func.count(WorkosSubtask.id),
                func.sum(WorkosSubtask.completed.cast(Integer)),
            )
            .where(WorkosSubtask.task_id.in_(ids))
            .group_by(WorkosSubtask.task_id)
        )
        counts = {task_id: (total or 0, completed or 0) for task_id, total, completed in res.all()}
        out = []
        for row in rows:
            model = TaskModel.model_validate(row)
            total, completed = counts.get(row.id, (0, 0))
            model.subtask_total = int(total)
            model.subtask_completed = int(completed)
            out.append(model)
        return out

    async def insert(
        self, workstream_id: str, team_id: str, team_key: str, title: str, created_by_id: Optional[str],
        *, description: Optional[str] = None, status: str = 'backlog', priority: Optional[str] = None,
        assignee_ids: Optional[list] = None, start_date: Optional[int] = None,
        due_date: Optional[int] = None, labels: Optional[list] = None,
        attachment_required: bool = False,
        db: Optional[AsyncSession] = None,
    ) -> TaskModel:
        number = await Teams.next_task_number(team_id, db=db)
        async with get_async_db_context(db) as db:
            now = _now()
            row = WorkosTask(
                id=_id(), workstream_id=workstream_id, team_id=team_id, number=number,
                key=f'{team_key}-{number}', title=title, description=description, status=status,
                priority=priority, assignee_ids=assignee_ids or [], start_date=start_date,
                due_date=due_date, progress=0,
                attachment_required=attachment_required,
                labels=labels or [], sort_key=float(now), created_by_id=created_by_id,
                completed_at=now if status == 'done' else None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return (await self._with_counts([row], db))[0]

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[TaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTask).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            return (await self._with_counts([row], db))[0]

    async def list_for_workstream(self, workstream_id: str, db: Optional[AsyncSession] = None) -> list[TaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosTask).filter_by(workstream_id=workstream_id)
                .order_by(WorkosTask.status.asc(), WorkosTask.sort_key.asc())
            )
            rows = res.scalars().all()
            return await self._with_counts(rows, db)

    async def list_for_user(
        self, user_id: str, team_ids: list, db: Optional[AsyncSession] = None
    ) -> list[TaskModel]:
        """Tasks the user created or is assigned to, within the given teams.

        Candidates are bounded by ``team_id IN team_ids`` (the denormalized team
        column), then membership is decided in Python because ``assignee_ids`` is a
        JSON list with no portable SQL containment across SQLite/Postgres. The router
        applies the per-task visibility filter on top.
        """
        if not team_ids:
            return []
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosTask)
                .filter(WorkosTask.team_id.in_(team_ids))
                .order_by(WorkosTask.created_at.asc())
            )
            rows = [
                r for r in res.scalars().all()
                if r.created_by_id == user_id or user_id in (r.assignee_ids or [])
            ]
            return await self._with_counts(rows, db)

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[TaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTask).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            self._apply_fields(row, fields)
            await db.commit()
            await db.refresh(row)
            return (await self._with_counts([row], db))[0]

    def _apply_fields(self, row, fields: dict) -> None:
        prev_status = row.status
        for k, v in fields.items():
            setattr(row, k, v)
        if 'status' in fields and fields['status'] != prev_status:
            # Stamp only on a real transition; a no-op re-save of 'done' must not
            # shift completion history (feeds the Overview momentum chart).
            row.completed_at = _now() if fields['status'] == 'done' else None
        row.updated_at = _now()

    async def merge_assignees(
        self, id: str, add_ids: list, db: Optional[AsyncSession] = None
    ) -> Optional[tuple[TaskModel, TaskModel]]:
        """Union ``add_ids`` into the task's assignee list atomically.

        The union is computed from the row read (FOR UPDATE where the backend
        supports it) inside this transaction — never from a caller snapshot —
        so a concurrent removal that committed after the caller loaded the task
        stays removed unless explicitly re-requested. Returns (before, after)
        models, or None if the task is gone.
        """
        async with _task_write_lock(id), get_async_db_context(db) as db:
            try:
                res = await db.execute(select(WorkosTask).filter_by(id=id).with_for_update())
                row = res.scalars().first()
                if not row:
                    return None
                before = (await self._with_counts([row], db))[0]
                missing = [uid for uid in add_ids if uid not in (row.assignee_ids or [])]
                if not missing:
                    return before, before
                row.assignee_ids = [*(row.assignee_ids or []), *missing]
                row.updated_at = _now()
                await db.commit()
                await db.refresh(row)
                return before, (await self._with_counts([row], db))[0]
            except Exception:
                await db.rollback()
                raise

    async def _cascade_subtask_assignees(self, db: AsyncSession, task_id: str, removed: list) -> list:
        """Strip ``removed`` from every subtask of the task. Runs inside the
        caller's transaction and does NOT commit; returns the changed rows."""
        res = await db.execute(select(WorkosSubtask).filter_by(task_id=task_id))
        changed = []
        for st in res.scalars().all():
            kept = [uid for uid in (st.assignee_ids or []) if uid not in removed]
            if kept != (st.assignee_ids or []):
                st.assignee_ids = kept
                st.updated_at = _now()
                changed.append(st)
        return changed

    async def update_with_cascade(
        self, id: str, fields: dict, db: Optional[AsyncSession] = None
    ) -> Optional[tuple[TaskModel, list[SubtaskModel]]]:
        """update_fields plus the subtask-assignee strip in ONE transaction.

        Dropping a parent assignee and stripping them from subtasks commit (or
        roll back) together, so the "subtask assignees ⊆ parent assignees"
        invariant can never half-commit. ``removed`` is computed from the row
        read in this transaction, not a caller snapshot. Returns
        (task, changed_subtasks) or None if the task is gone.
        """
        async with _task_write_lock(id), get_async_db_context(db) as db:
            try:
                res = await db.execute(select(WorkosTask).filter_by(id=id).with_for_update())
                row = res.scalars().first()
                if not row:
                    return None
                prev_assignees = list(row.assignee_ids or [])
                self._apply_fields(row, fields)
                changed_rows = []
                if 'assignee_ids' in fields:
                    removed = [uid for uid in prev_assignees if uid not in (row.assignee_ids or [])]
                    if removed:
                        changed_rows = await self._cascade_subtask_assignees(db, id, removed)
                # Capture the cascade results before commit expires the rows.
                changed = [SubtaskModel.model_validate(st) for st in changed_rows]
                await db.commit()
                await db.refresh(row)
                return (await self._with_counts([row], db))[0], changed
            except Exception:
                await db.rollback()
                raise

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTask).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosTask).filter_by(id=id))
            await db.commit()
            return True


Labels = LabelsDao()
Tasks = TasksDao()


class SubtasksDao:
    @staticmethod
    async def _parent_subset(db: AsyncSession, task_id: str, assignee_ids: list) -> list:
        """Intersect ``assignee_ids`` against the parent task read (FOR UPDATE
        where supported) in the caller's transaction. Enforces the "subtask
        assignees ⊆ parent assignees" invariant at the write itself, so a stale
        list racing a parent-removal cascade can never resurrect a removed
        assignee — whichever transaction commits second still satisfies it."""
        res = await db.execute(select(WorkosTask).filter_by(id=task_id).with_for_update())
        parent = res.scalars().first()
        allowed = set(parent.assignee_ids or []) if parent else set()
        return [uid for uid in assignee_ids if uid in allowed]

    async def insert(
        self, task_id: str, title: str, created_by_id: Optional[str],
        *, assignee_ids: Optional[list] = None, sort_key: Optional[float] = None,
        db: Optional[AsyncSession] = None,
    ) -> SubtaskModel:
        async with _task_write_lock(task_id), get_async_db_context(db) as db:
            now = _now()
            row = WorkosSubtask(
                id=_id(), task_id=task_id, title=title, completed=False,
                assignee_ids=await self._parent_subset(db, task_id, assignee_ids or []),
                sort_key=sort_key if sort_key is not None else float(now),
                created_by_id=created_by_id, completed_at=None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return SubtaskModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[SubtaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosSubtask).filter_by(id=id))
            row = res.scalars().first()
            return SubtaskModel.model_validate(row) if row else None

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list[SubtaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosSubtask).filter_by(task_id=task_id).order_by(WorkosSubtask.sort_key.asc())
            )
            return [SubtaskModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[SubtaskModel]:
        async with get_async_db_context(db) as db:
            if 'assignee_ids' not in fields:
                res = await db.execute(select(WorkosSubtask).filter_by(id=id))
                row = res.scalars().first()
                if not row:
                    return None
                return await self._apply_and_commit(row, fields, db)
            # Assignee writes serialize on the parent's task lock. task_id is
            # immutable on subtasks, so reading it unlocked is safe; the row
            # itself is re-read under the lock.
            res = await db.execute(select(WorkosSubtask.task_id).filter_by(id=id))
            task_id = res.scalar_one_or_none()
            if task_id is None:
                return None
            async with _task_write_lock(task_id):
                res = await db.execute(select(WorkosSubtask).filter_by(id=id))
                row = res.scalars().first()
                if not row:
                    return None
                fields = {**fields, 'assignee_ids':
                          await self._parent_subset(db, task_id, fields['assignee_ids'])}
                return await self._apply_and_commit(row, fields, db)

    @staticmethod
    async def _apply_and_commit(row, fields: dict, db: AsyncSession) -> SubtaskModel:
        if 'completed' in fields:
            row.completed_at = _now() if fields['completed'] else None
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = _now()
        await db.commit()
        await db.refresh(row)
        return SubtaskModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosSubtask).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosSubtask).filter_by(id=id))
            await db.commit()
            return True


Subtasks = SubtasksDao()


# ──────────────────────────── Comment + Activity Tables ────────────────────────────


class WorkosComment(Base):
    __tablename__ = 'workos_comment'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    user_id = Column(Text)
    body = Column(Text)
    mentions = Column(JSON, default=list)
    parent_id = Column(Text, nullable=True)   # threading: null = top-level; parent is on the same task
    deleted_at = Column(BigInteger, nullable=True)  # tombstone marker (body/mentions blanked when set)
    edited_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class WorkosActivity(Base):
    __tablename__ = 'workos_activity'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    team_id = Column(Text)
    user_id = Column(Text)
    type = Column(Text)
    data = Column(JSON, default=dict)
    created_at = Column(BigInteger)


class WorkosCommentReaction(Base):
    __tablename__ = 'workos_comment_reaction'

    id = Column(Text, primary_key=True, unique=True)
    comment_id = Column(Text)
    user_id = Column(Text)
    emoji = Column(Text)
    created_at = Column(BigInteger)

    __table_args__ = (
        UniqueConstraint('comment_id', 'user_id', 'emoji', name='uq_workos_reaction'),
    )


class CommentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    user_id: str
    body: str
    mentions: list = []
    parent_id: Optional[str] = None
    deleted_at: Optional[int] = None
    reactions: list = []
    edited_at: Optional[int] = None
    created_at: int
    updated_at: int


class ActivityModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    team_id: str
    user_id: str
    type: str
    data: dict = {}
    created_at: int


_MENTION_RE = re.compile(r'\(mention:([^)\s]+)\)')


def parse_mentions(body: str) -> list:
    """Extract unique user ids from `@[Name](mention:ID)` tokens, preserving order."""
    out: list = []
    for uid in _MENTION_RE.findall(body or ''):
        if uid not in out:
            out.append(uid)
    return out


_ACTIVITY_FIELDS = {
    'status': 'status_changed',
    'assignee_ids': 'assignee_changed',
    'priority': 'priority_changed',
    'start_date': 'start_changed',
    'due_date': 'due_changed',
    'title': 'title_changed',
    'description': 'description_changed',
    'attachment_required': 'attachment_required_changed',
}


def task_change_activities(actor_id: str, before: dict, after: dict) -> list:
    """Diff two task field-dicts into activity entries (pure; no DB)."""
    acts: list = []
    for field, atype in _ACTIVITY_FIELDS.items():
        if field in after and after[field] != before.get(field):
            if field == 'assignee_ids':
                b, a = before.get(field) or [], after[field] or []
                data = {'added': [x for x in a if x not in b], 'removed': [x for x in b if x not in a]}
            else:
                data = {'from': before.get(field), 'to': after[field]}
            acts.append({'type': atype, 'data': data})
    # Completion transitions get their own entry in addition to status_changed.
    if 'status' in after and after['status'] != before.get('status'):
        if after['status'] == 'done':
            acts.append({'type': 'completed', 'data': {}})
        elif before.get('status') == 'done':
            acts.append({'type': 'reopened', 'data': {}})
    return acts


class CommentsDao:
    async def insert(
        self, task_id: str, user_id: str, body: str, mentions: list,
        parent_id: Optional[str] = None, db: Optional[AsyncSession] = None,
    ) -> CommentModel:
        async with get_async_db_context(db) as db:
            now = _now()
            row = WorkosComment(
                id=_id(), task_id=task_id, user_id=user_id, body=body,
                mentions=mentions or [], parent_id=parent_id, deleted_at=None,
                edited_at=None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return CommentModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[CommentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            row = res.scalars().first()
            return CommentModel.model_validate(row) if row else None

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosComment).filter_by(task_id=task_id).order_by(WorkosComment.created_at.asc())
            )
            return [CommentModel.model_validate(r) for r in res.scalars().all()]

    async def update_body(
        self, id: str, body: str, mentions: list, db: Optional[AsyncSession] = None
    ) -> Optional[CommentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            now = _now()
            row.body = body
            row.mentions = mentions or []
            row.edited_at = now
            row.updated_at = now
            await db.commit()
            await db.refresh(row)
            return CommentModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosComment).filter_by(id=id))
            await db.commit()
            return True

    async def has_children(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment.id).filter_by(parent_id=id).limit(1))
            return res.scalars().first() is not None

    async def tombstone(self, id: str, db: Optional[AsyncSession] = None) -> Optional[CommentModel]:
        """Soft-delete: blank content, keep the row so replies stay attached."""
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            now = _now()
            row.deleted_at = now
            row.body = ''
            row.mentions = []
            row.updated_at = now
            await db.commit()
            await db.refresh(row)
            return CommentModel.model_validate(row)


class ActivityDao:
    async def insert(
        self, task_id: str, team_id: str, user_id: str, type: str, data: dict,
        db: Optional[AsyncSession] = None,
    ) -> ActivityModel:
        async with get_async_db_context(db) as db:
            row = WorkosActivity(
                id=_id(), task_id=task_id, team_id=team_id, user_id=user_id,
                type=type, data=data or {}, created_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return ActivityModel.model_validate(row)

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosActivity).filter_by(task_id=task_id).order_by(WorkosActivity.created_at.asc())
            )
            return [ActivityModel.model_validate(r) for r in res.scalars().all()]

    async def list_for_workstream(
        self, workstream_id: str, limit: int = 30, db: Optional[AsyncSession] = None
    ) -> list:
        """Newest activities across the workstream's tasks, joined with task key/title."""
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosActivity, WorkosTask.key, WorkosTask.title)
                .join(WorkosTask, WorkosTask.id == WorkosActivity.task_id)
                .where(WorkosTask.workstream_id == workstream_id)
                .order_by(WorkosActivity.created_at.desc())
                .limit(limit)
            )
            out = []
            for row, task_key, task_title in res.all():
                item = ActivityModel.model_validate(row).model_dump()
                item['task_key'] = task_key
                item['task_title'] = task_title
                out.append(item)
            return out

    async def timestamps_for_workstream(
        self, workstream_id: str, since_ms: int, db: Optional[AsyncSession] = None
    ) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosActivity.created_at)
                .join(WorkosTask, WorkosTask.id == WorkosActivity.task_id)
                .where(WorkosTask.workstream_id == workstream_id, WorkosActivity.created_at >= since_ms)
            )
            return [r[0] for r in res.all()]


class ReactionsDao:
    async def toggle(
        self, comment_id: str, user_id: str, emoji: str, db: Optional[AsyncSession] = None
    ) -> bool:
        """Add the reaction, or remove it if it already exists. True = added."""
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosCommentReaction).filter_by(
                comment_id=comment_id, user_id=user_id, emoji=emoji))
            row = res.scalars().first()
            if row:
                await db.execute(delete(WorkosCommentReaction).filter_by(id=row.id))
                await db.commit()
                return False
            db.add(WorkosCommentReaction(
                id=_id(), comment_id=comment_id, user_id=user_id, emoji=emoji, created_at=_now(),
            ))
            await db.commit()
            return True

    async def purge_for_comment(self, comment_id: str, db: Optional[AsyncSession] = None) -> None:
        async with get_async_db_context(db) as db:
            await db.execute(delete(WorkosCommentReaction).filter_by(comment_id=comment_id))
            await db.commit()

    async def aggregate_for_comments(
        self, comment_ids: list, db: Optional[AsyncSession] = None
    ) -> dict:
        """{comment_id: [{'emoji','count','user_ids'}]} — entries ordered by first reaction."""
        if not comment_ids:
            return {}
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosCommentReaction)
                .where(WorkosCommentReaction.comment_id.in_(comment_ids))
                .order_by(WorkosCommentReaction.created_at.asc())
            )
            out: dict = {}
            for row in res.scalars().all():
                per = out.setdefault(row.comment_id, {})
                agg = per.setdefault(row.emoji, {'emoji': row.emoji, 'count': 0, 'user_ids': []})
                agg['count'] += 1
                agg['user_ids'].append(row.user_id)
            return {cid: list(per.values()) for cid, per in out.items()}


Comments = CommentsDao()
Reactions = ReactionsDao()
Activity = ActivityDao()


# ──────────────────────────── Attachment + Notification Tables ────────────────────────────


class WorkosAttachment(Base):
    __tablename__ = 'workos_attachment'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    comment_id = Column(Text, nullable=True)
    storage_key = Column(Text)
    name = Column(Text)
    size = Column(BigInteger)
    content_type = Column(Text, nullable=True)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)


class WorkosNotification(Base):
    __tablename__ = 'workos_notification'

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text)
    actor_id = Column(Text, nullable=True)
    task_id = Column(Text, nullable=True)
    comment_id = Column(Text, nullable=True)
    type = Column(Text)
    data = Column(JSON, default=dict)
    read = Column(Boolean, default=False)
    archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(BigInteger)


class AttachmentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    comment_id: Optional[str] = None
    storage_key: str
    name: str
    size: int
    content_type: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: int


class NotificationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    actor_id: Optional[str] = None
    task_id: Optional[str] = None
    comment_id: Optional[str] = None
    type: str
    data: dict = {}
    read: bool
    archived: bool = False
    created_at: int


class AttachmentsDao:
    async def insert(
        self, task_id: str, comment_id: Optional[str], storage_key: str, name: str,
        size: int, content_type: Optional[str], created_by_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> AttachmentModel:
        async with get_async_db_context(db) as db:
            row = WorkosAttachment(
                id=_id(), task_id=task_id, comment_id=comment_id, storage_key=storage_key,
                name=name, size=size, content_type=content_type,
                created_by_id=created_by_id, created_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return AttachmentModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[AttachmentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosAttachment).filter_by(id=id))
            row = res.scalars().first()
            return AttachmentModel.model_validate(row) if row else None

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosAttachment).filter_by(task_id=task_id).order_by(WorkosAttachment.created_at.asc())
            )
            return [AttachmentModel.model_validate(r) for r in res.scalars().all()]

    async def list_for_workstream(
        self, workstream_id: str, limit: int = 1000, db: Optional[AsyncSession] = None
    ) -> list:
        """Newest attachments across the workstream's tasks, joined with task key/title/status."""
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosAttachment, WorkosTask.key, WorkosTask.title, WorkosTask.status)
                .join(WorkosTask, WorkosTask.id == WorkosAttachment.task_id)
                .where(WorkosTask.workstream_id == workstream_id)
                .order_by(WorkosAttachment.created_at.desc())
                .limit(limit)
            )
            out = []
            for row, task_key, task_title, task_status in res.all():
                item = AttachmentModel.model_validate(row).model_dump()
                item['task_key'] = task_key
                item['task_title'] = task_title
                item['task_status'] = task_status
                out.append(item)
            return out

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosAttachment).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosAttachment).filter_by(id=id))
            await db.commit()
            return True


class NotificationsDao:
    async def insert(
        self, user_id: str, actor_id: Optional[str], type: str, data: dict,
        task_id: Optional[str] = None, comment_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> NotificationModel:
        async with get_async_db_context(db) as db:
            row = WorkosNotification(
                id=_id(), user_id=user_id, actor_id=actor_id, task_id=task_id,
                comment_id=comment_id, type=type, data=data or {}, read=False, created_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return NotificationModel.model_validate(row)

    async def list_for_user(
        self, user_id: str, unread_only: bool = False, limit: int = 50,
        before: Optional[int] = None, before_id: Optional[str] = None,
        archived: bool = False, db: Optional[AsyncSession] = None,
    ) -> list:
        async with get_async_db_context(db) as db:
            q = select(WorkosNotification).filter_by(user_id=user_id)
            q = q.filter(WorkosNotification.archived == archived)  # noqa: E712
            if unread_only:
                q = q.filter(WorkosNotification.read == False)  # noqa: E712
            if before is not None:
                if before_id is not None:
                    # Compound cursor: strictly-older ms, or same ms with a smaller
                    # id — rows sharing the boundary millisecond are never skipped.
                    q = q.filter(
                        (WorkosNotification.created_at < before)
                        | ((WorkosNotification.created_at == before)
                           & (WorkosNotification.id < before_id))
                    )
                else:
                    q = q.filter(WorkosNotification.created_at < before)
            q = q.order_by(
                WorkosNotification.created_at.desc(), WorkosNotification.id.desc()
            ).limit(limit)
            res = await db.execute(q)
            return [NotificationModel.model_validate(r) for r in res.scalars().all()]

    async def unread_count(self, user_id: str, db: Optional[AsyncSession] = None) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosNotification).filter_by(user_id=user_id, read=False)
            )
            return len(res.scalars().all())

    async def mark_read(
        self, user_id: str, ids: Optional[list] = None, all: bool = False,
        db: Optional[AsyncSession] = None,
    ) -> int:
        async with get_async_db_context(db) as db:
            q = select(WorkosNotification).filter_by(user_id=user_id, read=False)
            if not all:
                q = q.filter(WorkosNotification.id.in_(ids or []))
            res = await db.execute(q)
            rows = res.scalars().all()
            for row in rows:
                row.read = True
            await db.commit()
            return len(rows)

    async def set_archived(
        self, user_id: str, ids: Optional[list] = None, all_read: bool = False,
        archived: bool = True, db: Optional[AsyncSession] = None,
    ) -> int:
        """Archive implies read; unarchive never un-reads."""
        async with get_async_db_context(db) as db:
            q = select(WorkosNotification).filter_by(user_id=user_id)
            if all_read:
                q = q.filter(WorkosNotification.read == True,      # noqa: E712
                             WorkosNotification.archived == False)  # noqa: E712
            else:
                q = q.filter(WorkosNotification.id.in_(ids or []))
            res = await db.execute(q)
            rows = res.scalars().all()
            for row in rows:
                row.archived = archived
                if archived:
                    row.read = True
            await db.commit()
            return len(rows)

    async def counts_for_user(self, user_id: str, db: Optional[AsyncSession] = None) -> dict:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosNotification.type, func.count())
                .where(
                    WorkosNotification.user_id == user_id,
                    WorkosNotification.read == False,      # noqa: E712
                    WorkosNotification.archived == False,  # noqa: E712
                )
                .group_by(WorkosNotification.type)
            )
            by_type = {'assigned': 0, 'subtask_assigned': 0, 'mentioned': 0, 'replied': 0, 'commented': 0,
                       'status_changed': 0}
            by_type.update({t: c for t, c in res.all()})
            return {'unread': sum(by_type.values()), 'by_type': by_type}

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[NotificationModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosNotification).filter_by(id=id))
            row = res.scalars().first()
            return NotificationModel.model_validate(row) if row else None


Attachments = AttachmentsDao()
Notifications = NotificationsDao()

# Visibility predicates (can_see_team / can_see_workspace / can_see_workstream)
# live in open_webui.utils.workos_access — the WorkOS access-policy module.
