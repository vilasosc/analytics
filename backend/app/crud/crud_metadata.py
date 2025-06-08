from sqlalchemy.orm import Session
from app.models.metadata import DataTable, DataColumn
from app.models.datasource import DataSource # This is the SQLAlchemy model
from app.schemas.datasource import DataSourceBase as DataSourceSchemaBase # For type hinting in utils
from app.schemas.metadata import DataTableCreate # Only DataTableCreate needed for this version of sync
from app.utils.sqlserver_utils import get_sqlserver_metadata
from typing import List, Dict, Any, Optional

def get_datatable(db: Session, table_id: int) -> Optional[DataTable]:
    return db.query(DataTable).filter(DataTable.id == table_id).first()

def get_datatables_for_datasource(db: Session, datasource_id: int) -> List[DataTable]:
    return db.query(DataTable).filter(DataTable.datasource_id == datasource_id).all()

def delete_existing_metadata_for_datasource(db: Session, datasource_id: int):
    # Delete columns first due to foreign key constraint from DataTable
    db.query(DataColumn).join(DataTable).filter(DataTable.datasource_id == datasource_id).delete(synchronize_session='fetch')
    # Then delete tables
    db.query(DataTable).filter(DataTable.datasource_id == datasource_id).delete(synchronize_session='fetch')
    # No commit here, assuming the calling function will commit. If standalone, needs commit.
    # For sync_datasource_metadata, commit is at the end.

def sync_datasource_metadata(db: Session, datasource: DataSource) -> Dict[str, Any]:
    # Ensure datasource is the SQLAlchemy model instance
    if not isinstance(datasource, DataSource):
        raise TypeError("datasource parameter must be an instance of app.models.datasource.DataSource")

    if datasource.type.value != "SQLSERVER": # Access .value for Enum member
        raise ValueError(f"Metadata sync is currently only supported for SQLSERVER data sources, not {datasource.type.value}.")

    # Construct a schema representation for get_sqlserver_metadata if needed by the utility,
    # or pass model attributes directly if utility can handle it.
    # The get_sqlserver_metadata expects a DataSourceBase schema.
    datasource_schema_for_util = DataSourceSchemaBase(
        name=datasource.name,
        type=datasource.type, # This should be the Enum value itself if schema expects it
        db_host=datasource.db_host,
        db_port=datasource.db_port,
        db_name=datasource.db_name,
        db_username=datasource.db_username
        # db_password is not part of DataSourceBase, handled by password_override
    )

    try:
        raw_tables = get_sqlserver_metadata(
            ds_details=datasource_schema_for_util,
            password_override=datasource.db_password,
            object_type='TABLES'
        )
    except Exception as e:
        # Log the full error for debugging
        print(f"Error during get_sqlserver_metadata (TABLES) for datasource {datasource.id}: {e}")
        raise ConnectionError(f"Failed to fetch tables from data source '{datasource.name}': {e}")

    delete_existing_metadata_for_datasource(db, datasource_id=datasource.id)
    tables_synced_count = 0
    columns_synced_count = 0

    for raw_table_info in raw_tables:
        table_schema_name = raw_table_info.get('TABLE_SCHEMA')
        table_name_db = raw_table_info.get('TABLE_NAME')
        if not table_name_db:
            print(f"Skipping table with no name: {raw_table_info}")
            continue

        # Create DataTable, is_active_for_sync defaults to False
        db_table = DataTable(
            datasource_id=datasource.id,
            table_name=table_name_db,
            schema_name=table_schema_name
        )
        db.add(db_table)
        # Must flush to get db_table.id for columns.
        # The final commit is at the end of the function.
        db.flush()
        tables_synced_count += 1

        try:
            raw_columns = get_sqlserver_metadata(
                ds_details=datasource_schema_for_util,
                password_override=datasource.db_password,
                object_type='COLUMNS',
                schema_name=table_schema_name,
                table_name=table_name_db
            )
        except Exception as e:
            print(f"Error fetching columns for {table_schema_name}.{table_name_db} (Datasource ID: {datasource.id}): {e}")
            # Decide if sync should continue or rollback/raise for this table
            continue # Skip this table's columns if error

        for raw_col_info in raw_columns:
            col_name = raw_col_info.get('COLUMN_NAME')
            if not col_name:
                print(f"Skipping column with no name for table {table_schema_name}.{table_name_db}: {raw_col_info}")
                continue

            is_nullable_str = raw_col_info.get('IS_NULLABLE', 'YES')
            is_nullable_bool = True if is_nullable_str is None else (is_nullable_str.upper() == 'YES')

            db_col = DataColumn(
                table_id=db_table.id,
                column_name=col_name,
                data_type=raw_col_info.get('DATA_TYPE', 'UNKNOWN'),
                is_nullable=is_nullable_bool,
                max_length=raw_col_info.get('CHARACTER_MAXIMUM_LENGTH')
            )
            db.add(db_col)
            columns_synced_count +=1

    db.commit() # Commit all changes for this datasource sync
    return {"tables_discovered": tables_synced_count, "columns_discovered": columns_synced_count, "message": "Metadata sync complete."}

def update_table_activation_status(db: Session, table_id: int, is_active: bool) -> Optional[DataTable]:
    db_table = db.query(DataTable).filter(DataTable.id == table_id).first()
    if db_table:
        db_table.is_active_for_sync = is_active
        db.add(db_table)
        db.commit()
        db.refresh(db_table)
    return db_table
