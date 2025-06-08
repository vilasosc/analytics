import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import SessionLocal # Or your specific DB session dependency
from app.models import user as user_model # For current_user type hint
from app.data_sync import service as sync_service
from app.schemas import sync as sync_schema
from app.routers.auth import get_current_active_user # Assuming auth dependency

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sync",
    tags=["Data Synchronization"],
    dependencies=[Depends(get_current_active_user)] # General auth for all sync routes
)

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post(
    "/trigger",
    response_model=sync_schema.DataSyncJobResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def trigger_sync_job_endpoint(
    request: sync_schema.DataSyncTriggerRequest,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_active_user)
):
    try:
        logger.info(f"User '{current_user.email}' triggering sync job for DataSource ID {request.datasource_id}, mode: {request.actual_sync_mode}, type: {request.sync_type}, tables: {request.table_ids}")
        job_response = sync_service.trigger_data_sync_job(
            db=db,
            request=request, # Pass the whole request
            current_user=current_user
        )
        return job_response
    except ValueError as ve:
        logger.error(f"ValueError triggering sync job: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error triggering sync job: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to trigger data sync job.")

@router.get("/jobs/{job_id}", response_model=sync_schema.DataSyncJobResponse)
def get_sync_job_status_endpoint(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_active_user)
):
    logger.debug(f"User '{current_user.email}' requesting status for Job ID {job_id}")
    job_status = sync_service.get_data_sync_job_status(db=db, job_id=job_id, current_user=current_user)
    if not job_status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data sync job not found or access denied.")
    return job_status

@router.get(
    "/jobs/datasource/{datasource_id}", # Corrected path parameter name
    response_model=List[sync_schema.DataSyncJobResponse]
)
def list_sync_jobs_for_data_source_endpoint(
    datasource_id: int, # Corrected variable name
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_active_user)
):
    logger.debug(f"User '{current_user.email}' requesting job list for DataSource ID {datasource_id}")
    jobs = sync_service.list_data_sync_jobs_for_source(
        db=db, datasource_id=datasource_id, current_user=current_user, skip=skip, limit=limit
    )
    # No need to check if jobs is None, service returns [] for not found/denied.
    return jobs
