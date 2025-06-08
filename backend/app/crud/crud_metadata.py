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
    if not isinstance(datasource, DataSource):
        raise TypeError("datasource parameter must be an instance of app.models.datasource.DataSource")

    if datasource.type.value != "SQLSERVER":
        raise ValueError(f"Metadata sync is currently only supported for SQLSERVER data sources, not {datasource.type.value}.")

    datasource_schema_for_util = DataSourceSchemaBase(
        name=datasource.name,
        type=datasource.type,
        db_host=datasource.db_host,
        db_port=datasource.db_port,
        db_name=datasource.db_name,
        db_username=datasource.db_username
    )

    # 1. Fetch Existing Metadata
    existing_tables_map: Dict[tuple[Optional[str], str], Dict[str, Any]] = {}
    existing_db_tables = db.query(DataTable).filter(DataTable.datasource_id == datasource.id).all()
    for tbl in existing_db_tables:
        table_key = (tbl.schema_name, tbl.table_name)
        existing_tables_map[table_key] = {
            "db_object": tbl,
            "columns": {col.column_name: col for col in tbl.columns} # Assuming 'columns' is the relationship name
        }

    # 2. Get Raw Tables from Source
    try:
        raw_tables_from_source = get_sqlserver_metadata(
            ds_details=datasource_schema_for_util,
            password_override=datasource.db_password, # Make sure datasource.db_password is decrypted if needed here
            object_type='TABLES'
        )
    except Exception as e:
        # Consider logging the error instead of print
        # print(f"Error during get_sqlserver_metadata (TABLES) for datasource {datasource.id}: {e}")
        raise ConnectionError(f"Failed to fetch tables from data source '{datasource.name}': {e}")

    # (Step 2 of instructions: Remove delete_existing_metadata_for_datasource call - it's removed)

    tables_processed_count = 0 # Counts tables processed (created or updated)
    columns_processed_count = 0 # Counts columns processed (created or updated)
    new_tables_count = 0
    new_columns_count = 0

    # 3. Process Source Tables
    for raw_table_info in raw_tables_from_source:
        table_schema_name = raw_table_info.get('TABLE_SCHEMA')
        table_name_db = raw_table_info.get('TABLE_NAME')
        if not table_name_db:
            # print(f"Skipping table with no name: {raw_table_info}") # Consider logging
            continue

        table_key = (table_schema_name, table_name_db)
        db_table: Optional[DataTable] = None # Initialize db_table

        if table_key in existing_tables_map:
            # Table exists, get its DB object
            db_table = existing_tables_map[table_key]["db_object"]
            # No source-derived fields on DataTable itself to update in this design,
            # but is_active_for_sync and description are preserved by not touching them.
        else:
            # Table is new, create it
            db_table = DataTable(
                datasource_id=datasource.id,
                table_name=table_name_db,
                schema_name=table_schema_name
                # is_active_for_sync defaults to False in model
                # description defaults to None in model
            )
            db.add(db_table)
            db.flush() # Flush to get db_table.id for new columns
            new_tables_count += 1

        tables_processed_count +=1

        if not db_table: # Should not happen if logic is correct
            # print(f"Error: db_table not set for {table_key}") # Consider logging
            continue

        # 4. Process Source Columns for the current table
        existing_columns_for_table_map = existing_tables_map.get(table_key, {}).get("columns", {})

        try:
            raw_columns_from_source = get_sqlserver_metadata(
                ds_details=datasource_schema_for_util,
                password_override=datasource.db_password, # Ensure decrypted password
                object_type='COLUMNS',
                schema_name=table_schema_name,
                table_name=table_name_db
            )
        except Exception as e:
            # print(f"Error fetching columns for {table_key} (Datasource ID: {datasource.id}): {e}") # Log this
            # Decide if sync should continue for other tables or rollback/raise. For now, skip this table's columns.
            continue

        for raw_col_info in raw_columns_from_source:
            column_name = raw_col_info.get('COLUMN_NAME')
            if not column_name:
                # print(f"Skipping column with no name for table {table_key}: {raw_col_info}") # Log this
                continue

            db_col: Optional[DataColumn] = None # Initialize db_col

            if column_name in existing_columns_for_table_map:
                # Column exists, get its DB object
                db_col = existing_columns_for_table_map[column_name]
                # Update source-derived fields
                db_col.data_type = raw_col_info.get('DATA_TYPE', db_col.data_type) # Keep old if new is None
                is_nullable_str = raw_col_info.get('IS_NULLABLE', 'YES')
                db_col.is_nullable = True if is_nullable_str is None else (is_nullable_str.upper() == 'YES')
                db_col.max_length = raw_col_info.get('CHARACTER_MAXIMUM_LENGTH', db_col.max_length)
                # db_col.description is preserved by not touching it.
                # db_col.ordinal_position could be updated if available and desired
            else:
                # Column is new, create it
                is_nullable_str = raw_col_info.get('IS_NULLABLE', 'YES')
                is_nullable_bool = True if is_nullable_str is None else (is_nullable_str.upper() == 'YES')
                db_col = DataColumn(
                    table_id=db_table.id, # Assign to current table
                    column_name=column_name,
                    data_type=raw_col_info.get('DATA_TYPE', 'UNKNOWN'),
                    is_nullable=is_nullable_bool,
                    max_length=raw_col_info.get('CHARACTER_MAXIMUM_LENGTH')
                    # description defaults to None in model
                )
                db.add(db_col)
                new_columns_count +=1

            columns_processed_count += 1

    # 5. Handling Tables/Columns No Longer in Source (Phase 1: No Deletion)
    # As per requirements, items not found in source are not deleted or marked stale in this phase.

    db.commit()
    return {
        "tables_processed": tables_processed_count,
        "columns_processed": columns_processed_count,
        "new_tables_created": new_tables_count,
        "new_columns_created": new_columns_count,
        "message": "Metadata sync complete. User-defined fields preserved."
    }

def update_table_activation_status(db: Session, table_id: int, is_active: bool) -> Optional[DataTable]:
    db_table = db.query(DataTable).filter(DataTable.id == table_id).first()
    if db_table:
        db_table.is_active_for_sync = is_active
        db.add(db_table)
        db.commit()
        db.refresh(db_table)
    return db_table
