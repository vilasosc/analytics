import pyodbc # To be added to requirements.txt
from app.schemas.datasource import DataSourceBase # For type hinting
from typing import Optional, List, Dict, Any

class DataSourceWithPassword(DataSourceBase): # Helper schema for functions needing password
    db_password: str

def _get_details_with_password(ds_details: DataSourceBase, password_override: Optional[str] = None) -> DataSourceWithPassword:
    # If ds_details is already DataSourceCreate (which has db_password), use it.
    # Otherwise, password_override must be provided or it's an issue.
    effective_password = password_override
    if effective_password is None:
        if hasattr(ds_details, 'db_password') and ds_details.db_password is not None:
            effective_password = ds_details.db_password
        else:
            # This case should ideally not happen if called correctly,
            # e.g. test_connection uses DataSourceCreate, or update passes existing password
            raise ValueError("Password must be provided for connection.")

    return DataSourceWithPassword(
        name=ds_details.name, type=ds_details.type, db_host=ds_details.db_host,
        db_port=ds_details.db_port, db_name=ds_details.db_name,
        db_username=ds_details.db_username, db_password=effective_password
    )

def build_connection_string(details_with_pw: DataSourceWithPassword) -> str:
    driver = "{ODBC Driver 17 for SQL Server}" # Assumption: driver is available
    return (
        f"DRIVER={driver};"
        f"SERVER={details_with_pw.db_host},{details_with_pw.db_port};"
        f"DATABASE={details_with_pw.db_name};"
        f"UID={details_with_pw.db_username};"
        f"PWD={details_with_pw.db_password};"
        f"TrustServerCertificate=yes;" # Review for prod
    )

def test_sqlserver_connection(ds_details: DataSourceBase, password_override: Optional[str] = None) -> bool:
    try:
        details_with_pw = _get_details_with_password(ds_details, password_override)
        conn_str = build_connection_string(details_with_pw)
        with pyodbc.connect(conn_str, timeout=5) as conn: # 5-second timeout
            return True
    except pyodbc.Error as ex:
        print(f"SQL Server Connection Error. SQLSTATE: {ex.args[0] if ex.args else 'Unknown'}. Message: {ex}")
        return False
    except ValueError as ve: # Catch password value errors from _get_details_with_password
        print(f"Configuration error for SQL Server connection: {ve}")
        return False
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred during SQL Server connection test: {e}")
        return False

def get_sqlserver_metadata(ds_details: DataSourceBase, password_override: Optional[str] = None, object_type: str = 'TABLES', schema_name: Optional[str] = None, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
    details_with_pw = _get_details_with_password(ds_details, password_override)
    conn_str = build_connection_string(details_with_pw)
    results: List[Dict[str, Any]] = []
    query = ""
    params: List[Any] = []

    if object_type == 'TABLES':
        query = "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_SCHEMA, TABLE_NAME;"
    elif object_type == 'COLUMNS' and schema_name and table_name:
        query = "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION;"
        params = [schema_name, table_name]
    else:
        raise ValueError(f"Invalid object_type '{object_type}' or missing parameters for COLUMNS.")

    try:
        with pyodbc.connect(conn_str, timeout=10) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            column_names = [desc[0] for desc in cursor.description] if cursor.description else []
            for row in cursor.fetchall():
                results.append(dict(zip(column_names, row)))
    except pyodbc.Error as ex:
        print(f"SQL Server Error (fetching {object_type}). SQLSTATE: {ex.args[0] if ex.args else 'Unknown'}. Message: {ex}")
        raise # Re-raise to be handled by the API layer
    except ValueError as ve: # Catch password value errors
        print(f"Configuration error during SQL Server metadata fetch: {ve}")
        raise
    except Exception as e:
        print(f"Unexpected error (fetching {object_type}): {e}")
        raise # Re-raise
    return results
