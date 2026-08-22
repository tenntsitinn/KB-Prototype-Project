from datetime import datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    department_id: str
    is_superuser: bool
    roles: list[str]
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_info: UserInfo | None = None
    permissions: list[str] = []


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""
    email: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""
    email: str = ""


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    department_id: str
    status: str
    is_superuser: bool
    roles: list[str]
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


class RoleAssignRequest(BaseModel):
    role_code: str


class RoleResponse(BaseModel):
    id: str
    role_name: str
    role_code: str
    description: str


class DepartmentResponse(BaseModel):
    id: str
    parent_id: str | None
    name: str
    leader_id: str
    sort_order: int


# --- User Edit ---

class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None
    department_id: str | None = None
    status: str | None = None


# --- Role CRUD ---

class RoleCreateRequest(BaseModel):
    role_name: str
    role_code: str
    description: str = ""


class RoleUpdateRequest(BaseModel):
    role_name: str | None = None
    description: str | None = None


class RoleDetailResponse(BaseModel):
    id: str
    role_name: str
    role_code: str
    description: str
    permissions: list[str]  # permission_code 列表


class RolePermissionAssignRequest(BaseModel):
    permissions: list[str]  # permission_code 列表


# --- Department CRUD ---

class DepartmentCreateRequest(BaseModel):
    parent_id: str | None = None
    name: str
    leader_id: str = ""
    sort_order: int = 0


class DepartmentUpdateRequest(BaseModel):
    parent_id: str | None = None
    name: str | None = None
    leader_id: str | None = None
    sort_order: int | None = None


# --- Password Change ---

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


# --- Profile Update ---

class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None