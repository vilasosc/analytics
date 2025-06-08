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

def fetch_all_data_from_table(
    ds_details: DataSourceBase,
    password_override: str,
    schema_name: str,
    table_name: str
) -> List[Dict[str, Any]]:

    details_with_pw = _get_details_with_password(ds_details, password_override)
    conn_str = build_connection_string(details_with_pw)

    rows_data: List[Dict[str, Any]] = []

    # Basic sanitization/validation for schema and table names
    # Ensure schema_name defaults to 'dbo' if not provided or empty, which is a common default.
    effective_schema_name = schema_name if schema_name else 'dbo'

    # Validate characters to prevent SQL injection through object names.
    # Allowing underscores as they are common in names.
    if not table_name.replace('_','').isalnum() or not effective_schema_name.replace('_','').isalnum():
        raise ValueError("Table and schema names must consist of alphanumeric characters and underscores only.")

    # Use pyodbc parameters for table and schema names if possible, though direct f-string formatting for
    # FROM clause is common. Here, we are embedding them, guarded by the validation above.
    sql_query = f"SELECT * FROM [{effective_schema_name}].[{table_name}]"

    try:
        with pyodbc.connect(conn_str, timeout=10) as conn: # Connection timeout
            with conn.cursor() as cursor:
                # It's generally safer to set a query timeout if the DB operation might hang
                # cursor.settimeout(30) # Example: 30 seconds query timeout - specific to some drivers/dbapis
                # pyodbc cursor itself doesn't have a settimeout. Timeout is on connect() or connection.timeout
                conn.timeout = 30 # Set execution timeout on the connection for operations

                cursor.execute(sql_query)
                columns = [column[0] for column in cursor.description]

                if not columns: # No columns found, likely table is empty or doesn't exist as expected
                    return []

                for row in cursor.fetchall():
                    rows_data.append(dict(zip(columns, row)))
    except pyodbc.Error as ex:
        # More detailed error logging
        sqlstate = ex.args[0] if ex.args and len(ex.args) > 0 else "Unknown"
        error_message = str(ex)
        print(f"SQL Server Error extracting data from {effective_schema_name}.{table_name}. SQLSTATE: {sqlstate}. Message: {error_message}")
        # Depending on policy, you might want to raise a custom, more generic error
        # or re-raise the original pyodbc.Error. For now, re-raising.
        raise
    except Exception as e:
        print(f"Unexpected error extracting data from {effective_schema_name}.{table_name}: {e}")
        raise # Re-raise unexpected errors
    return rows_data


def fetch_table_preview_data(
    ds_details: DataSourceBase,
    password_override: str,
    schema_name: Optional[str],
    table_name: str,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Fetches a limited number of rows from a specified table for preview.
    Returns a dictionary containing column names and rows.
    """
    if not table_name:
        raise ValueError("Table name cannot be empty.")
    if limit <= 0:
        raise ValueError("Limit must be a positive integer.")

    details_with_pw = _get_details_with_password(ds_details, password_override)
    conn_str = build_connection_string(details_with_pw)
    preview_data = {"columns": [], "rows": [], "actual_row_count": 0}

    try:
        with pyodbc.connect(conn_str, timeout=10) as conn: # Added connection timeout
            with conn.cursor() as cursor:
                conn.timeout = 20 # Set execution timeout on the connection (e.g., 20 seconds)

                # Construct safe table and schema name for query
                safe_table_name = table_name.replace("]", "]]") # Basic escaping for brackets

                # Effective schema name (defaults to 'dbo' if None or empty, common for SQL Server)
                effective_schema = schema_name if schema_name else 'dbo'
                safe_schema_name = effective_schema.replace("]", "]]")

                # Formulate query using TOP for limit
                # Ensure schema and table are properly quoted to handle special characters/reserved words
                query = f"SELECT TOP ({limit}) * FROM [{safe_schema_name}].[{safe_table_name}]" # Ensure TOP is parenthesized for some SQL Server versions if limit is a variable, though direct int is usually fine.

                cursor.execute(query)

                columns = [column[0] for column in cursor.description] if cursor.description else []
                preview_data["columns"] = columns

                rows_fetched = 0
                if columns: # Only proceed if columns were found
                    for row in cursor.fetchall(): # fetchall() respects the TOP clause
                        preview_data["rows"].append(dict(zip(columns, row)))
                        rows_fetched += 1
                preview_data["actual_row_count"] = rows_fetched

    except pyodbc.Error as ex:
        sqlstate = ex.args[0] if ex.args and len(ex.args) > 0 else "Unknown"
        error_message = str(ex)
        # Basic error classification, can be expanded
        if sqlstate in ('08001', '08003', '08004', '08S01'): # Connection related errors
            raise ConnectionError(f"Connection failed to SQL Server: {error_message}")
        elif sqlstate in ('42S02', '3F000'): # Table or schema not found (42S02), Invalid schema name (3F000)
            raise ValueError(f"Table or schema not found: [{effective_schema}].[{table_name}]. Error: {error_message}")
        else: # Other database errors
            raise ValueError(f"Database error fetching preview for table [{effective_schema}].[{table_name}]: {error_message}")
    except Exception as e: # Catch any other unexpected errors
        raise RuntimeError(f"An unexpected error occurred while fetching table preview: {e}")

    return preview_data
