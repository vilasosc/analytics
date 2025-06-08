from sqlalchemy.orm import Session
from app.models.datasource import DataSource
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate
from typing import List, Optional

def get_datasource(db: Session, datasource_id: int) -> Optional[DataSource]:
    return db.query(DataSource).filter(DataSource.id == datasource_id).first()

def get_datasources(db: Session, skip: int = 0, limit: int = 100) -> List[DataSource]:
    return db.query(DataSource).offset(skip).limit(limit).all()

def create_datasource(db: Session, datasource: DataSourceCreate) -> DataSource:
    db_datasource = DataSource(**datasource.model_dump()) # TECH_DEBT: Encrypt password
    db.add(db_datasource)
    db.commit()
    db.refresh(db_datasource)
    return db_datasource

def update_datasource(db: Session, db_obj: DataSource, obj_in: DataSourceUpdate) -> Optional[DataSource]:
    obj_data = obj_in.model_dump(exclude_unset=True)
    # TECH_DEBT: Handle db_password update with encryption if provided
    for field, value in obj_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def delete_datasource(db: Session, datasource_id: int) -> Optional[DataSource]:
    db_obj = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj # Returns the object if found and deleted, else None
