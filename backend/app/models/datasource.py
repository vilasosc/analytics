from sqlalchemy import Column, Integer, String, Enum as SAEnum, DateTime
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class DBDataSourceType(str, enum.Enum):
    SQLSERVER = "SQLSERVER"

class DataSource(Base):
    __tablename__ = "datasources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    type = Column(SAEnum(DBDataSourceType), nullable=False, default=DBDataSourceType.SQLSERVER)
    db_host = Column(String, nullable=False)
    db_port = Column(Integer, nullable=False)
    db_name = Column(String, nullable=False)
    db_username = Column(String, nullable=False)
    db_password = Column(String, nullable=False) # TECH_DEBT: Store securely
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_onupdate=func.now())
