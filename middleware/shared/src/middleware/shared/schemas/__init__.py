"""Document schemas for CouchDB storage."""

from enum import Enum


class ArcLifecycleStatus(str, Enum):
    """ARC lifecycle status in the system."""

    ACTIVE = "ACTIVE"  # Normal active state
    PROCESSING = "PROCESSING"  # Git workflow in progress
    MISSING = "MISSING"  # Not seen in recent harvest
    DELETED = "DELETED"  # Soft-deleted (not physically removed)
    INVALID = "INVALID"  # Validation failed


class ArcEventType(str, Enum):
    """Types of events in the ARC event log."""

    # Lifecycle events
    ARC_CREATED = "ARC_CREATED"
    ARC_UPDATED = "ARC_UPDATED"
    ARC_NOT_SEEN = "ARC_NOT_SEEN"
    ARC_MARKED_MISSING = "ARC_MARKED_MISSING"
    ARC_MARKED_DELETED = "ARC_MARKED_DELETED"
    ARC_RESTORED = "ARC_RESTORED"  # Reappeared after being marked missing/deleted

    # Git workflow events
    GIT_QUEUED = "GIT_QUEUED"
    GIT_PROCESSING = "GIT_PROCESSING"
    GIT_PUSH_SUCCESS = "GIT_PUSH_SUCCESS"
    GIT_PUSH_FAILED = "GIT_PUSH_FAILED"

    # Validation events
    VALIDATION_WARNING = "VALIDATION_WARNING"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_SUCCESS = "VALIDATION_SUCCESS"

    # Operator actions
    OPERATOR_NOTE = "OPERATOR_NOTE"
    MANUAL_DELETION = "MANUAL_DELETION"


class HarvestStatus(str, Enum):
    """Harvest run status."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
