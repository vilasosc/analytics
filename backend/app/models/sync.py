from sqlalchemy import Column, Integer, String, Enum as SAEnum, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
# Forward references as strings can be used if models are in different files and loaded later
# from app.models.metadata import DataTable
# from app.models.datasource import DataSource
import enum

class SyncStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"

class SyncType(str, enum.Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED" # For future use

class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id = Column(Integer, primary_key=True, index=True)
    # ForeignKey uses the actual table name and column name, e.g., 'datasources.id'
    datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=False)

    sync_type = Column(SAEnum(SyncType), nullable=False, default=SyncType.MANUAL)
    status = Column(SAEnum(SyncStatus), nullable=False, default=SyncStatus.PENDING)

    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)

    message = Column(Text, nullable=True) # For overall job messages or errors

    # Relationships
    # If DataSource model had a 'sync_jobs' relationship, it would be:
    # datasource = relationship("DataSource", back_populates="sync_jobs")
    # For now, no direct back_populates from DataSource model.

    details = relationship("SyncJobTableDetail", back_populates="sync_job", cascade="all, delete-orphan")

class SyncJobTableDetail(Base):
    __tablename__ = "sync_job_table_details"
    id = Column(Integer, primary_key=True, index=True)
    sync_job_id = Column(Integer, ForeignKey("sync_jobs.id"), nullable=False)
    # ForeignKey uses the actual table name 'datatables' and column 'id'
    datatable_id = Column(Integer, ForeignKey("datatables.id"), nullable=False)

    status = Column(SAEnum(SyncStatus), nullable=False, default=SyncStatus.PENDING)
    start_time = Column(DateTime(timezone=True), server_default=func.now()) # Default to job start is tricky, usually set when detail processing starts
    end_time = Column(DateTime(timezone=True), nullable=True)

    rows_processed = Column(BigInteger, default=0)
    error_message = Column(Text, nullable=True)

    # Relationships
    sync_job = relationship("SyncJob", back_populates="details")
    # Optional: direct relationship to the DataTable model if frequently accessed
    # datatable = relationship("DataTable") # This would require importing DataTable
    # For now, access via datatable_id is sufficient. We can add this later if needed.
