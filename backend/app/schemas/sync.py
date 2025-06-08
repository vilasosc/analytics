from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
# Assuming SyncStatus and SyncType enums are in app.models.sync
from app.models.sync import SyncStatus, SyncType
# For DataTableResponse, if we want to embed it in SyncJobTableDetailResponse
# from app.schemas.metadata import DataTableResponse

# --- SyncJobTableDetail Schemas ---
class SyncJobTableDetailBase(BaseModel):
    datatable_id: int # ID of the table from our metadata store
    status: SyncStatus = SyncStatus.PENDING
    rows_processed: Optional[int] = 0
    error_message: Optional[str] = None
    # table: Optional[DataTableResponse] = None # Optional: embed full table details

class SyncJobTableDetailCreate(SyncJobTableDetailBase):
    # sync_job_id will be set by the system when creating within a job
    pass

class SyncJobTableDetailResponse(SyncJobTableDetailBase):
    id: int
    sync_job_id: int
    start_time: datetime
    end_time: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- SyncJob Schemas ---
class SyncJobBase(BaseModel):
    datasource_id: int
    sync_type: SyncType = SyncType.MANUAL
    status: SyncStatus = SyncStatus.PENDING
    message: Optional[str] = None

class SyncJobCreate(SyncJobBase):
    # All fields are typically set by the system or derived when a sync is triggered.
    # This schema might be minimal if job creation is mostly internal.
    # If user can specify type or other params on creation, add them here.
    pass

class SyncJobResponse(SyncJobBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    details: List[SyncJobTableDetailResponse] = [] # Embed details in the job response

    class Config:
        from_attributes = True

# Schema for triggering a sync, might be very simple
class TriggerSyncRequest(BaseModel):
    datasource_id: int
    # Potentially add sync_type if user can choose, or other params
    # sync_type: Optional[SyncType] = SyncType.MANUAL
