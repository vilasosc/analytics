// shared/types.ts

export interface User {
  id: number | string; // Using string if UUIDs are planned, number for simple DB IDs
  email: string;
  role?: 'Admin' | 'Analyst' | 'Viewer'; // Optional for now, roles defined in PRD
  // Add other user-related fields as they become clear
}

export enum DataSourceType {
  SQLSERVER = 'SQLSERVER',
  POSTGRESQL = 'POSTGRESQL', // Future
  MYSQL = 'MYSQL',         // Future
  ORACLE = 'ORACLE'        // Future
}

export interface DataSource {
  id: number | string;
  name: string;
  type: DataSourceType;
  // Connection details might be sensitive and handled differently,
  // but for a shared type, we can define what's expected.
  host?: string;
  port?: number;
  username?: string;
  // password will not be part of shared types sent to client
  dbName?: string;
  createdAt: string; // ISO date string
  updatedAt: string; // ISO date string
}

// Add other shared types/enums as needed by the PRD's MVP scope
