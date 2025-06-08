import logging
import os
from datetime import datetime, timezone
import shutil

from sqlalchemy.orm import Session
from app.core.celery_app import celery_app # Adjusted import for Celery app
from app.models.sync import SyncJob, SyncJobTableDetail, ExistingSyncStatus, TableDetailStatus, ExistingSyncType
from app.models.datasource import DataSource
from app.models.metadata import DataTable
from app.core.database import SessionLocal
from app.core.security import decrypt_data # Assuming this exists from a previous step/base
from app.core.config import get_parquet_file_path_for_table, settings # For DATASOURCE_ENCRYPTION_KEY
from app.utils.type_mapper import get_pyarrow_schema_from_model # Adjusted from get_pyarrow_schema_from_table_metadata
from app.utils.data_sync_utils import (
    extract_data_from_sql_server_full,
    extract_data_from_sql_server_incremental,
    write_record_batches_to_parquet
)
from app.utils.sqlserver_utils import get_sql_server_connection_string # General utility

logger = logging.getLogger(__name__)

def _update_job_status_if_all_done(job_id: int, db: Session):
    """Helper to check and update parent DataSyncJob status."""
    job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
    if not job:
        logger.error(f"_update_job_status: SyncJob ID {job_id} not found.")
        return

    pending_details = db.query(SyncJobTableDetail).filter(
        SyncJobTableDetail.sync_job_id == job_id,
        SyncJobTableDetail.status.in_([
            TableDetailStatus.PENDING, TableDetailStatus.EXTRACTING,
            TableDetailStatus.CONVERTING, TableDetailStatus.WRITING
        ])
    ).count()

    if pending_details > 0:
        logger.info(f"SyncJob ID {job_id}: {pending_details} table syncs still pending/in progress.")
        return

    failed_details_count = db.query(SyncJobTableDetail).filter(
        SyncJobTableDetail.sync_job_id == job_id,
        SyncJobTableDetail.status == TableDetailStatus.FAILED
    ).count()

    completed_details_count = db.query(SyncJobTableDetail).filter(
        SyncJobTableDetail.sync_job_id == job_id,
        SyncJobTableDetail.status == TableDetailStatus.COMPLETED
    ).count()

    total_details_count = db.query(SyncJobTableDetail).filter(SyncJobTableDetail.sync_job_id == job_id).count()

    if failed_details_count > 0:
        job.status = ExistingSyncStatus.PARTIAL_SUCCESS if completed_details_count > 0 else ExistingSyncStatus.FAILED
        job.message = f"{failed_details_count}/{total_details_count} table(s) failed to sync."
    elif completed_details_count == total_details_count:
        job.status = ExistingSyncStatus.SUCCESS
        job.message = "All tables synced successfully."
    else: # Mix of completed and skipped, but no active failures
        job.status = ExistingSyncStatus.PARTIAL_SUCCESS
        job.message = f"Job finished with {total_details_count - completed_details_count} skipped/pending tables and no failures."

    job.end_time = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"SyncJob ID {job_id} status updated to {job.status}.")


@celery_app.task(name="execute_table_sync_task", bind=True, max_retries=1, default_retry_delay=60)
def execute_table_sync_task(self, table_detail_id: int):
    db: Session = SessionLocal()
    table_detail: Optional[SyncJobTableDetail] = None
    try:
        table_detail = db.query(SyncJobTableDetail).filter(SyncJobTableDetail.id == table_detail_id).first()
        if not table_detail:
            logger.error(f"Task execute_table_sync_task: SyncJobTableDetail ID {table_detail_id} not found.")
            return

        job = table_detail.sync_job
        datatable = table_detail.datatable # Relationship should load this
        datasource = job.datasource     # Relationship should load this

        if not (job and datatable and datasource):
            raise ValueError("Could not load job, datatable, or datasource from table_detail relationships.")

        table_detail.detail_start_time = datetime.now(timezone.utc)
        table_detail.status = TableDetailStatus.EXTRACTING
        db.commit()

        decrypted_password = decrypt_data(datasource.db_password, settings.DATASOURCE_ENCRYPTION_KEY)
        if not decrypted_password:
            raise ValueError("Failed to decrypt data source password.")

        conn_str = get_sql_server_connection_string(
            datasource.db_host, datasource.db_port, datasource.db_name,
            datasource.db_username, decrypted_password
        )

        # Use datatable.columns relationship (already loaded or lazy-loads)
        pyarrow_schema = get_pyarrow_schema_from_model(datatable.columns)
        if not pyarrow_schema:
            raise ValueError(f"Failed to generate PyArrow schema for DataTable ID {datatable.id}.")

        # File naming: ds_<id>/<schema>_<table_name>/<YYYYMMDD_HHMMSS>_<type>.parquet
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        versioned_file_name = f"{timestamp_str}_{job.actual_sync_mode}.parquet"

        target_parquet_path = get_parquet_file_path_for_table( # From core.config
            data_source_id=datasource.id,
            schema_name=datatable.schema_name,
            table_name=datatable.table_name,
            version=versioned_file_name
        )
        latest_parquet_path = get_parquet_file_path_for_table(
            data_source_id=datasource.id,
            schema_name=datatable.schema_name,
            table_name=datatable.table_name,
            version=None # gets 'latest_sync.parquet'
        )

        record_iterator: Iterator[pa.RecordBatch]
        current_watermark_for_next_run = None

        if job.actual_sync_mode == "full":
            record_iterator = extract_data_from_sql_server_full(
                conn_str, datatable.schema_name, datatable.table_name, pyarrow_schema
            )
            table_detail.source_watermark_start = None
        elif job.actual_sync_mode == "incremental":
            if not datatable.incremental_sync_column_name or not datatable.incremental_sync_column_type:
                raise ValueError("Incremental sync requested but table is not configured (missing column name/type).")

            last_watermark = datatable.last_successful_incremental_sync_watermark
            table_detail.source_watermark_start = last_watermark
            # TODO: Actual type casting for last_watermark based on datatable.incremental_sync_column_type
            # This is critical for correct incremental logic. Placeholder:
            typed_last_watermark = last_watermark

            record_iterator = extract_data_from_sql_server_incremental(
                conn_str, datatable.schema_name, datatable.table_name,
                datatable.incremental_sync_column_name,
                typed_last_watermark,
                pyarrow_schema
            )
        else:
            raise ValueError(f"Unsupported sync_mode: {job.actual_sync_mode}")

        table_detail.status = TableDetailStatus.WRITING
        db.commit()

        # Handle potential error string from iterator's first item
        first_item = next(record_iterator, None)
        if isinstance(first_item, str) and first_item.startswith("Error:"):
            raise ValueError(f"Data extraction failed: {first_item}")

        def combined_iterator(first, rest):
            if first is not None: yield first
            yield from rest

        final_iterator = combined_iterator(first_item, record_iterator) if first_item is not None else iter([])

        records_written, error = write_record_batches_to_parquet(final_iterator, target_parquet_path, pyarrow_schema)

        if error:
            raise ValueError(f"Parquet writing failed: {error}")

        table_detail.records_processed = records_written
        table_detail.parquet_file_path = target_parquet_path
        table_detail.status = TableDetailStatus.COMPLETED
        table_detail.error_message = None

        # Update 'latest_sync.parquet'
        # Ensure directory for latest_parquet_path exists
        latest_dir = os.path.dirname(latest_parquet_path)
        if latest_dir: os.makedirs(latest_dir, exist_ok=True)

        if os.path.exists(latest_parquet_path): os.remove(latest_parquet_path)
        shutil.copy2(target_parquet_path, latest_parquet_path)
        logger.info(f"Updated 'latest_sync.parquet' for {datatable.schema_name}.{datatable.table_name}")

        if job.actual_sync_mode == "incremental" and records_written > 0:
            # This is a placeholder. Real watermark extraction from Parquet file is needed.
            # For now, using sync time as a proxy if the column is datetime-like.
            # This is NOT robust for non-datetime or non-sequential watermarks.
            current_watermark_for_next_run = datetime.now(timezone.utc).isoformat()
            datatable.last_successful_incremental_sync_watermark = current_watermark_for_next_run
            table_detail.source_watermark_end = current_watermark_for_next_run
            logger.info(f"Incremental sync for {datatable.table_name}: new watermark '{current_watermark_for_next_run}' (placeholder).")

        datatable.last_metadata_synced_at = datetime.now(timezone.utc) # Treat data sync as a metadata update for this table
        db.commit()

    except Exception as exc:
        logger.error(f"execute_table_sync_task failed for Detail ID {table_detail_id}: {exc}", exc_info=True)
        if db.is_active: db.rollback()
        if table_detail:
            table_detail.status = TableDetailStatus.FAILED
            table_detail.error_message = str(exc)[:2048] # Limit error message length
        # Retry logic is implicitly handled by Celery if self.retry is called (or task fails)
        # self.update_state(state='FAILURE', meta={'exc_type': type(exc).__name__, 'exc_message': str(exc)})
        raise # Re-raise to let Celery handle retry/failure state
    finally:
        if table_detail: # Final update regardless of outcome
            table_detail.detail_end_time = datetime.now(timezone.utc)
            db.commit()
            _update_job_status_if_all_done(table_detail.sync_job_id, db)
        if db: db.close()


@celery_app.task(name="main_data_sync_job_task", bind=True)
def main_data_sync_job_task(self, data_sync_job_id: int):
    db: Session = SessionLocal()
    job: Optional[SyncJob] = None
    try:
        job = db.query(SyncJob).filter(SyncJob.id == data_sync_job_id).first()
        if not job:
            logger.error(f"Task main_data_sync_job_task: SyncJob ID {data_sync_job_id} not found.")
            return

        job.processing_start_time = datetime.now(timezone.utc)
        job.status = ExistingSyncStatus.RUNNING
        db.commit()

        # This task now expects table_ids_to_sync to be set by the service layer
        # when creating SyncJobTableDetail entries. Here we just iterate them.
        table_details_to_process = db.query(SyncJobTableDetail).filter(
            SyncJobTableDetail.sync_job_id == job.id,
            SyncJobTableDetail.status == TableDetailStatus.PENDING # Only process pending
        ).all()

        if not table_details_to_process:
            logger.info(f"No pending table details found for SyncJob ID {job.id} to process.")
            # This might mean tables were pre-failed/skipped or already processed.
            # _update_job_status_if_all_done will finalize if nothing was pending.

        any_task_launched = False
        for detail in table_details_to_process:
            datatable = db.query(DataTable).filter(DataTable.id == detail.datatable_id).first() # Refresh datatable object
            if not datatable:
                detail.status = TableDetailStatus.FAILED
                detail.error_message = "DataTable metadata not found."
            elif not datatable.is_active_for_sync:
                detail.status = TableDetailStatus.SKIPPED
                detail.error_message = "Table is not active for sync."
            elif job.actual_sync_mode == "incremental" and not datatable.incremental_sync_column_name:
                detail.status = TableDetailStatus.FAILED
                detail.error_message = "Incremental sync requested but table not configured."

            if detail.status != TableDetailStatus.PENDING: # If status changed due to checks
                db.commit() # Commit pre-failure/skip status
            else:
                execute_table_sync_task.delay(table_detail_id=detail.id)
                any_task_launched = True

        if not any_task_launched and table_details_to_process: # All were pre-failed/skipped
             _update_job_status_if_all_done(job.id, db)
        elif not table_details_to_process: # No details were pending initially
            _update_job_status_if_all_done(job.id, db)


    except Exception as e:
        logger.error(f"main_data_sync_job_task failed for Job ID {data_sync_job_id}: {e}", exc_info=True)
        if job:
            job.status = ExistingSyncStatus.FAILED
            job.message = str(e)
            job.end_time = datetime.now(timezone.utc)
            db.commit()
    finally:
        if db: db.close()
