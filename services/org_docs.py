"""
Org-scoped documentation storage — runbooks, policies, playbooks.
Loaded into agent context to ground responses in org-specific knowledge.
"""
from __future__ import annotations

import os
from typing import List, Optional

import structlog

from services.pii_scrubber import scrub_text
from storage.base import StorageProvider
from storage.factory import get_storage

log = structlog.get_logger()

ALLOWED_DOC_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json", ".rst"}
MAX_DOC_CONTEXT_CHARS = int(os.getenv("MAX_DOC_CONTEXT_CHARS", "12000"))
MAX_DOCS_IN_CONTEXT = int(os.getenv("MAX_DOCS_IN_CONTEXT", "5"))


class OrgDocs:
    def __init__(self, storage: Optional[StorageProvider] = None):
        self.storage = storage or get_storage()

    def upload(self, org_id: str, doc_path: str, content: str, content_type: str = "text/markdown") -> str:
        safe_path = _normalize_doc_path(doc_path)
        key = self.storage.doc_key(org_id, safe_path)
        self.storage.put_bytes(key, content.encode("utf-8"), content_type)
        log.info("Org doc uploaded", org_id=org_id, path=safe_path)
        return key

    def get(self, org_id: str, doc_path: str) -> Optional[str]:
        key = self.storage.doc_key(org_id, _normalize_doc_path(doc_path))
        raw = self.storage.get_bytes(key)
        return raw.decode("utf-8") if raw else None

    def list_docs(self, org_id: str, prefix: str = "") -> List[dict]:
        base = self.storage.org_prefix(org_id, "docs")
        if prefix:
            base = f"{base}/{_normalize_doc_path(prefix).rstrip('/')}"
        keys = self.storage.list_keys(base)
        docs = []
        org_prefix_len = len(self.storage.org_prefix(org_id, "docs")) + 1
        for key in keys:
            rel = key[org_prefix_len:] if len(key) > org_prefix_len else key
            docs.append({"path": rel, "key": key})
        return docs

    def delete(self, org_id: str, doc_path: str) -> bool:
        return self.storage.delete(self.storage.doc_key(org_id, _normalize_doc_path(doc_path)))

    def get_context_for_agent(self, org_id: str, issue_type: Optional[str] = None) -> str:
        """
        Build a documentation context block for the agent.
        Prioritizes runbooks matching issue_type, then general docs.
        """
        all_docs = self.list_docs(org_id)
        if not all_docs:
            return ""

        prioritized = []
        general = []
        for doc in all_docs:
            path = doc["path"].lower()
            if issue_type and issue_type in path:
                prioritized.append(doc)
            elif any(p in path for p in ("runbook", "playbook", "policy", "readme", "guide")):
                general.append(doc)
            else:
                general.append(doc)

        selected = (prioritized + general)[:MAX_DOCS_IN_CONTEXT]
        parts = []
        total = 0
        for doc in selected:
            content = self.get(org_id, doc["path"])
            if not content:
                continue
            content = scrub_text(content)
            header = f"### Org doc: {doc['path']}\n"
            block = header + content
            if total + len(block) > MAX_DOC_CONTEXT_CHARS:
                remaining = MAX_DOC_CONTEXT_CHARS - total
                if remaining > 200:
                    parts.append(block[:remaining] + "\n...[truncated]")
                break
            parts.append(block)
            total += len(block)

        if not parts:
            return ""
        return "## Organization documentation (use as authoritative reference)\n\n" + "\n\n".join(parts)


def _normalize_doc_path(path: str) -> str:
    cleaned = path.strip().lstrip("/").replace("..", "")
    if not cleaned:
        raise ValueError("doc_path cannot be empty")
    ext = os.path.splitext(cleaned)[1].lower()
    if ext and ext not in ALLOWED_DOC_EXTENSIONS:
        raise ValueError(f"Unsupported doc extension {ext}. Allowed: {ALLOWED_DOC_EXTENSIONS}")
    return cleaned
