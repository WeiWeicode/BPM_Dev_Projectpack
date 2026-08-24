// API 呼叫封裝。型別全部來自 types.ts（由後端 OpenAPI 產生，勿手改）。
import { ref } from 'vue';
import type { components } from './types';

type Schemas = components['schemas'];

export type HostOption = Schemas['HostOption'];
export type Health = Schemas['Health'];
export type UserCandidate = Schemas['UserCandidate'];
export type TodoItem = Schemas['TodoItem'];
export type TodoList = Schemas['TodoList'];
export type RequestedItem = Schemas['RequestedItem'];
export type RequestedList = Schemas['RequestedList'];
export type HandledItem = Schemas['HandledItem'];
export type HandledList = Schemas['HandledList'];
export type InstanceDetail = Schemas['InstanceDetail'];
export type ApprovalStep = Schemas['ApprovalStep'];

/**
 * 目前選定的資料來源主機。所有請求自動帶上；深連結也跟著它走，
 * 所以切換主機等於同時切換「看哪一區的資料」與「連到哪一區的 BPM」。
 */
const HOST_STORAGE_KEY = 'bpm-todo-host';
export const activeHost = ref<string>(
  window.localStorage.getItem(HOST_STORAGE_KEY) ?? '');

export function setActiveHost(key: string) {
  activeHost.value = key;
  window.localStorage.setItem(HOST_STORAGE_KEY, key);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const query = new URLSearchParams();
  if (activeHost.value) query.set('host', activeHost.value);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query}` : '';
  const response = await fetch(`/api${path}${suffix}`);
  if (!response.ok) {
    // 失敗要如實往上拋，讓畫面顯示錯誤而不是空清單
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch { /* 回應不是 JSON 就沿用狀態碼 */ }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  hosts: () => get<HostOption[]>('/hosts'),
  health: () => get<Health>('/health'),
  searchUsers: (q: string) => get<UserCandidate[]>('/users/search', { q }),
  todo: (userId: string) => get<TodoList>(`/users/${encodeURIComponent(userId)}/todo`),
  requested: (userId: string, offset: number, limit: number, state?: number) =>
    get<RequestedList>(`/users/${encodeURIComponent(userId)}/requested`,
      { offset, limit, state }),
  handled: (userId: string, offset: number, limit: number) =>
    get<HandledList>(`/users/${encodeURIComponent(userId)}/handled`, { offset, limit }),
  instance: (serialNumber: string, userId = '') =>
    get<InstanceDetail>(`/instances/${encodeURIComponent(serialNumber)}`,
      { user_id: userId }),
};

/** ProcessInstance.currentState 對應的徽章樣式 */
export function stateClass(code: number | null | undefined): string {
  switch (code) {
    case 1: return 'running';
    case 3: return 'closed';
    case 4: return 'aborted';
    case 5: return 'terminated';
    default: return '';
  }
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '';
  return value.replace('T', ' ').slice(0, 19);
}
