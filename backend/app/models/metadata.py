from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class DataTable(Base):
    __tablename__ = "datatables"
    id = Column(Integer, primary_key=True, index=True)
    datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=False)
    table_name = Column(String, nullable=False)
    schema_name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    is_active_for_sync = Column(Boolean, default=False, nullable=False)
    # The relationship to DataSource will be established by the backref in DataSource model if one is defined there.
    # If not, this defines one side of it.
    datasource = relationship("DataSource", backref="datatables")
    columns = relationship("DataColumn", back_populates="table", cascade="all, delete-orphan")

class DataColumn(Base):
    __tablename__ = "datacolumns"
    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("datatables.id"), nullable=False)
    column_name = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    is_nullable = Column(Boolean, default=True, nullable=False)
    max_length = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    table = relationship("DataTable", back_populates="columns")
