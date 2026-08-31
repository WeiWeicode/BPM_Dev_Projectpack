import type {
  AcceptResult,
  ActivityBoard,
  CloseProcessResult,
  CompleteResult,
  CreateInstanceResult,
  FormEditPreviewResult,
  FormEditSubmitResult,
  InstanceDetail,
  InstanceListResult,
  InvokeRequest,
  InvokeResult,
  OperationDetail,
  OperationSummary,
  OverviewSummary,
  NewFormTemplate,
  OrgUnitListResult,
  ProcessListResult,
  ReassignResult,
  ReexecuteResult,
  SeedsData,
} from './types';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, options: { method?: string; body?: any; params?: Record<string, any> } = {}): Promise<T> {
  const { method = 'GET', body, params } = options;
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err: any) {
    throw new ApiError('無法連線到後端服務，請確認後端 uvicorn 是否已在 :8001 啟動', 0);
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  getOverview: () => request<OverviewSummary>('/api/overview'),
  listOperations: (params?: { keyword?: string; level?: string; confidence?: string; status?: string }) =>
    request<OperationSummary[]>('/api/operations', { params }),
  getOperation: (name: string, inputMessage?: string) =>
    request<OperationDetail>(`/api/operations/${encodeURIComponent(name)}`, {
      params: inputMessage ? { input_message: inputMessage } : undefined,
    }),
  getSeeds: () => request<SeedsData>('/api/seeds'),
  getPayload: async (name: string): Promise<string> => {
    const res = await fetch(`/api/payloads/${encodeURIComponent(name)}`);
    if (!res.ok) throw new ApiError('無法取得樣本內容', res.status);
    return res.text();
  },
  invoke: (req: InvokeRequest) => request<InvokeResult>('/api/invoke', { method: 'POST', body: req }),

  // 改單工作台
  listEditProcesses: (keyword?: string) =>
    request<ProcessListResult>('/api/form-edit/processes', { params: { keyword } }),
  listEditInstances: (params: { processId: string; scope?: string; startTime?: string; endTime?: string; dateBasis?: string }) =>
    request<InstanceListResult>('/api/form-edit/instances', { params }),
  loadEditInstance: (serialNo: string) =>
    request<InstanceDetail>(`/api/form-edit/instance/${encodeURIComponent(serialNo)}`),
  previewEdit: (serialNo: string, changes: Record<string, string>) =>
    request<FormEditPreviewResult>('/api/form-edit/preview', { method: 'POST', body: { serialNo, changes } }),
  submitEdit: (body: { serialNo: string; changes?: Record<string, string>; rawFormXml?: string; confirm: boolean }) =>
    request<FormEditSubmitResult>('/api/form-edit/submit', { method: 'POST', body }),

  // 建立新單
  listOrgUnits: (userId: string) =>
    request<OrgUnitListResult>('/api/form-edit/org-units', { params: { userId } }),
  loadNewForm: (processId: string) =>
    request<NewFormTemplate>('/api/form-edit/new-form', { params: { processId } }),
  createInstance: (body: {
    processId: string;
    requesterId: string;
    orgUnitId: string;
    subject?: string;
    values?: Record<string, string>;
    orgId?: string;
    confirm: boolean;
  }) => request<CreateInstanceResult>('/api/form-edit/create', { method: 'POST', body }),

  // 關卡操作
  getBoard: (serialNo: string) =>
    request<ActivityBoard>(`/api/workitem/board/${encodeURIComponent(serialNo)}`),
  acceptWorkItem: (body: { workItemOID: string; userId: string; confirm: boolean }) =>
    request<AcceptResult>('/api/workitem/accept', { method: 'POST', body }),
  completeWorkItem: (body: {
    serialNo: string;
    workItemOID: string;
    userId: string;
    comment?: string;
    changes?: Record<string, string>;
    autoAccept?: boolean;
    confirm: boolean;
  }) => request<CompleteResult>('/api/workitem/complete', { method: 'POST', body }),
  reassignWorkItem: (body: {
    workItemOID: string;
    acceptorId: string;
    comment?: string;
    mode?: string;
    requesterId?: string;
    confirm: boolean;
  }) => request<ReassignResult>('/api/workitem/reassign', { method: 'POST', body }),
  reexecuteActivity: (body: {
    serialNo: string;
    askUserId: string;
    activityId: string;
    comment?: string;
    confirm: boolean;
  }) => request<ReexecuteResult>('/api/workitem/reexecute', { method: 'POST', body }),
  closeProcess: (body: {
    serialNo: string;
    mode?: string;
    userId?: string;
    comment?: string;
    confirm: boolean;
  }) => request<CloseProcessResult>('/api/workitem/close', { method: 'POST', body }),
};
