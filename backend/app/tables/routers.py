import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

# Assuming auth dependencies and models are correctly pathed
from app.routers.auth import get_current_active_user
from app.models import user as user_model
from app.models.metadata import DataTable # Using DataTable as per current models

# Schemas for this router
from app.schemas import datasource as datasource_schema # May not be needed directly
from app.schemas import metadata as metadata_schema # For responses if not using table-specific ones
from app.schemas import sync as sync_schema # For the new incremental config endpoint

# Services
# Need to ensure services are created/available for these.
# For Epic 4, there would have been a tables_service.
# For Epic 5, the incremental config might call data_sync_service.
# Placeholder/TODO: These service imports will need actual files and functions.
# For now, to make the file syntactically valid, we might need to define dummy services
# or ensure the actual service files (e.g. tables_service.py) are created in subsequent steps.

# Mocking service calls for now if actual service files are not yet (re)created:
class MockTablesService:
    def activate_deactivate_tables(self, db: Session, table_metadata_ids: List[int], activate: bool, current_user: user_model.User):
        logger.warning("MockTablesService.activate_deactivate_tables called. Implement actual service.")
        return {"success": True, "message": "Mocked activation/deactivation", "details": []}
    def get_table_data_preview_service(self, db: Session, table_metadata_id: int, current_user: user_model.User, limit: int):
        logger.warning("MockTablesService.get_table_data_preview_service called. Implement actual service.")
        # Must match TableDataPreviewResponse structure from app.schemas.metadata (or a new tables_schema)
        return {
            "columns": ["mock_col1", "mock_col2"], "rows": [["mock_val1", "mock_val2"]], "row_count": 1,
            "total_source_table_rows": 1, "source_info": "Mock Preview", "error_message": None,
            "table_metadata_id": table_metadata_id, "data_source_id": 0
        }
tables_service = MockTablesService() # Replace with actual service import

from app.data_sync.service import update_table_incremental_config # Assuming this service is created

# DB session dependency
from app.core.database import SessionLocal
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tables",
    tags=["Table Management"],
    dependencies=[Depends(get_current_active_user)]
)

# Schemas specifically for this router's direct request/response if not using common ones
# This is from my Epic 4 plan - TableActivationRequest, TableActivationResponse, TableDataPreviewResponse
# Assuming these would be in app.schemas.table (new file) or app.schemas.metadata
# For now, using placeholders if not defined in existing schema files.
class TableActivationRequest(BaseModel): # from pydantic import BaseModel
    table_ids: List[int]
    activate: bool

class TableActivationDetail(BaseModel):
    table_id: int
    status: str
    message: Optional[str] = None

class TableActivationResponse(BaseModel):
    success: bool
    message: str
    details: List[TableActivationDetail] = []

class TableDataPreviewResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    total_source_table_rows: Optional[int] = None
    source_info: str
    error_message: Optional[str] = None
    table_metadata_id: int
    data_source_id: int


@router.post("/activate", response_model=TableActivationResponse)
def activate_tables_endpoint(
    request: TableActivationRequest, # Using locally defined placeholder
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_active_user)
):
    logger.info(f"User {current_user.email} requested to {'activate' if request.activate else 'deactivate'} tables: {request.table_ids}")
    # This should call a service function, e.g., from a (to be created) tables_service.py
    # For now, using the mock.
    response_data = tables_service.activate_deactivate_tables(
        db=db, table_metadata_ids=request.table_ids, activate=request.activate, current_user=current_user
    )
    return TableActivationResponse(**response_data)


@router.get("/{datatable_id}/preview", response_model=TableDataPreviewResponse) # Changed to datatable_id
def get_table_preview_endpoint(
    datatable_id: int, # Changed from table_metadata_id
    limit: int = Query(50, ge=1, le=1000, description="Number of rows to preview"),
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_active_user)
):
    logger.info(f"User {current_user.email} requested preview for DataTable ID {datatable_id} with limit {limit}.")
    # This should call a service function, e.g., from tables_service.py
    preview_response_data = tables_service.get_table_data_preview_service(
        db=db, table_metadata_id=datatable_id, current_user=current_user, limit=limit
    )
    response_obj = TableDataPreviewResponse(**preview_response_data)
    if response_obj.error_message and response_obj.source_info == "Error": # Check for critical errors
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in response_obj.error_message else status.HTTP_400_BAD_REQUEST,
            detail=response_obj.error_message
        )
    return response_obj

# New endpoint for Epic 5 (incremental config)
@router.put(
    "/{datatable_id}/incremental-config",
    response_model=sync_schema.TableIncrementalConfigRequest # Response can be the same as request for confirmation
)
def configure_table_incremental_sync(
    datatable_id: int, # Changed from table_metadata_id
    config_request: sync_schema.TableIncrementalConfigRequest,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_active_user)
):
    logger.info(f"User {current_user.email} configuring incremental sync for DataTable ID {datatable_id} with column '{config_request.incremental_sync_column_name}' type '{config_request.incremental_sync_column_type}'.")
    try:
        # Assuming update_table_incremental_config is in data_sync.service
        updated_table_meta = update_table_incremental_config( # Direct call to service function
            db=db,
            datatable_id=datatable_id, # Pass datatable_id
            config_request=config_request,
            current_user=current_user
        )
        # Return the configuration that was set
        return sync_schema.TableIncrementalConfigRequest(
            incremental_sync_column_name=updated_table_meta.incremental_sync_column_name,
            incremental_sync_column_type=updated_table_meta.incremental_sync_column_type
        )
    except ValueError as ve:
        logger.error(f"ValueError configuring incremental sync for DataTable ID {datatable_id} by user {current_user.email}: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error configuring incremental sync for DataTable ID {datatable_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to configure incremental sync.")
