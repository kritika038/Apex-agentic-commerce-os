from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import List

class Permission(TimeStampedBase):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    description: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, default="commerce")

    agent_associations: Mapped[List["AgentPermission"]] = relationship("AgentPermission", back_populates="permission", cascade="all, delete-orphan")

class Agent(TimeStampedBase):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String, default="1.0")
    model: Mapped[str] = mapped_column(String, default="default-model")
    status: Mapped[str] = mapped_column(String, default="active")

    permission_associations: Mapped[List["AgentPermission"]] = relationship("AgentPermission", back_populates="agent", cascade="all, delete-orphan")
    merchant = relationship("Merchant")

    @property
    def permission_names(self) -> List[str]:
        return [assoc.permission.name for assoc in self.permission_associations if assoc.permission]

class AgentPermission(TimeStampedBase):
    __tablename__ = "agent_permissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id"), index=True)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="permission_associations")
    permission: Mapped["Permission"] = relationship("Permission", back_populates="agent_associations")
