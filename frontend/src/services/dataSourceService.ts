import axios from 'axios';
import { DataSource, DataSourceType } from '../../../shared/types'; // Assuming shared types are updated/correct

const API_BASE_URL = 'http://localhost:8000/api/v1'; // Adjust if your backend URL is different

// Define interfaces based on backend Pydantic models if not fully covered by shared/types.ts
// These might be more specific for request/response than the generic DataSource from shared/types
export interface DataSourceCreate {
  name: string;
  type: DataSourceType;
  db_host?: string;
  db_port?: number;
  db_name?: string;
  db_username?: string;
  db_password?: string; // Password will be sent for creation/update
}

export interface DataSourceUpdate extends Partial<DataSourceCreate> {}

export interface DataSourceResponse extends DataSource {
  // Backend's DataSourceResponse includes id, createdAt, updatedAt
  // and sensitive fields like db_password are typically excluded or handled carefully.
  // The shared/types.ts DataSource should ideally match this response structure.
}

export interface TestConnectionRequest extends DataSourceCreate {}

export interface TestConnectionResponse {
  message: string;
  connected: boolean;
}

const dataSourceService = {
  getAllDataSources: async (): Promise<DataSourceResponse[]> => {
    const response = await axios.get<DataSourceResponse[]>(`${API_BASE_URL}/datasources`);
    return response.data;
  },

  getDataSourceById: async (id: number | string): Promise<DataSourceResponse> => {
    const response = await axios.get<DataSourceResponse>(`${API_BASE_URL}/datasources/${id}`);
    return response.data;
  },

  createDataSource: async (data: DataSourceCreate): Promise<DataSourceResponse> => {
    const response = await axios.post<DataSourceResponse>(`${API_BASE_URL}/datasources`, data);
    return response.data;
  },

  updateDataSource: async (id: number | string, data: DataSourceUpdate): Promise<DataSourceResponse> => {
    const response = await axios.put<DataSourceResponse>(`${API_BASE_URL}/datasources/${id}`, data);
    return response.data;
  },

  deleteDataSource: async (id: number | string): Promise<void> => {
    await axios.delete(`${API_BASE_URL}/datasources/${id}`);
  },

  testDataSourceConnection: async (data: TestConnectionRequest): Promise<TestConnectionResponse> => {
    const response = await axios.post<TestConnectionResponse>(`${API_BASE_URL}/datasources/test_connection`, data);
    return response.data;
  },
};

export default dataSourceService;
