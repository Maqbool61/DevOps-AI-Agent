"""Cloud-agnostic object storage for audit logs, incidents, and org documentation."""

from storage.factory import get_storage

__all__ = ["get_storage"]
