from pydantic import BaseModel, constr
from typing import List, Optional, Any # Added Any for TablePreviewResponse

class DataColumnBase(BaseModel):
    column_name: constr(min_length=1, max_length=255)
    data_type: str
    is_nullable: bool = True
    max_length: Optional[int] = None
    description: Optional[str] = None

class DataColumnCreate(DataColumnBase): pass

class DataColumnResponse(DataColumnBase):
    id: int
    table_id: int
    class Config: from_attributes = True

class DataTableBase(BaseModel):
    table_name: constr(min_length=1, max_length=255)
    schema_name: Optional[str] = None
    description: Optional[str] = None
    is_active_for_sync: bool = False

class DataTableCreate(DataTableBase): # Used by CRUD, not directly by sync in this version
    columns: List[DataColumnCreate] = [] # For potential future direct creation

class DataTableResponse(DataTableBase):
    id: int
    datasource_id: int
    columns: List[DataColumnResponse] = []
    class Config: from_attributes = True

class MetadataSyncRequest(BaseModel):
    datasource_id: int

class MetadataSyncResult(BaseModel):
    datasource_id: int
    tables_discovered: int
    columns_discovered: int
    message: str

# New Schemas for Epic 4
class TableActivationRequest(BaseModel):
    is_active_for_sync: bool

class TablePreviewResponse(BaseModel):
    table_name: str
    schema_name: Optional[str] = None
    columns: List[str]
    rows: List[Dict[str, Any]] # Using Dict[str, Any] for rows
    row_count: int
    is_preview_limited: bool
    limit: int
