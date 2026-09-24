from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class GithubLinkResponse(BaseModel):
    id: UUID
    task_id: UUID
    kind: str  # "commit" or "pull_request"
    ref: str  # commit sha, or pull-request number
    url: str
    title: str
    author_login: Optional[str] = None
    state: Optional[str] = None  # open / merged / closed, for a pull request
    authored_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GithubSyncResult(BaseModel):
    """What one sync read and what it changed."""

    repository: str
    commits_read: int
    commits_matched: int
    pull_requests_read: int
    pull_requests_matched: int
    links_added: int
    tasks_moved: list[dict]


class GithubWebhookSecret(BaseModel):
    """Shown once, when it is made: what to paste into GitHub's webhook settings."""

    secret: str
    path: str  # append to your public API URL to get the payload URL
    events: list[str]
    content_type: str = "application/json"


class GithubWebhookReceipt(BaseModel):
    """What one webhook call did."""

    event: str
    applied: bool
    links_added: int = 0
    tasks_moved: list[dict] = []
    detail: str = ""
