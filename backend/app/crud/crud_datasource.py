from sqlalchemy.orm import Session
from app.models.datasource import DataSource
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate
from typing import List, Optional
from app.core.security import encrypt_data, decrypt_data # Import for password encryption and decryption

def get_datasource(db: Session, datasource_id: int) -> Optional[DataSource]:
    return db.query(DataSource).filter(DataSource.id == datasource_id).first()

def get_datasources(db: Session, skip: int = 0, limit: int = 100) -> List[DataSource]:
    return db.query(DataSource).offset(skip).limit(limit).all()

def create_datasource(db: Session, datasource: DataSourceCreate) -> DataSource:
    datasource_data = datasource.model_dump()
    if datasource.db_password:
        encrypted_password = encrypt_data(datasource.db_password)
        datasource_data['db_password'] = encrypted_password
    db_datasource = DataSource(**datasource_data)
    db.add(db_datasource)
    db.commit()
    db.refresh(db_datasource)
    return db_datasource

def update_datasource(db: Session, db_obj: DataSource, obj_in: DataSourceUpdate) -> Optional[DataSource]:
    obj_data = obj_in.model_dump(exclude_unset=True)
    if 'db_password' in obj_data and obj_data['db_password']:
        obj_data['db_password'] = encrypt_data(obj_data['db_password'])
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

def get_datasource_with_decrypted_password(db: Session, datasource_id: int) -> Optional[DataSource]:
    """
    Retrieves a datasource by ID and decrypts its db_password in-memory.

    Args:
        db: The database session.
        datasource_id: The ID of the datasource to retrieve.

    Returns:
        The DataSource object with its db_password decrypted, or None if not found.
        IMPORTANT: The password decryption is in-memory. If this session-attached SQLAlchemy
        object is later part of a db.commit(), it would attempt to save the decrypted
        password. This function is intended for read-only use of the password.
    """
    db_datasource = get_datasource(db=db, datasource_id=datasource_id)

    if db_datasource and db_datasource.db_password:
        try:
            decrypted_password = decrypt_data(db_datasource.db_password)
            db_datasource.db_password = decrypted_password
        except Exception as e:
            # Log or handle specific Fernet exceptions like InvalidToken if necessary
            # For now, re-raising to make it visible that decryption failed.
            # Consider specific error handling based on application needs.
            # print(f"Error decrypting password for datasource {datasource_id}: {e}")
            raise e # Or a custom application exception

    return db_datasource
