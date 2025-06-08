from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.crud import crud_datasource
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate, DataSourceResponse, DataSourceBase
from app.models.datasource import DataSource as DBDataSourceModel # Alias to avoid naming conflict with schema
from app.models.sync import SyncType # Added for SyncType enum
from app.utils.sqlserver_utils import test_sqlserver_connection
from app.tasks.sync_tasks import run_sync_for_datasource_task # Import Celery task
# from app.core.auth import get_current_active_user # Placeholder for future authentication
# from app.models.user import User # For current_user type hint

router = APIRouter()

@router.post("/", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
def create_new_datasource(datasource_in: DataSourceCreate, db: Session = Depends(get_db)):
    # current_user: User = Depends(get_current_active_user) # Uncomment for auth
    if not test_sqlserver_connection(ds_details=datasource_in, password_override=datasource_in.db_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection test failed for the provided SQL Server details.")
    created_ds = crud_datasource.create_datasource(db=db, datasource=datasource_in)
    return created_ds

@router.get("/", response_model=List[DataSourceResponse])
def read_all_datasources(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # current_user: User = Depends(get_current_active_user) # Uncomment for auth
    datasources = crud_datasource.get_datasources(db=db, skip=skip, limit=limit)
    return datasources

@router.get("/{datasource_id}", response_model=DataSourceResponse)
def read_single_datasource(datasource_id: int, db: Session = Depends(get_db)):
    # current_user: User = Depends(get_current_active_user) # Uncomment for auth
    db_datasource = crud_datasource.get_datasource(db=db, datasource_id=datasource_id)
    if db_datasource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    return db_datasource

@router.put("/{datasource_id}", response_model=DataSourceResponse)
def update_existing_datasource(datasource_id: int, datasource_in: DataSourceUpdate, db: Session = Depends(get_db)):
    # current_user: User = Depends(get_current_active_user) # Uncomment for auth
    db_datasource_model = crud_datasource.get_datasource(db=db, datasource_id=datasource_id)
    if db_datasource_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

    # Determine if connection-related fields are being updated
    connection_fields_updated = any(
        getattr(datasource_in, field) is not None
        for field in ["db_host", "db_port", "db_name", "db_username", "db_password", "type"]
        if hasattr(datasource_in, field) # Check if field exists in Optional schema
    )

    if connection_fields_updated:
        # Use new password if provided, else the existing one from the database model
        password_for_test = datasource_in.db_password if datasource_in.db_password is not None else db_datasource_model.db_password

        # Create a temporary schema instance with merged data for testing
        # Start with current data from the model, then update with incoming changes
        current_data_for_test = DataSourceBase(
            name=datasource_in.name if datasource_in.name is not None else db_datasource_model.name,
            type=datasource_in.type if datasource_in.type is not None else db_datasource_model.type,
            db_host=datasource_in.db_host if datasource_in.db_host is not None else db_datasource_model.db_host,
            db_port=datasource_in.db_port if datasource_in.db_port is not None else db_datasource_model.db_port,
            db_name=datasource_in.db_name if datasource_in.db_name is not None else db_datasource_model.db_name,
            db_username=datasource_in.db_username if datasource_in.db_username is not None else db_datasource_model.db_username
        )

        if not test_sqlserver_connection(ds_details=current_data_for_test, password_override=password_for_test):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection test failed for the updated SQL Server details.")

    updated_ds = crud_datasource.update_datasource(db=db, db_obj=db_datasource_model, obj_in=datasource_in)
    if not updated_ds: # Should not happen if db_datasource_model was found
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update data source.")
    return updated_ds


@router.delete("/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_datasource(datasource_id: int, db: Session = Depends(get_db)):
    # current_user: User = Depends(get_current_active_user) # Uncomment for auth
    deleted_ds = crud_datasource.delete_datasource(db=db, datasource_id=datasource_id)
    if deleted_ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    # No content is returned for 204, so just return nothing or Response(status_code=204)
    return None

@router.post("/test_connection", status_code=status.HTTP_200_OK)
def test_datasource_connection_endpoint(datasource_test_details: DataSourceCreate): # Use Create schema as it includes password
    # current_user: User = Depends(get_current_active_user) # Uncomment for auth
    if not test_sqlserver_connection(ds_details=datasource_test_details, password_override=datasource_test_details.db_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection test failed.")
    return {"message": "Connection test successful"}


@router.post("/{datasource_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_datasource_sync(datasource_id: int, db: Session = Depends(get_db)):
    # Optional: Add current_user dependency for authorization if needed
    # current_user: User = Depends(get_current_active_user)

    # Verify datasource exists
    db_datasource = crud_datasource.get_datasource(db=db, datasource_id=datasource_id)
    if db_datasource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

    # Dispatch the Celery task
    # .delay() is a shortcut for .apply_async()
    task = run_sync_for_datasource_task.delay(datasource_id=datasource_id, sync_type_value=SyncType.MANUAL.value)

    # Return the task ID so the client can (optionally) monitor its status
    return {"message": "Data synchronization task accepted.", "task_id": task.id}
