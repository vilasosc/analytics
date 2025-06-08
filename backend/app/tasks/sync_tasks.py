import logging # Added
import os
from typing import List

from celery import Celery # Should already be here via celery_app, but explicit can be fine
from app.core.celery_app import celery_app
from app.core.config import settings # Added
from app.core.database import SessionLocal
from app.crud.crud_datasource import get_datasource_with_decrypted_password
from app.crud.crud_metadata import get_datatables_for_datasource # Moved to top
from app.crud.crud_sync import (
    create_sync_job,
    get_sync_job,
    update_sync_job_status,
    create_sync_job_table_detail,
    update_sync_job_table_detail_status,
)
from app.models.metadata import DataTable
from app.models.sync import SyncStatus, SyncType
from app.schemas.datasource import DataSourceBase as PydanticDataSourceBase
from app.utils.parquet_utils import write_data_to_parquet
from app.utils.sqlserver_utils import fetch_all_data_from_table


# PARQUET_BASE_DIR is now sourced from settings.PARQUET_STORAGE_BASE_DIR

@celery_app.task(bind=True, name="tasks.run_sync_for_datasource")
def run_sync_for_datasource_task(self, datasource_id: int, sync_type_value: str = SyncType.MANUAL.value):
    """
    Celery task to perform data synchronization for a given datasource.
    """
    logger = self.get_logger() # Get Celery logger
    db = SessionLocal()
    sync_job = None
    current_sync_type = SyncType(sync_type_value)

    try:
        datasource = get_datasource_with_decrypted_password(db=db, datasource_id=datasource_id)
        if not datasource:
            logger.error(f"Datasource ID {datasource_id} not found.")
            return {"status": "Error", "message": "Datasource not found"}

        sync_job = create_sync_job(
            db=db,
            datasource_id=datasource.id,
            sync_type=current_sync_type, # Use current_sync_type
            initial_status=SyncStatus.RUNNING
        )

        active_tables_query: List[DataTable] = get_datatables_for_datasource(db=db, datasource_id=datasource.id)
        active_tables = [table for table in active_tables_query if table.is_active_for_sync]


        if not active_tables:
            update_sync_job_status(db, sync_job_id=sync_job.id, status=SyncStatus.SUCCESS, message="No active tables found for synchronization.", set_end_time=True)
            # refetched_job = get_sync_job(db, sync_job.id)
            return {"status": "Success", "job_id": sync_job.id, "message": "No active tables."}


        overall_status = SyncStatus.SUCCESS
        failed_count = 0

        for table_meta in active_tables:
            detail = create_sync_job_table_detail(db=db, sync_job_id=sync_job.id, datatable_id=table_meta.id, initial_status=SyncStatus.RUNNING)
            rows_count = 0
            try:
                pydantic_ds_details = PydanticDataSourceBase(
                    name=datasource.name,
                    type=str(datasource.type.value),
                    db_host=datasource.db_host,
                    db_port=datasource.db_port,
                    db_name=datasource.db_name,
                    db_username=datasource.db_username
                    # db_password is intentionally omitted, as fetch_all_data_from_table takes password_override
                )

                table_data = fetch_all_data_from_table(
                    ds_details=pydantic_ds_details,
                    password_override=datasource.db_password, # Use the decrypted password
                    schema_name=table_meta.schema_name if table_meta.schema_name else 'dbo',
                    table_name=table_meta.table_name
                )
                rows_count = len(table_data)

                schema_folder_name = f"schema_{table_meta.schema_name}" if table_meta.schema_name else "schema_None"
                datasource_parquet_dir = os.path.join(
                    settings.PARQUET_STORAGE_BASE_DIR, # Use settings
                    f"datasource_{datasource.id}",
                    schema_folder_name
                )
                os.makedirs(datasource_parquet_dir, exist_ok=True)

                file_path = os.path.join(datasource_parquet_dir, f"table_{table_meta.table_name}.parquet")
                write_data_to_parquet(data=table_data, file_path=file_path)
                update_sync_job_table_detail_status(db=db, detail_id=detail.id, status=SyncStatus.SUCCESS, rows_processed=rows_count, set_end_time=True)

            except Exception as table_exc: # Renamed to avoid conflict with outer 'e'
                failed_count += 1
                err_msg = f"Error processing table '{table_meta.table_name}': {str(table_exc)[:500]}"
                logger.error(f"Table processing error for {table_meta.table_name} in datasource {datasource_id}: {table_exc}", exc_info=True)
                update_sync_job_table_detail_status(db=db, detail_id=detail.id, status=SyncStatus.FAILED, error_message=err_msg, rows_processed=rows_count, set_end_time=True)

        if failed_count > 0:
            overall_status = SyncStatus.PARTIAL_SUCCESS if failed_count < len(active_tables) else SyncStatus.FAILED

        final_msg = f"Synchronization complete. {len(active_tables) - failed_count} table(s) succeeded, {failed_count} table(s) failed."
        update_sync_job_status(db, sync_job_id=sync_job.id, status=overall_status, message=final_msg, set_end_time=True)

        return {"status": str(overall_status.value), "job_id": sync_job.id, "message": final_msg}

    except Exception as e:
        logger.error(f"Error in Celery task run_sync_for_datasource_task for datasource_id {datasource_id}: {e}", exc_info=True)
        if sync_job:
            update_sync_job_status(db, sync_job_id=sync_job.id, status=SyncStatus.FAILED, message=f"Task level error: {str(e)[:500]}", set_end_time=True)
        # self.update_state(state='FAILURE', meta={'exc': str(e)}) # Optional: update Celery task state
        return {"status": "Error", "message": str(e)}
    finally:
        db.close()
