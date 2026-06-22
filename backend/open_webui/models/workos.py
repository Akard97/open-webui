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
)
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


def _now() -> int:
    return int(time.time_ns())


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


class WorkosTeamMember(Base):
    __tablename__ = 'workos_team_member'
    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='uq_workos_team_member'),)

    id = Column(Text, primary_key=True, unique=True)
    team_id = Column(Text)
    user_id = Column(Text)
    role = Column(Text)  # owner | admin | member
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
    role = Column(Text)  # admin | member
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
