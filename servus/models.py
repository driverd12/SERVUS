from __future__ import annotations
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field, EmailStr

class WorkerType(str, Enum):
    FTE = "FTE"
    CON = "CON"
    INT = "INT"
    MRG = "MRG"
    SUP = "SUP"

class UserProfile(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    preferred_name: str | None = None

    work_email: EmailStr
    personal_email: EmailStr | None = None

    start_date: date | None = None
    worker_type: WorkerType = WorkerType.FTE

    department: str | None = None
    department_number: str | None = None
    manager_email: EmailStr | None = None
    location: str | None = None

    is_service_account: bool = False
    needs_mac: bool = False

    @property
    def username(self) -> str:
        return str(self.work_email).split("@", 1)[0]

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
