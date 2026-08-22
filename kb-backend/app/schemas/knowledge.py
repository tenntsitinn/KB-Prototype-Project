from datetime import datetime
from pydantic import BaseModel, Field


# --- Knowledge Unit ---

class KnowledgeUnitCreate(BaseModel):
    title: str
    content: str = ""
    summary: str = ""
    category: str = ""
    source_file_name: str = ""
    file_type: str = ""
    file_size: int = 0
    file_md5: str = ""
    minio_path: str = ""
    creator_id: str = ""


class KnowledgeUnitUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    category: str | None = None


class KnowledgeUnitOut(BaseModel):
    id: str
    unit_code: str
    title: str
    content: str
    summary: str
    category: str
    source_file_name: str
    file_type: str
    file_size: int
    status: str
    creator_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Permission ---

class PermissionCreate(BaseModel):
    target_type: str = Field(..., pattern="^(global|department|role|user)$")
    target_id: str = ""


class PermissionBatchCreate(BaseModel):
    permissions: list[PermissionCreate]


class PermissionOut(BaseModel):
    id: str
    unit_id: str
    target_type: str
    target_id: str

    class Config:
        from_attributes = True


# --- Check Permissions ---

class CheckPermissionsRequest(BaseModel):
    user_id: str
    unit_ids: list[str]


class CheckPermissionsResponse(BaseModel):
    authorized_unit_ids: list[str]
    unauthorized_unit_ids: list[str]


# --- Import ---

class ImportItem(BaseModel):
    filename: str
    task_id: str
    unit_id: str
    status: str
    error: str = ""


class ImportResponse(BaseModel):
    task_id: str
    unit_id: str
    status: str


class BatchImportResponse(BaseModel):
    total: int
    items: list[ImportItem]


class ImportStatusResponse(BaseModel):
    task_id: str
    unit_id: str
    status: str  # pending | processing | completed | failed
    progress: int = 0  # 0-100
    error: str = ""