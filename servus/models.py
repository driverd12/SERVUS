from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import date

class UserProfile(BaseModel):
    # --- RAW DATA FIELDS (Matches your JSON/Rippling) ---
    first_name: str
    last_name: str
    work_email: EmailStr  # Pydantic will validate this is an email
    personal_email: Optional[EmailStr] = None
    
    department: str
    title: Optional[str] = None
    manager_email: Optional[EmailStr] = None
    
    # New Fields for Badge Printing
    preferred_first_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    
    # "Full-Time", "Contractor", "Intern"
    employment_type: str 
    
    start_date: Optional[str] = None
    location: Optional[str] = "US"

    # --- HELPER PROPERTIES (The "Bridge") ---
    
    @property
    def email(self) -> str:
        """Standard alias for work_email"""
        return self.work_email

    @property
    def user_type(self) -> str:
        """
        Translates raw employment_type into SERVUS codes:
        'Full-Time' -> 'FTE'
        'Contractor' -> 'CON'
        'Intern'     -> 'INT'
        """
        raw = self.employment_type.lower()
        if "contractor" in raw:
            return "CON"
        elif "intern" in raw:
            return "INT"
        else:
            return "FTE" # Default to FTE for "Full-Time" or others

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    # --- VALIDATORS ---
    
    @field_validator('department')
    def validate_dept(cls, v):
        return v.strip()  # Clean up whitespace
