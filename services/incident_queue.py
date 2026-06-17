"""
Durable incident queue backed by cloud storage.
Survives process restarts — pending incidents are re-processed on startup.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import structlog

from storage.base import StorageProvider
from storage.factory import get_storage

log = structlog.get_logger()

QUEUE_PENDING = "pending"
QUEUE_PROCESSING = "processing"
QUEUE_COMPLETED = "completed"
QUEUE_FAILED = "failed"


class IncidentQueue:
    def __init__(self, storage: Optional[StorageProvider] = None):
        self.storage = storage or get_storage()

    def enqueue(self, org_id: str, context: dict, incident_id: Optional[str] = None) -> str:
        incident_id = incident_id or f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        entry = {
            "incident_id": incident_id,
            "org_id": org_id,
            "context": context,
            "status": QUEUE_PENDING,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "attempts": 0,
        }
        key = self.storage.queue_key(org_id, QUEUE_PENDING, incident_id)
        self.storage.put_json(key, entry)
        log.info("Incident enqueued", incident_id=incident_id, org_id=org_id)
        return incident_id

    def claim_next(self, org_id: str) -> Optional[Dict[str, Any]]:
        prefix = self.storage.org_prefix(org_id, "queue", QUEUE_PENDING)
        keys = self.storage.list_keys(prefix)
        if not keys:
            return None

        key = keys[0]
        entry = self.storage.get_json(key)
        if not entry:
            return None

        incident_id = entry["incident_id"]
        entry["status"] = QUEUE_PROCESSING
        entry["claimed_at"] = datetime.now(timezone.utc).isoformat()
        entry["attempts"] = entry.get("attempts", 0) + 1

        proc_key = self.storage.queue_key(org_id, QUEUE_PROCESSING, incident_id)
        self.storage.put_json(proc_key, entry)
        self.storage.delete(key)
        return entry

    def recover_stale_processing(self, org_id: str) -> int:
        """Move processing items back to pending (e.g. after crash mid-run)."""
        prefix = self.storage.org_prefix(org_id, "queue", QUEUE_PROCESSING)
        recovered = 0
        for key in self.storage.list_keys(prefix):
            entry = self.storage.get_json(key)
            if not entry:
                continue
            incident_id = entry["incident_id"]
            entry["status"] = QUEUE_PENDING
            entry["recovered_at"] = datetime.now(timezone.utc).isoformat()
            pending_key = self.storage.queue_key(org_id, QUEUE_PENDING, incident_id)
            self.storage.put_json(pending_key, entry)
            self.storage.delete(key)
            recovered += 1
            log.warning("Recovered stale incident", incident_id=incident_id, org_id=org_id)
        return recovered

    def mark_completed(self, org_id: str, incident_id: str, result: dict):
        entry = self._get_processing(org_id, incident_id) or {"incident_id": incident_id, "org_id": org_id}
        entry["status"] = QUEUE_COMPLETED
        entry["completed_at"] = datetime.now(timezone.utc).isoformat()
        entry["result_summary"] = {
            "resolved": result.get("resolved"),
            "steps": result.get("steps"),
        }
        key = self.storage.queue_key(org_id, QUEUE_COMPLETED, incident_id)
        self.storage.put_json(key, entry)
        self._delete_processing(org_id, incident_id)

    def mark_failed(self, org_id: str, incident_id: str, error: str):
        entry = self._get_processing(org_id, incident_id) or {"incident_id": incident_id, "org_id": org_id}
        entry["status"] = QUEUE_FAILED
        entry["failed_at"] = datetime.now(timezone.utc).isoformat()
        entry["error"] = error
        key = self.storage.queue_key(org_id, QUEUE_FAILED, incident_id)
        self.storage.put_json(key, entry)
        self._delete_processing(org_id, incident_id)

    def list_pending_org_ids(self) -> List[str]:
        """Scan all orgs with pending or processing items."""
        orgs = set()
        org_id = os.getenv("ORG_ID", "default")
        orgs.add(org_id)
        extra = os.getenv("ORG_IDS", "")
        for o in extra.split(","):
            o = o.strip()
            if o:
                orgs.add(o)
        return list(orgs)

    def _get_processing(self, org_id: str, incident_id: str) -> Optional[dict]:
        return self.storage.get_json(self.storage.queue_key(org_id, QUEUE_PROCESSING, incident_id))

    def _delete_processing(self, org_id: str, incident_id: str):
        self.storage.delete(self.storage.queue_key(org_id, QUEUE_PROCESSING, incident_id))
