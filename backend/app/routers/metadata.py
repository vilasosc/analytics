from fastapi import APIRouter, Depends, HTTPException, status, Query # Added Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any # Added Dict, Any
from app.core.database import get_db
from app.crud import crud_datasource, crud_metadata
from app.schemas.metadata import ( # Expanded imports
    MetadataSyncResult, DataTableResponse, MetadataSyncRequest,
    TableActivationRequest, TablePreviewResponse
)
from app.schemas.datasource import DataSourceResponse as DataSourceSchemaResponse # For type hint in mock preview
# from app.core.auth import get_current_active_user # Placeholder
# from app.models.user import User # Placeholder

router = APIRouter()

@router.post("/sync", response_model=MetadataSyncResult, tags=["Metadata Sync"]) # Changed tag
def trigger_metadata_synchronization(sync_request: MetadataSyncRequest, db: Session = Depends(get_db)):
    # current_user: User = Depends(get_current_active_user) # Add auth later
    db_datasource = crud_datasource.get_datasource(db, datasource_id=sync_request.datasource_id)
    if not db_datasource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

    if db_datasource.type.value != "SQLSERVER":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Metadata sync is only supported for SQLSERVER, not {db_datasource.type.value}.")

    try:
        outcome = crud_metadata.sync_datasource_metadata(db=db, datasource=db_datasource)
        return MetadataSyncResult(datasource_id=db_datasource.id, **outcome)
    except ConnectionError as ce:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to data source: {ce}")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"Unexpected error during metadata sync for datasource {db_datasource.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred during metadata synchronization: {e}")

@router.get("/datasources/{datasource_id}/tables", response_model=List[DataTableResponse], tags=["Metadata Tables"]) # Changed tag
def list_tables_for_datasource(datasource_id: int, db: Session = Depends(get_db)):
    # current_user: User = Depends(get_current_active_user) # Add auth later
    db_datasource = crud_datasource.get_datasource(db, datasource_id=datasource_id)
    if not db_datasource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

    tables = crud_metadata.get_datatables_for_datasource(db=db, datasource_id=datasource_id)
    return tables

@router.patch("/tables/{table_id}/activation", response_model=DataTableResponse, tags=["Metadata Tables"])
def set_table_activation_status(
    table_id: int,
    activation_request: TableActivationRequest,
    db: Session = Depends(get_db)
    # current_user: User = Depends(get_current_active_user) # Auth
):
    db_table = crud_metadata.get_datatable(db, table_id=table_id)
    if not db_table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table metadata not found.")

    updated_table = crud_metadata.update_table_activation_status(
        db=db, table_id=table_id, is_active=activation_request.is_active_for_sync
    )
    if not updated_table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to update table activation status.") # Should be caught by get_datatable generally
    return updated_table

@router.get("/tables/{table_id}/preview", response_model=TablePreviewResponse, tags=["Metadata Tables"])
def preview_table_data(
    table_id: int,
    limit: int = Query(default=50, gt=0, le=100),
    db: Session = Depends(get_db)
    # current_user: User = Depends(get_current_active_user) # Auth
):
    db_table_meta = crud_metadata.get_datatable(db, table_id=table_id)
    if not db_table_meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table metadata not found.")

    # The db_table_meta.datasource relationship is used here.
    # SQLAlchemy will lazy-load it if not already loaded.
    db_datasource = db_table_meta.datasource
    if not db_datasource:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Datasource not found for table. Data integrity issue.")

    if db_datasource.type.value != "SQLSERVER":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data preview is currently only supported for SQLSERVER data sources.")

    try:
        # --- MOCK IMPLEMENTATION START (to be replaced by actual utility call) ---
        # This section simulates what fetch_table_preview_data_from_source would do.
        # It uses db_table_meta.columns for column names (lazy-loaded if not already).

        mock_columns = [col.column_name for col in db_table_meta.columns]
        mock_rows = []
        if mock_columns: # Only generate mock rows if columns exist
            for i in range(min(limit, 5)): # Generate a few mock rows up to limit (max 5 for this mock)
                row_data = {}
                for idx, col_name in enumerate(mock_columns):
                    row_data[col_name] = f"sample_data_{i+1}_{idx+1}"
                mock_rows.append(row_data)

        preview_data = {
            "columns": mock_columns,
            "rows": mock_rows,
            "actual_row_count": len(mock_rows)
        }
        # --- MOCK IMPLEMENTATION END ---

        return TablePreviewResponse(
            table_name=db_table_meta.table_name,
            schema_name=db_table_meta.schema_name,
            columns=preview_data["columns"],
            rows=preview_data["rows"],
            row_count=preview_data["actual_row_count"],
            is_preview_limited=preview_data["actual_row_count"] >= limit,
            limit=limit
        )

    except ConnectionError as ce: # Though mock doesn't connect, keep for future
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to source database: {str(ce)}")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"Unexpected error during table preview for table {table_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred during table preview: {str(e)}")
