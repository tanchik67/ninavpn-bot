from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    SUPPORT = "support"
    ADMIN = "admin"


class SubscriptionStatus(str, Enum):
    TRIAL = "trial"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REFUNDED = "refunded"


class ProvisionJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SupportTicketStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"


class NotificationChannel(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    PUSH = "push"


class NotificationOutboxStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
