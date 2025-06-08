import pyodbc
import pyarrow as pa
import pyarrow.parquet as pq
import logging
import os
from typing import Iterator, Optional, Tuple, Any, List, Dict

logger = logging.getLogger(__name__)

def _get_column_data_for_batch(raw_rows: List[tuple], column_index: int, target_type: pa.DataType) -> List[Any]:
    """Helper to extract data for a single column in a batch. Placeholder for future casting if needed."""
    # This is simplified; in a robust system, you might need explicit casting here
    # based on target_type, especially for dates, times, decimals if pyodbc doesn't map them perfectly.
    return [row[column_index] for row in raw_rows]

def _rows_to_record_batch(raw_rows: List[tuple], schema: pa.Schema) -> Optional[pa.RecordBatch]:
    """Converts a list of raw row tuples (from pyodbc) to a PyArrow RecordBatch."""
    if not raw_rows:
        return None

    try:
        batch_data_arrays = []
        if not schema or len(schema.types) == 0:
            logger.error("Cannot convert rows to RecordBatch: PyArrow schema is empty or not provided.")
            return None

        num_columns_in_schema = len(schema.types)
        if raw_rows and len(raw_rows[0]) != num_columns_in_schema:
            logger.error(f"Schema column count ({num_columns_in_schema}) does not match data row column count ({len(raw_rows[0])}).")
            # This often happens if SELECT * is used and schema is based on different column set/order.
            # For now, we'll attempt to proceed but this is a common source of errors.
            # Consider only taking min(len(raw_rows[0]), num_columns_in_schema) columns.

        for i, field in enumerate(schema):
            if i >= len(raw_rows[0]): # Safety break if data has fewer columns than schema
                logger.warning(f"Data row has fewer columns than schema. Stopping at column index {i-1} for schema field {field.name}.")
                # Pad with nulls or raise error? For now, this will likely lead to errors in from_arrays.
                # It's better to ensure SELECT query matches schema.
                break

            column_values = _get_column_data_for_batch(raw_rows, i, field.type)
            try:
                # PyArrow will attempt to cast data to the type specified in the schema field.
                arrow_array = pa.array(column_values, type=field.type, safe=False) # safe=False can be faster but less error checking
                batch_data_arrays.append(arrow_array)
            except Exception as e_col:
                logger.error(f"Error converting column '{field.name}' (index {i}, type {field.type}) to PyArrow array: {e_col}. First 100 chars of values: {str(column_values)[:100]}...", exc_info=True)
                raise # Propagate error to be handled by caller

        return pa.RecordBatch.from_arrays(batch_data_arrays, schema=schema)
    except Exception as e:
        logger.error(f"Failed to convert rows to RecordBatch: {e}", exc_info=True)
        return None # Or raise e to be handled by caller


def extract_data_from_sql_server_full(
    conn_str: str,
    schema_name: str,
    table_name: str,
    pyarrow_schema: pa.Schema, # The PyArrow schema to map to
    chunk_size: int = 10000
) -> Iterator[Union[pa.RecordBatch, str]]: # Yields RecordBatch or error string
    if not (schema_name.replace('_', '').isalnum() and table_name.replace('_', '').isalnum()):
        err_msg = f"Error: Invalid schema or table name '{schema_name}.{table_name}' for full extraction."
        logger.error(err_msg)
        yield err_msg
        return

    # Constructing column list from PyArrow schema to ensure SELECT order matches schema order
    if not pyarrow_schema or len(pyarrow_schema.names) == 0:
        err_msg = f"Error: PyArrow schema is empty or not provided for table {schema_name}.{table_name}."
        logger.error(err_msg)
        yield err_msg
        return

    select_columns = ", ".join([f"[{col_name}]" for col_name in pyarrow_schema.names])
    query = f"SELECT {select_columns} FROM [{schema_name}].[{table_name}];"

    try:
        with pyodbc.connect(conn_str, timeout=60) as conn: # Increased timeout
            with conn.cursor() as cursor:
                logger.info(f"Executing full data extraction for {schema_name}.{table_name}: {query}")
                cursor.execute(query)

                while True:
                    raw_rows = cursor.fetchmany(chunk_size)
                    if not raw_rows:
                        break

                    record_batch = _rows_to_record_batch(raw_rows, pyarrow_schema)
                    if record_batch:
                        yield record_batch
                    elif record_batch is None and raw_rows: # Failed conversion for non-empty rows
                        err_msg = f"Error: Failed to convert data chunk to RecordBatch for {schema_name}.{table_name}."
                        logger.error(err_msg)
                        yield err_msg
                        return # Stop further processing for this table
                logger.info(f"Finished extracting data for {schema_name}.{table_name}")

    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        err_msg = f"Error: SQL Server connection/query error (full extr.) for {schema_name}.{table_name}: {sqlstate} - {str(ex)}"
        logger.error(err_msg)
        yield err_msg
    except Exception as e:
        err_msg = f"Error: Unexpected error (full extr.) for {schema_name}.{table_name}: {str(e)}"
        logger.error(err_msg, exc_info=True)
        yield err_msg


def extract_data_from_sql_server_incremental(
    conn_str: str,
    schema_name: str,
    table_name: str,
    watermark_column: str,
    last_watermark_value: Any,
    pyarrow_schema: pa.Schema, # PyArrow schema for column ordering and type mapping
    chunk_size: int = 10000
) -> Iterator[Union[pa.RecordBatch, str]]: # Yields RecordBatch or error string
    if not (schema_name.replace('_', '').isalnum() and \
            table_name.replace('_', '').isalnum() and \
            watermark_column.replace('_', '').isalnum()):
        err_msg = "Error: Invalid schema, table, or watermark column name for incremental extraction."
        logger.error(err_msg)
        yield err_msg
        return

    if not pyarrow_schema or len(pyarrow_schema.names) == 0:
        err_msg = f"Error: PyArrow schema is empty or not provided for incremental sync of table {schema_name}.{table_name}."
        logger.error(err_msg)
        yield err_msg
        return

    select_columns = ", ".join([f"[{col_name}]" for col_name in pyarrow_schema.names])
    query = f"SELECT {select_columns} FROM [{schema_name}].[{table_name}] WHERE [{watermark_column}] > ? ORDER BY [{watermark_column}];"

    try:
        with pyodbc.connect(conn_str, timeout=60) as conn: # Increased timeout
            with conn.cursor() as cursor:
                logger.info(f"Executing incremental extraction for {schema_name}.{table_name} (watermark > {last_watermark_value} on [{watermark_column}]): {query}")
                try:
                    cursor.execute(query, last_watermark_value)
                except pyodbc.Error as ex_query:
                    err_msg = f"Error executing incremental query for {schema_name}.{table_name} (Watermark: '{last_watermark_value}', Column: '{watermark_column}'): {ex_query}"
                    logger.error(err_msg, exc_info=True)
                    yield err_msg
                    return

                while True:
                    raw_rows = cursor.fetchmany(chunk_size)
                    if not raw_rows:
                        break

                    record_batch = _rows_to_record_batch(raw_rows, pyarrow_schema)
                    if record_batch:
                        yield record_batch
                    elif record_batch is None and raw_rows:
                        err_msg = f"Error: Failed to convert incremental data chunk to RecordBatch for {schema_name}.{table_name}."
                        logger.error(err_msg)
                        yield err_msg
                        return
                logger.info(f"Finished incremental extraction for {schema_name}.{table_name}")

    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        err_msg = f"Error: SQL Server error (incr. extr.) for {schema_name}.{table_name}: {sqlstate} - {str(ex)}"
        logger.error(err_msg)
        yield err_msg
    except Exception as e:
        err_msg = f"Error: Unexpected error (incr. extr.) for {schema_name}.{table_name}: {str(e)}"
        logger.error(err_msg, exc_info=True)
        yield err_msg


def write_record_batches_to_parquet(
    record_batch_iterator: Iterator[Union[pa.RecordBatch, str]],
    file_path: str,
    schema: pa.Schema
) -> Tuple[int, Optional[str]]:
    total_records_written = 0
    error_message: Optional[str] = None

    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            logger.info(f"Ensured directory exists: {dir_name}")

        # Check the first item from iterator without consuming it from the main loop if it's a batch
        first_item_or_error = next(record_batch_iterator, None)
        if first_item_or_error is None: # Iterator is empty
            logger.info(f"No data to write to Parquet file: {file_path}. 0 records written.")
            return 0, None
        if isinstance(first_item_or_error, str) and first_item_or_error.startswith("Error:"):
            logger.error(f"Received error string from iterator, stopping Parquet write: {first_item_or_error}")
            return 0, first_item_or_error

        # If we are here, first_item_or_error is a valid RecordBatch.
        with pq.ParquetWriter(file_path, schema) as writer:
            # Write the first batch
            writer.write_batch(first_item_or_error)
            total_records_written += len(first_item_or_error)
            logger.debug(f"Wrote first batch with {len(first_item_or_error)} records to {file_path}. Total written: {total_records_written}")

            # Write remaining batches
            for batch_idx, batch_or_error in enumerate(record_batch_iterator, start=1):
                if isinstance(batch_or_error, str) and batch_or_error.startswith("Error:"):
                    error_message = batch_or_error
                    logger.error(f"Received error string from iterator at batch {batch_idx}, stopping Parquet write: {error_message}")
                    break # Stop writing further batches

                if not isinstance(batch_or_error, pa.RecordBatch):
                    error_message = f"Invalid data type {type(batch_or_error)} received by Parquet writer at batch {batch_idx}."
                    logger.error(error_message)
                    break

                writer.write_batch(batch_or_error)
                total_records_written += len(batch_or_error)
                logger.debug(f"Wrote batch {batch_idx} with {len(batch_or_error)} records to {file_path}. Total written: {total_records_written}")

        if error_message:
             logger.warning(f"Parquet writing completed with an error for {file_path}. Records written: {total_records_written}.")
        else:
            logger.info(f"Successfully wrote {total_records_written} records to Parquet file: {file_path}")

    except Exception as e:
        error_msg = f"Error writing to Parquet file {file_path}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        error_message = error_msg
        # Attempt to clean up partially written file if an error occurs during writer operation
        if os.path.exists(file_path) and error_message: # Only remove if error occurred
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up Parquet file due to error: {file_path}")
            except OSError as e_remove:
                logger.error(f"Failed to clean up Parquet file {file_path}: {e_remove}")

    return total_records_written, error_message
