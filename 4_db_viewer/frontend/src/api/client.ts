// API 呼叫封裝。型別全部來自 types.ts（由後端 OpenAPI 產生，勿手改）。
import { ref } from 'vue';
import type { components } from './types';

type Schemas = components['schemas'];

export type FormSummary = Schemas['FormSummary'];
export type FormDetail = Schemas['FormDetail'];
export type FormField = Schemas['FormField'];
export type FormUsage = Schemas['FormUsage'];
export type ProcessSummary = Schemas['ProcessSummary'];
export type ProcessDetail = Schemas['ProcessDetail'];
export type Activity = Schemas['Activity'];
export type ActivityPermission = Schemas['ActivityPermission'];
export type Matrix = Schemas['Matrix'];
export type MatrixRow = Schemas['MatrixRow'];
export type Health = Schemas['Health'];
export type SearchResult = Schemas['SearchResult'];
export type SearchHit = Schemas['SearchHit'];
export type HostOption = Schemas['HostOption'];
export type Permission = NonNullable<ActivityPermission['permission']>;

export type PermissionItem = Schemas['PermissionItem'];
// DISABLE 不是存進資料庫的值，而是把元件從權限字串中移除（設計師顯示「唯讀」）。
// 後端是 Literal 型別別名，不會單獨出現在 schemas，故由 PermissionItem 推導。
export type WritablePermission = PermissionItem['permission'];
export type PermissionPreview = Schemas['PermissionPreview'];
export type PermissionChange = Schemas['PermissionChange'];
export type PermissionApplyResult = Schemas['PermissionApplyResult'];

export const WRITABLE_VALUES: WritablePermission[] = [
  'ENABLED', 'INVISIBLE', 'FULL_CONTROL', 'DISABLE',
];

export const PERMISSION_LABELS: Record<string, string> = {
  ENABLED: '可編輯(Enable)',
  INVISIBLE: '隱藏(Invisible)',
  FULL_CONTROL: '完全控制',
  DISABLE: '唯讀(Disable)',
};

/**
 * 目前選定的資料庫主機。所有請求都會自動帶上，後端無伺服器端狀態，
 * 兩台的快取也各自獨立。存進 localStorage 讓重新整理後保持選擇。
 */
const HOST_STORAGE_KEY = 'bpm-viewer-host';
export const activeHost = ref<string>(
  window.localStorage.getItem(HOST_STORAGE_KEY) ?? '');

export function setActiveHost(key: string) {
  activeHost.value = key;
  window.localStorage.setItem(HOST_STORAGE_KEY, key);
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

interface RequestOptions {
  params?: Record<string, unknown>;
  method?: 'GET' | 'POST' | 'PATCH';
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, method = 'GET', body } = options;
  const url = new URL(path, window.location.origin);
  if (activeHost.value) url.searchParams.set('host', activeHost.value);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError('無法連線到後端，請確認 uvicorn 是否已啟動（預設 :8000）', 0);
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // 回應不是 JSON 就沿用狀態碼描述
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

const permissionsPath = (processId: string, activityId: string) =>
  `/api/processes/${encodeURIComponent(processId)}/activities/`
  + `${encodeURIComponent(activityId)}/permissions`;

export const api = {
  health: () => request<Health>('/api/health'),
  listForms: (keyword = '') =>
    request<FormSummary[]>('/api/forms', { params: { keyword, limit: 1000 } }),
  getForm: (formId: string) => request<FormDetail>(`/api/forms/${encodeURIComponent(formId)}`),
  getFormUsage: (formId: string) =>
    request<FormUsage[]>(`/api/forms/${encodeURIComponent(formId)}/usage`),
  listProcesses: (keyword = '') =>
    request<ProcessSummary[]>('/api/processes', { params: { keyword, limit: 1000 } }),
  getProcess: (processId: string) =>
    request<ProcessDetail>(`/api/processes/${encodeURIComponent(processId)}`),
  getMatrix: (processId: string, only = 'all') =>
    request<Matrix>(`/api/processes/${encodeURIComponent(processId)}/matrix`,
      { params: { only } }),
  search: (q: string, includeFields = false) =>
    request<SearchResult>('/api/search', { params: { q, include_fields: includeFields } }),

  // --- 寫入（後端未開旗標時這些路徑不存在，會回 404/405）---
  previewPermissions: (processId: string, activityId: string, items: PermissionItem[]) =>
    request<PermissionPreview>(`${permissionsPath(processId, activityId)}/preview`,
      { method: 'POST', body: { items } }),
  applyPermissions: (processId: string, activityId: string,
                     items: PermissionItem[], token: string) =>
    request<PermissionApplyResult>(permissionsPath(processId, activityId),
      { method: 'PATCH', body: { items, token } }),
  restoreBackup: (backupId: string) =>
    request<{ restored: boolean; backup_id: string; perm_oid: string }>(
      `/api/write/restore/${encodeURIComponent(backupId)}`, { method: 'POST' }),
};
