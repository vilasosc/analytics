import pyarrow as pa
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from app.models.metadata import DataColumn # Adjusted import path

logger = logging.getLogger(__name__)

SQL_TO_PYARROW_TYPE_MAP: Dict[str, Any] = {
    "bigint": pa.int64(),
    "int": pa.int32(),
    "smallint": pa.int16(),
    "tinyint": pa.uint8(),
    "bit": pa.bool_(),
    "decimal": lambda p, s: pa.decimal128(p if p is not None and p > 0 else 18, s if s is not None else 0),
    "numeric": lambda p, s: pa.decimal128(p if p is not None and p > 0 else 18, s if s is not None else 0),
    "money": pa.decimal128(19, 4),
    "smallmoney": pa.decimal128(10, 4),
    "float": pa.float64(),
    "real": pa.float32(),
    "datetime": pa.timestamp('us'),
    "datetime2": pa.timestamp('ns'),
    "smalldatetime": pa.timestamp('s'),
    "date": pa.date32(), # days from epoch
    "time": pa.time64('ns'),
    "datetimeoffset": pa.timestamp('ns', tz='UTC'),
    "char": pa.string(),
    "varchar": pa.string(),
    "text": pa.string(),
    "nchar": pa.string(),
    "nvarchar": pa.string(),
    "ntext": pa.string(),
    "binary": pa.binary(),
    "varbinary": pa.binary(),
    "image": pa.binary(),
    "uniqueidentifier": pa.string(),
    "sql_variant": pa.binary(), # Safest default
    "xml": pa.string(),
    "json": pa.string(), # SQL Server 2016+
    "rowversion": pa.binary(8), # Specific SQL Server type often named 'timestamp'
    "geometry": pa.binary(),   # WKB representation
    "geography": pa.binary(),  # WKB representation
    "hierarchyid": pa.binary(),
}

def sql_type_to_pyarrow_type(
    sql_type_name: str,
    precision: Optional[int] = None,
    scale: Optional[int] = None,
    char_max_length: Optional[int] = None # Currently not used for pa.string() or pa.binary() in this map
) -> pa.DataType: # Changed return type to non-optional, will always return a type (string as fallback)
    sql_type_name_lower = sql_type_name.lower()

    # Handle SQL Server's "timestamp" type which is an alias for "rowversion"
    if sql_type_name_lower == "timestamp":
        logger.debug("Mapping SQL Server 'timestamp' (rowversion type) to pa.binary(8)")
        return pa.binary(8)

    mapper = SQL_TO_PYARROW_TYPE_MAP.get(sql_type_name_lower)

    if mapper:
        if callable(mapper): # For types like decimal that need precision/scale
            if sql_type_name_lower in ["decimal", "numeric"]:
                effective_precision = precision if precision is not None and precision > 0 else 18
                effective_scale = scale if scale is not None else 0
                if effective_scale < 0: effective_scale = 0 # Scale cannot be negative
                if effective_precision <= 0: effective_precision = 18 # Default if invalid
                if effective_scale > effective_precision: effective_scale = effective_precision
                return mapper(effective_precision, effective_scale)
            else: # Should not happen with current map, but future-proof
                return mapper()
        else: # Direct type mapping
            return mapper
    else:
        logger.warning(f"Unsupported SQL Server data type '{sql_type_name}' for PyArrow conversion. Defaulting to pa.string().")
        return pa.string()

def get_pyarrow_schema_from_model(db_columns: List[DataColumn]) -> Optional[pa.Schema]:
    """
    Constructs a PyArrow Schema from a list of DataColumn SQLAlchemy model instances.
    """
    if not db_columns:
        logger.error("No column metadata provided. Cannot generate PyArrow schema.")
        return None

    fields = []
    for col_model in db_columns:
        # These attributes (numeric_precision, numeric_scale, etc.) would ideally be on the DataColumn model.
        # They would be populated during metadata sync (Epic 3) from INFORMATION_SCHEMA.COLUMNS.
        # For now, we pass None, and sql_type_to_pyarrow_type uses defaults.
        # This is a known limitation from the Epic 3 plan not storing these.
        # TODO: Enhance DataColumn model and metadata sync to include these details for accurate type mapping.
        db_column_precision = None # Placeholder: getattr(col_model, 'numeric_precision', None)
        db_column_scale = None     # Placeholder: getattr(col_model, 'numeric_scale', None)
        db_char_max_length = col_model.max_length # max_length is available on DataColumn

        arrow_type = sql_type_to_pyarrow_type(
            sql_type_name=col_model.data_type,
            precision=db_column_precision,
            scale=db_column_scale,
            char_max_length=db_char_max_length
        )

        fields.append(pa.field(col_model.column_name, arrow_type, nullable=col_model.is_nullable))

    if not fields: # Should not happen if db_columns is not empty and default type is pa.string()
        logger.error("No fields could be mapped to PyArrow. Returning empty schema.")
        return pa.schema([])

    return pa.schema(fields)

if __name__ == '__main__':
    print("--- PyArrow Type Mapping Self-Tests ---")
    # (Self-tests from previous attempt would go here)
    # Example:
    # print(f"int -> {sql_type_to_pyarrow_type('int')}")
    # print(f"decimal(10,2) -> {sql_type_to_pyarrow_type('decimal', 10, 2)}")
    # print(f"VARCHAR(MAX) -> {sql_type_to_pyarrow_type('varchar')}")
    # print(f"timestamp (SQL Server rowversion) -> {sql_type_to_pyarrow_type('timestamp')}")
    pass
EOF

# Explicitly add the file to git staging area
git add backend/app/utils/type_mapper.py
