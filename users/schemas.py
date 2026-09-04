"""
User API schemas.
"""
from datetime import datetime
from typing import Optional

from ninja import Schema
from pydantic import BaseModel


class UserOut(BaseModel):
    """Schema for user output."""
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    
    class Config:
        from_attributes = True


class ClientProfileOut(BaseModel):
    """Schema for client profile output."""
    id: int
    phone: str
    address: str
    city: str
    country: str
    postal_code: str
    id_number: str
    user: UserOut
    
    class Config:
        from_attributes = True


class ClientProfileIn(BaseModel):
    """Schema for client profile input."""
    first_name: str
    last_name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    address: Optional[str] = ""
    city: Optional[str] = ""
    postal_code: Optional[str] = ""
    id_number: Optional[str] = ""


class ClientProfileUpdate(BaseModel):
    """Schema for client profile update."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    id_number: Optional[str] = None


class ProviderProfileOut(BaseModel):
    """Schema for provider profile output."""
    id: int
    phone: str
    address: str
    city: str
    country: str
    postal_code: str
    company_name: str
    tax_id: str
    user: UserOut
    
    class Config:
        from_attributes = True


class ProviderProfileIn(BaseModel):
    """Schema for provider profile input."""
    first_name: str
    last_name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    address: Optional[str] = ""
    city: Optional[str] = ""
    postal_code: Optional[str] = ""
    company_name: Optional[str] = ""
    tax_id: Optional[str] = ""


class LoginIn(Schema):
    username: str
    password: str


class AccountProfileUpdateIn(Schema):
    first_name: str = ''
    last_name: str = ''
    email: str = ''
    phone: str = ''


class PasswordChangeIn(Schema):
    current_password: str
    new_password: str


class AdminUserOut(Schema):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    is_active: bool
    is_staff: bool
    role: str
    last_login: Optional[datetime] = None
    date_joined: datetime


class AdminUserIn(Schema):
    username: str
    password: str
    first_name: str = ''
    last_name: str = ''
    email: str = ''
    role: str = ''


class AdminUserUpdate(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    password: Optional[str] = None


class MeOut(Schema):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    role: Optional[str] = None
    is_staff: bool
    phone: str = ''
    date_joined: datetime
    last_login: Optional[datetime] = None

    @staticmethod
    def from_user(user):
        from users.permissions import get_user_role

        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": get_user_role(user),
            "is_staff": user.is_staff,
            "phone": getattr(getattr(user, 'staff_profile', None), 'phone', ''),
            "date_joined": user.date_joined,
            "last_login": user.last_login,
        }


class ProviderProfileUpdate(BaseModel):
    """Schema for provider profile update."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
