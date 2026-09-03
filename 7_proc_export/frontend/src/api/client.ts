import type {
  ExportPreview,
  ExportRequest,
  FieldCatalog,
  InstanceDetail,
  MetaInfo,
  ProcessListResult,
  SearchRequest,
  SearchResult,
} from './types';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  params?: Record<string, unknown>;
}

function buildUrl(path: string, params?: Record<string, unknown>): URL {
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url;
}

async function readError(response: Response): Promise<string> {
  // FastAPI 的錯誤在 detail；讀不出來就退回狀態碼，不假裝成功
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
    return JSON.stringify(data);
  } catch {
    return `HTTP ${response.status}`;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, params } = options;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('無法連線到後端服務，請確認 uvicorn 是否已啟動（port 8002）', 0);
  }
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  return response.json() as Promise<T>;
}

/** 匯出回傳的是檔案不是 JSON，另外處理；同時把後端算出的筆數帶回來。 */
async function download(
  path: string,
  body: unknown,
  params?: Record<string, unknown>,
): Promise<{ blob: Blob; filename: string; rows: string }> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError('無法連線到後端服務，請確認 uvicorn 是否已啟動（port 8002）', 0);
  }
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  const disposition = response.headers.get('Content-Disposition') || '';
  const match = /filename\*=UTF-8''([^;]+)/.exec(disposition);
  return {
    blob: await response.blob(),
    filename: match ? decodeURIComponent(match[1]) : 'export.xlsx',
    rows: response.headers.get('X-Export-Rows') || '',
  };
}

export const api = {
  meta: () => request<MetaInfo>('/api/meta'),

  processes: (host: string, keyword: string) =>
    request<ProcessListResult>('/api/processes', { params: { host, keyword } }),

  fields: (host: string, processId: string) =>
    request<FieldCatalog>(`/api/processes/${encodeURIComponent(processId)}/fields`, {
      params: { host },
    }),

  search: (host: string, req: SearchRequest) =>
    request<SearchResult>('/api/instances/search', {
      method: 'POST',
      body: req,
      params: { host },
    }),

  instance: (host: string, serialNumber: string) =>
    request<InstanceDetail>(`/api/instances/${encodeURIComponent(serialNumber)}`, {
      params: { host },
    }),

  exportPreview: (host: string, req: ExportRequest) =>
    request<ExportPreview>('/api/export/preview', {
      method: 'POST',
      body: req,
      params: { host },
    }),

  exportDownload: (host: string, req: ExportRequest) =>
    download('/api/export/download', req, { host }),
};
