// 與後端 app/schemas.py 對應。後端的 Pydantic 模型是唯一真實來源，
// 這裡是手抄的對應型別（本專案未設 openapi-typescript 產生步驟）。

export interface HostInfo {
  key: string;
  label: string;
  address: string;
  production: boolean;
}

export interface MetaInfo {
  hosts: HostInfo[];
  defaultHost: string;
  maxExportRows: number;
  maxScanRows: number;
  fieldSampleRows: number;
}

export interface ProcessSummary {
  processId: string;
  processName: string;
  instanceCount: number;
  firstCreated?: string | null;
  lastCreated?: string | null;
}

export interface ProcessListResult {
  processes: ProcessSummary[];
  total: number;
}

export interface FieldInfo {
  id: string;
  name: string;
  type: string;
  named: boolean;
  source: string;
}

export interface GridColumn {
  id: string;
  name: string;
  named: boolean;
}

export interface GridInfo {
  id: string;
  name: string;
  columns: GridColumn[];
}

export interface FormMeta {
  formId: string;
  formName: string;
  version?: number | null;
  missing: boolean;
}

export interface FieldCatalog {
  processId: string;
  forms: FormMeta[];
  fields: FieldInfo[];
  grids: GridInfo[];
  sampled: number;
  parseFailures: number;
  labelCoverage: { named: number; total: number };
}

export interface FixedFilters {
  processSerialNumber: string;
  formSerialNumber: string;
  requester: string;
  subject: string;
  states: number[];
}

export interface CustomFilter {
  fieldId: string;
  value: string;
}

export interface SearchRequest {
  processId: string;
  startDate: string;
  endDate: string;
  filters: FixedFilters;
  customFilters: CustomFilter[];
  fieldIds: string[];
  page: number;
  pageSize: number;
}

export interface InstanceRow {
  processSerialNumber: string;
  formSerialNumber: string;
  processId: string;
  processName: string;
  formId: string;
  subject: string;
  state?: number | null;
  stateName: string;
  createdTime?: string | null;
  requesterId: string;
  requesterName: string;
  orgUnitId: string;
  orgUnitName: string;
  abortComment: string;
  abortedBy: string;
  parseError: string;
  values: Record<string, string>;
}

export interface SearchResult {
  rows: InstanceRow[];
  total: number;
  scanned: number;
  truncated: boolean;
  exact: boolean;
  note: string;
}

export interface WorkItemRow {
  workItemName: string;
  state?: number | null;
  stateName: string;
  createdTime?: string | null;
  completedTime?: string | null;
  performerId: string;
  performerName: string;
  comment: string;
}

export interface InstanceDetail {
  summary: InstanceRow;
  formId: string;
  fields: FieldInfo[];
  values: Record<string, string>;
  grids: Record<string, Record<string, string>[]>;
  workItems: WorkItemRow[];
  parseError: string;
}

export interface ExportRequest {
  processId: string;
  startDate: string;
  endDate: string;
  filters: FixedFilters;
  customFilters: CustomFilter[];
  fieldIds: string[];
  gridIds: string[];
  exportList: boolean;
  exportContent: boolean;
  exportSignatures: boolean;
}

export interface ExportPreview {
  matched: number;
  limit: number;
  exceeded: boolean;
  exact: boolean;
  note: string;
}
