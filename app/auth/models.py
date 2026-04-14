from dataclasses import dataclass
from typing import Optional


@dataclass
class UserRecord:
    id: Optional[int]
    email: str
    created_at: Optional[str]
    last_login_at: Optional[str]


@dataclass
class OTPRecord:
    id: Optional[int]
    email: str
    code: str
    expires_at: str
    used: int
    created_at: Optional[str]


@dataclass
class SessionRecord:
    id: Optional[int]
    user_id: int
    email: str
    token: str
    expires_at: str
    created_at: Optional[str]
