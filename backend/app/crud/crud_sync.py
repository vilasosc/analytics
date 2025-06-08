from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.models.sync import SyncJob, SyncJobTableDetail, SyncStatus, SyncType
from app.models.datasource import DataSource # Retained: Used by other functions or potentially useful
from app.models.metadata import DataTable # Retained: Used by other functions or potentially useful
# from app.crud.crud_metadata import get_datatables_for_datasource # Removed: Specific to run_manual_sync_for_datasource
# from app.utils.sqlserver_utils import fetch_all_data_from_table # Removed: Specific to run_manual_sync_for_datasource
# from app.utils.parquet_utils import write_data_to_parquet # Removed: Specific to run_manual_sync_for_datasource
# from app.schemas.datasource import DataSourceBase as PydanticDataSourceBase # Removed: Specific to run_manual_sync_for_datasource
# import os # Removed: Specific to run_manual_sync_for_datasource
from sqlalchemy.sql import func

def create_sync_job(db: Session, datasource_id: int, sync_type: SyncType = SyncType.MANUAL, initial_status: SyncStatus = SyncStatus.PENDING) -> SyncJob:
    db_sync_job = SyncJob(datasource_id=datasource_id, sync_type=sync_type, status=initial_status)
    db.add(db_sync_job)
    db.commit()
    db.refresh(db_sync_job)
    return db_sync_job

def get_sync_job(db: Session, sync_job_id: int) -> Optional[SyncJob]:
    return db.query(SyncJob).options(joinedload(SyncJob.details)).filter(SyncJob.id == sync_job_id).first()

def get_sync_jobs_for_datasource(db: Session, datasource_id: int, skip: int = 0, limit: int = 10) -> List[SyncJob]:
    return db.query(SyncJob).options(joinedload(SyncJob.details)).filter(SyncJob.datasource_id == datasource_id).order_by(SyncJob.start_time.desc()).offset(skip).limit(limit).all()

def update_sync_job_status(db: Session, sync_job_id: int, status: SyncStatus, message: Optional[str] = None, set_end_time: bool = False) -> Optional[SyncJob]:
    db_sync_job = db.query(SyncJob).filter(SyncJob.id == sync_job_id).first()
    if db_sync_job:
        db_sync_job.status = status
        if message is not None:
            db_sync_job.message = message
        if set_end_time:
            db_sync_job.end_time = func.now()
        db.commit()
        db.refresh(db_sync_job)
    return db_sync_job

def create_sync_job_table_detail(db: Session, sync_job_id: int, datatable_id: int, initial_status: SyncStatus = SyncStatus.PENDING) -> SyncJobTableDetail:
    # start_time is server_default=func.now() in the model, so it's set on creation.
    db_detail = SyncJobTableDetail(sync_job_id=sync_job_id, datatable_id=datatable_id, status=initial_status)
    db.add(db_detail)
    db.commit()
    db.refresh(db_detail)
    return db_detail

def update_sync_job_table_detail_status(db: Session, detail_id: int, status: SyncStatus, rows_processed: Optional[int] = None, error_message: Optional[str] = None, set_end_time: bool = False) -> Optional[SyncJobTableDetail]:
    db_detail = db.query(SyncJobTableDetail).filter(SyncJobTableDetail.id == detail_id).first()
    if db_detail:
        db_detail.status = status
        if rows_processed is not None:
            db_detail.rows_processed = rows_processed

        # Logic to allow clearing error_message by passing None explicitly.
        # If error_message is provided (even if empty string), set it.
        # If error_message is None, and the field currently has a value, set it to None.
        if error_message is not None:
            db_detail.error_message = error_message
        elif error_message is None and db_detail.error_message is not None: # Only clear if it was previously set
             db_detail.error_message = None

        if set_end_time:
            db_detail.end_time = func.now()
        db.commit()
        db.refresh(db_detail)
    return db_detail

def get_sync_job_table_details_for_job(db: Session, sync_job_id: int) -> List[SyncJobTableDetail]:
    return db.query(SyncJobTableDetail).filter(SyncJobTableDetail.sync_job_id == sync_job_id).all()

# def run_manual_sync_for_datasource(db: Session, datasource: DataSource) -> SyncJob:
#     PARQUET_BASE_DIR = os.path.join("pcsoft_data_storage", "parquet_files") # Simplified path
#
#     sync_job = create_sync_job(db=db, datasource_id=datasource.id, sync_type=SyncType.MANUAL, initial_status=SyncStatus.RUNNING)
#
#     # Ensure that get_datatables_for_datasource returns DataTable instances
#     active_tables_query: List[DataTable] = get_datatables_for_datasource(db=db, datasource_id=datasource.id) # This import would need to be restored if uncommented
#     active_tables = [table for table in active_tables_query if table.is_active_for_sync]
#
#     if not active_tables:
#         update_sync_job_status(db, sync_job_id=sync_job.id, status=SyncStatus.SUCCESS, message="No active tables found for synchronization.", set_end_time=True)
#         # Re-fetch job to get updated status and details (though no details in this case)
#         refetched_job = get_sync_job(db, sync_job.id)
#         return refetched_job if refetched_job else sync_job
#
#
#     overall_status = SyncStatus.SUCCESS # Assume success until a failure occurs
#     failed_count = 0
#
#     for table_meta in active_tables:
#         # Create detail record, start_time is set by server_default in model
#         detail = create_sync_job_table_detail(db=db, sync_job_id=sync_job.id, datatable_id=table_meta.id, initial_status=SyncStatus.RUNNING)
#         rows_count = 0
#         try:
#             # Convert SQLAlchemy DataSource model to Pydantic DataSourceBase for utility function compatibility
#             # Assuming datasource.type is an Enum, its .value gives the string representation
#             # pydantic_ds_details = PydanticDataSourceBase( # This import would need to be restored if uncommented
#             # name=datasource.name,
#             # type=str(datasource.type.value),
#             # db_host=datasource.db_host,
#             # db_port=datasource.db_port,
#             # db_name=datasource.db_name,
#             # db_username=datasource.db_username
#             # )
#
#             # table_data = fetch_all_data_from_table( # This import would need to be restored if uncommented
#             # ds_details=pydantic_ds_details,
#             # password_override=datasource.db_password, # Assuming db_password field exists on DataSource model
#             # schema_name=table_meta.schema_name if table_meta.schema_name else 'dbo',
#             # table_name=table_meta.table_name
#             # )
#             # rows_count = len(table_data)
#
#             # Define file path structure: BASE_DIR/datasource_XX/schema_YYY/table_ZZZ.parquet
#             # Handle cases where schema_name might be None or empty
#             schema_folder_name = f"schema_{table_meta.schema_name}" if table_meta.schema_name else "schema_None"
#
#             # file_path = os.path.join(PARQUET_BASE_DIR, f"datasource_{datasource.id}", schema_folder_name, f"table_{table_meta.table_name}.parquet") # os import needed
#
#             # write_data_to_parquet(data=table_data, file_path=file_path) # This import would need to be restored if uncommented
#             update_sync_job_table_detail_status(db=db, detail_id=detail.id, status=SyncStatus.SUCCESS, rows_processed=rows_count, set_end_time=True)
#
#         except Exception as e:
#             failed_count += 1
#             # Truncate error message to avoid overly long strings in DB
#             err_msg = f"Error processing table '{table_meta.table_name}': {str(e)[:500]}"
#             update_sync_job_table_detail_status(db=db, detail_id=detail.id, status=SyncStatus.FAILED, error_message=err_msg, rows_processed=rows_count, set_end_time=True)
#
#     if failed_count > 0:
#         if failed_count == len(active_tables):
#             overall_status = SyncStatus.FAILED
#         else:
#             overall_status = SyncStatus.PARTIAL_SUCCESS
#
#     final_msg = f"Synchronization complete. {len(active_tables) - failed_count} table(s) succeeded, {failed_count} table(s) failed."
#     update_sync_job_status(db, sync_job_id=sync_job.id, status=overall_status, message=final_msg, set_end_time=True)
#
#     # Re-fetch the job to include all updated details and status
#     refetched_job_final = get_sync_job(db, sync_job.id)
#     return refetched_job_final if refetched_job_final else sync_job
