import logging
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models import user as user_model # For current_user type hint
from app.models.datasource import DataSource
from app.models.metadata import DataTable
from app.models.sync import SyncJob, SyncJobTableDetail, ExistingSyncStatus, ExistingSyncType, TableDetailStatus
from app.schemas import sync as sync_schema # Pydantic schemas for data_sync
from app.data_sync.tasks import main_data_sync_job_task # Celery task
from app.crud import crud_datasource # To get DataSource
from app.core.config import settings # For DATASOURCE_ENCRYPTION_KEY if needed by tasks directly

logger = logging.getLogger(__name__)

def trigger_data_sync_job(
    db: Session,
    request: sync_schema.DataSyncTriggerRequest,
    current_user: user_model.User
) -> sync_schema.DataSyncJobResponse:

    data_source = crud_datasource.get_datasource(db=db, id=request.datasource_id, user_id=current_user.id)
    if not data_source:
        raise ValueError(f"Data source ID {request.datasource_id} not found or access denied.")

    new_sync_job = SyncJob(
        datasource_id=request.datasource_id,
        triggered_by_user_id=current_user.id,
        sync_type=request.sync_type, # e.g. MANUAL
        actual_sync_mode=request.actual_sync_mode, # 'full' or 'incremental'
        status=ExistingSyncStatus.PENDING,
        start_time=datetime.now(timezone.utc) # This is 'created_at'
    )
    db.add(new_sync_job)
    db.flush() # Flush to get new_sync_job.id

    table_ids_to_process: List[int] = []
    if request.table_ids:
        # Future: Validate these tables belong to datasource_id and are accessible by user
        table_ids_to_process = request.table_ids
        logger.info(f"Job ID {new_sync_job.id}: Syncing specified tables: {table_ids_to_process}")
    else:
        active_datatables = db.query(DataTable.id).filter(
            DataTable.datasource_id == request.datasource_id,
            DataTable.is_active_for_sync == True
        ).all()
        table_ids_to_process = [dt.id for dt in active_datatables]
        logger.info(f"Job ID {new_sync_job.id}: Syncing all active tables for DS {request.datasource_id}. Found: {table_ids_to_process}")

    if not table_ids_to_process:
        new_sync_job.status = ExistingSyncStatus.FAILED
        new_sync_job.message = "No tables specified or found active for synchronization."
        new_sync_job.processing_start_time = datetime.now(timezone.utc)
        new_sync_job.end_time = datetime.now(timezone.utc)
        db.commit()
        job_response_early_fail = sync_schema.DataSyncJobResponse.from_orm(new_sync_job)
        job_response_early_fail.data_source_name = data_source.name
        return job_response_early_fail

    # Create SyncJobTableDetail records BEFORE launching the main task
    for table_id in table_ids_to_process:
        table_detail = SyncJobTableDetail(
            sync_job_id=new_sync_job.id,
            datatable_id=table_id,
            status=TableDetailStatus.PENDING # Initial status
        )
        db.add(table_detail)

    db.commit() # Commit job and all its details
    db.refresh(new_sync_job) # Refresh to load details relationship if needed for response

    # Launch the main Celery task, which will then spawn sub-tasks
    main_data_sync_job_task.delay(data_sync_job_id=new_sync_job.id)
    logger.info(f"Celery task main_data_sync_job_task.delay called for Job ID {new_sync_job.id}")

    job_response = sync_schema.DataSyncJobResponse.from_orm(new_sync_job)
    job_response.data_source_name = data_source.name
    # Populate table names in details for the response
    for detail_resp in job_response.details:
        dt = db.query(DataTable.schema_name, DataTable.table_name)\
               .filter(DataTable.id == detail_resp.datatable_id).first()
        if dt:
            detail_resp.schema_name = dt.schema_name
            detail_resp.table_name = dt.table_name
    return job_response

def get_data_sync_job_status(db: Session, job_id: int, current_user: user_model.User) -> Optional[sync_schema.DataSyncJobResponse]:
    job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
    if not job: return None

    # Validate user ownership by checking parent datasource
    data_source = crud_datasource.get_datasource(db=db, id=job.datasource_id, user_id=current_user.id)
    if not data_source:
        logger.warning(f"User {current_user.id} access denied for Job ID {job_id} (DS ID {job.datasource_id}).")
        return None # Or raise HTTPException(403)

    job_response = sync_schema.DataSyncJobResponse.from_orm(job)
    job_response.data_source_name = data_source.name
    for detail_resp in job_response.details:
        dt = db.query(DataTable.schema_name, DataTable.table_name)\
               .filter(DataTable.id == detail_resp.datatable_id).first()
        if dt:
            detail_resp.schema_name = dt.schema_name
            detail_resp.table_name = dt.table_name
    return job_response

def list_data_sync_jobs_for_source(
    db: Session,
    datasource_id: int,
    current_user: user_model.User,
    skip: int = 0,
    limit: int = 100
) -> List[sync_schema.DataSyncJobResponse]:
    data_source = crud_datasource.get_datasource(db=db, id=datasource_id, user_id=current_user.id)
    if not data_source:
        logger.warning(f"User {current_user.id} access denied or DS ID {datasource_id} not found for listing jobs.")
        return []

    jobs_query = db.query(SyncJob).filter(SyncJob.datasource_id == datasource_id)\
                     .order_by(SyncJob.start_time.desc()) # start_time is effectively created_at

    jobs = jobs_query.offset(skip).limit(limit).all()

    response_list: List[sync_schema.DataSyncJobResponse] = []
    for job in jobs:
        job_resp = sync_schema.DataSyncJobResponse.from_orm(job)
        job_resp.data_source_name = data_source.name
        for detail_resp in job_resp.details:
            dt = db.query(DataTable.schema_name, DataTable.table_name)\
                   .filter(DataTable.id == detail_resp.datatable_id).first()
            if dt:
                detail_resp.schema_name = dt.schema_name
                detail_resp.table_name = dt.table_name
        response_list.append(job_resp)

    return response_list

def update_table_incremental_config(
    db: Session,
    datatable_id: int, # Changed from table_metadata_id to match model name
    config_request: sync_schema.TableIncrementalConfigRequest,
    current_user: user_model.User
) -> DataTable: # Return the updated SQLAlchemy model instance

    # Fetch DataTable and verify ownership via its DataSource
    datatable = db.query(DataTable).filter(DataTable.id == datatable_id).first()
    if not datatable:
        raise ValueError("DataTable not found.")

    # Check ownership (user must own the datasource this datatable belongs to)
    data_source = crud_datasource.get_datasource(db=db, id=datatable.datasource_id, user_id=current_user.id)
    if not data_source:
        raise ValueError("Access to this DataTable's data source is denied.")

    # TODO: Future validation:
    # 1. Check if incremental_sync_column_name actually exists in datatable.columns.
    # 2. Check if incremental_sync_column_type is compatible with the actual column's data_type.
    # This would involve querying DataColumn models associated with this DataTable.

    datatable.incremental_sync_column_name = config_request.incremental_sync_column_name
    datatable.incremental_sync_column_type = config_request.incremental_sync_column_type
    # Optional: Clear last_successful_incremental_sync_watermark when config changes,
    # forcing the next incremental sync to potentially re-evaluate or start fresh for this table.
    # datatable.last_successful_incremental_sync_watermark = None

    db.add(datatable)
    db.commit()
    db.refresh(datatable)

    logger.info(f"User {current_user.email} updated incremental sync config for DataTable ID {datatable_id}: column '{config_request.incremental_sync_column_name}', type '{config_request.incremental_sync_column_type}'.")
    return datatable
