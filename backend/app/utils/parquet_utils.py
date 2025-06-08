import pyarrow as pa
import pyarrow.parquet as pq
import os
from typing import List, Dict, Any

def write_data_to_parquet(
    data: List[Dict[str, Any]],
    file_path: str
) -> None:
    if not data:
        print(f"Warning: No data provided for {file_path}. File not written.")
        return

    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory): # Check if directory string is not empty
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            print(f"Error creating directory {directory}: {e}")
            raise

    try:
        # PyArrow can infer schema from a list of Python dicts.
        # For robustness in production, explicit schema definition is better,
        # especially to handle nulls, specific data types, and consistency.
        # MVP: Rely on schema inference.
        table = pa.Table.from_pylist(data)
        pq.write_table(table, file_path, compression='snappy')

    except pa.ArrowException as ae:
        print(f"PyArrow error writing {file_path}: {ae}")
        raise
    except Exception as e:
        print(f"Unexpected error writing {file_path}: {e}")
        raise
