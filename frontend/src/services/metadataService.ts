import axios from 'axios';
// Assuming shared types might eventually have some of these, but defining locally for now.
// Based on backend schemas.

const API_BASE_URL = 'http://localhost:8000/api/v1'; // Adjust if your backend URL is different

export interface DataTableColumnResponse {
  name: string;
  data_type: string;
  is_nullable: boolean;
  // Add other properties if available from backend like constraints, etc.
}

export interface DataTableResponse {
  id: number;
  datasource_id: number;
  name: string;
  schema_name?: string;
  description?: string;
  row_count?: number;
  column_count?: number;
  is_active_for_sync: boolean;
  columns: DataTableColumnResponse[];
  created_at: string; // ISO date string
  updated_at: string; // ISO date string
}

export interface MetadataSyncRequest {
  datasource_id: number;
}

export interface MetadataSyncResult {
  datasource_id: number;
  tables_discovered: number;
  tables_updated: number;
  new_tables_added: number;
  status: string; // e.g., "Completed", "Failed"
  message?: string;
}

export interface TableActivationRequest {
  is_active: boolean;
}

export interface TablePreviewDataRow {
  [columnName: string]: any; // Rows are dictionaries of column_name: value
}
export interface TablePreviewResponse {
  table_id: number;
  table_name: string;
  columns: string[]; // List of column names in order
  rows: TablePreviewDataRow[];
  row_count_total: number; // Total rows in the actual table
  row_count_preview: number; // Number of rows in this preview
  is_preview_limited: boolean;
}


const metadataService = {
  getTablesForDataSource: async (datasourceId: number | string): Promise<DataTableResponse[]> => {
    const response = await axios.get<DataTableResponse[]>(`${API_BASE_URL}/metadata/datasources/${datasourceId}/tables`);
    return response.data;
  },

  triggerMetadataSync: async (datasourceId: number | string): Promise<MetadataSyncResult> => {
    const requestData: MetadataSyncRequest = { datasource_id: Number(datasourceId) };
    const response = await axios.post<MetadataSyncResult>(`${API_BASE_URL}/metadata/sync`, requestData);
    return response.data;
  },

  setTableActivation: async (tableId: number | string, isActive: boolean): Promise<DataTableResponse> => {
    const requestData: TableActivationRequest = { is_active: isActive };
    const response = await axios.patch<DataTableResponse>(`${API_BASE_URL}/metadata/tables/${tableId}/activation`, requestData);
    return response.data;
  },

  getTablePreview: async (tableId: number | string, limit: number = 20): Promise<TablePreviewResponse> => {
    const response = await axios.get<TablePreviewResponse>(`${API_BASE_URL}/metadata/tables/${tableId}/preview?limit=${limit}`);
    return response.data;
  },
};

export default metadataService;
