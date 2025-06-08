from pydantic import BaseModel, constr, Field
from typing import Optional
from app.models.datasource import DBDataSourceType # Import from models
from datetime import datetime

class DataSourceBase(BaseModel):
    name: constr(min_length=1, max_length=255)
    type: DBDataSourceType = DBDataSourceType.SQLSERVER
    db_host: constr(min_length=1, max_length=255)
    db_port: int = Field(gt=0, le=65535)
    db_name: constr(min_length=1, max_length=255)
    db_username: constr(min_length=1, max_length=255)

class DataSourceCreate(DataSourceBase):
    db_password: str

class DataSourceUpdate(DataSourceBase):
    name: Optional[constr(min_length=1, max_length=255)] = None
    type: Optional[DBDataSourceType] = None
    db_host: Optional[constr(min_length=1, max_length=255)] = None
    db_port: Optional[int] = Field(default=None, gt=0, le=65535)
    db_name: Optional[constr(min_length=1, max_length=255)] = None
    db_username: Optional[constr(min_length=1, max_length=255)] = None
    db_password: Optional[str] = None

class DataSourceResponse(DataSourceBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True # Pydantic V2+
