from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user")
    app_sessions: Mapped[list["AppSession"]] = relationship(back_populates="user")
    oauth_connections: Mapped[list["OAuthConnection"]] = relationship(back_populates="user")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="auth_sessions")


class AppSession(Base):
    __tablename__ = "app_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    user: Mapped[User] = relationship(back_populates="app_sessions")


class OAuthConnection(Base):
    __tablename__ = "oauth_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_oauth_connection_user_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    access_token: Mapped[str] = mapped_column(Text, default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    account_email: Mapped[str] = mapped_column(String(320), default="")
    account_name: Mapped[str] = mapped_column(String(255), default="")
    cloud_id: Mapped[str] = mapped_column(String(255), default="")
    cloud_name: Mapped[str] = mapped_column(String(255), default="")
    cloud_url: Mapped[str] = mapped_column(String(1024), default="")
    account_id: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    user: Mapped[User] = relationship(back_populates="oauth_connections")


class SlackJiraRequest(Base):
    __tablename__ = "slack_jira_requests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "channel_id", "thread_ts", name="uq_slack_jira_request_thread"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(120), index=True)
    channel_id: Mapped[str] = mapped_column(String(120), index=True)
    thread_ts: Mapped[str] = mapped_column(String(64), index=True)
    root_message_ts: Mapped[str] = mapped_column(String(64), default="")
    requester_slack_id: Mapped[str] = mapped_column(String(120), default="")
    requester_name: Mapped[str] = mapped_column(String(255), default="")
    project_key: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(50), default="collecting", index=True)
    summary: Mapped[str] = mapped_column(String(255), default="")
    background: Mapped[str] = mapped_column(Text, default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    device: Mapped[str] = mapped_column(String(64), default="")
    priority: Mapped[str] = mapped_column(String(32), default="")
    transcript: Mapped[str] = mapped_column(Text, default="")
    proposal_json: Mapped[str] = mapped_column(Text, default="")
    confluence_draft: Mapped[str] = mapped_column(Text, default="")
    approval_notes: Mapped[str] = mapped_column(Text, default="")
    approved_by_slack_id: Mapped[str] = mapped_column(String(120), default="")
    approved_by_name: Mapped[str] = mapped_column(String(255), default="")
    created_ticket_keys_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class SlackEventDelivery(Base):
    __tablename__ = "slack_event_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
