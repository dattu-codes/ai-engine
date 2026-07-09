from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.auth.database.connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    last_active = Column(DateTime, nullable=True)
    
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

    # GitHub Integration
    github_id = Column(String(255), unique=True, index=True, nullable=True)
    github_username = Column(String(255), nullable=True)
    github_token = Column(String(512), nullable=True)
    github_connected = Column(Boolean, default=False, nullable=False)

    # Stripe Billing
    stripe_customer_id = Column(String(255), unique=True, index=True, nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    billing_plan = Column(String(50), default="Free", nullable=False)
    billing_status = Column(String(50), default="active", nullable=False)

    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    notification_preferences = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    
    # Refresh Token Rotation self-referential relationship
    replaced_by_token_id = Column(Integer, ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True)
    
    user_agent = Column(String(512), nullable=True)
    ip_address = Column(String(100), nullable=True)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    user_agent = Column(String(512), nullable=True)
    ip_address = Column(String(100), nullable=True)
    
    login_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    logout_time = Column(DateTime, nullable=True)
    last_active_time = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    email_analysis_completed = Column(Boolean, default=True, nullable=False)
    email_fix_completed = Column(Boolean, default=True, nullable=False)
    email_tests_completed = Column(Boolean, default=True, nullable=False)
    email_repo_synced = Column(Boolean, default=True, nullable=False)
    email_invitation_accepted = Column(Boolean, default=True, nullable=False)
    email_deployment_completed = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="notification_preferences")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="api_keys")

