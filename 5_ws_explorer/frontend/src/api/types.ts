export interface ParameterInfo {
  name: string;
  type: string;
  description?: string | null;
  defaultValue?: any;
}

export interface ReturnInfo {
  type?: string | null;
  name?: string | null;
  description?: string | null;
}

export interface OperationSummary {
  name: string;
  inputMessage: string;
  level: 'read' | 'write';
  confidence: 'verified' | 'external' | 'guess' | 'none';
  confidenceLabel: string;
  status: 'ok' | 'fault' | 'error' | 'soft_error' | 'skipped';
  statusLabel: string;
  elapsedMs?: number | null;
  purpose?: string | null;
  parameterCount: number;
  parameters: ParameterInfo[];
  returns?: ReturnInfo | null;
  hasPayload: boolean;
}

export interface OperationDetail {
  name: string;
  inputMessage: string;
  portType: string;
  parameterOrder: string[];
  level: 'read' | 'write';
  confidence: 'verified' | 'external' | 'guess' | 'none';
  confidenceLabel: string;
  status: 'ok' | 'fault' | 'error' | 'soft_error' | 'skipped';
  statusLabel: string;
  elapsedMs?: number | null;
  purpose?: string | null;
  parameters: ParameterInfo[];
  returns?: ReturnInfo | null;
  remarks?: string | null;
  payloadPath?: string | null;
  payloadSample?: string | null;
  faultCode?: string | null;
  faultString?: string | null;
  error?: string | null;
  softError?: string | null;
  reason?: string | null;
  returnShape?: string | null;
  signature: string;
}

export interface OverviewSummary {
  endpoint: string;
  targetNamespace: string;
  operationCount: number;
  documentedCount: number;
  verifiedCount: number;
  probedAt?: string | null;
  statusCounts: Record<string, number>;
  confidenceCounts: Record<string, number>;
  levelCounts: Record<string, number>;
}

export interface SeedsData {
  seeds: Record<string, any>;
  sources: Record<string, string>;
  overrides: Record<string, Record<string, any>>;
}

export interface InvokeRequest {
  operationName: string;
  inputMessage?: string | null;
  params: Record<string, any>;
  allowWrite?: boolean;
  endpoint?: string | null;
}

export interface InvokeResult {
  status: 'ok' | 'fault' | 'soft_error' | 'error';
  elapsedMs: number;
  value?: string | null;
  rawResponse?: string | null;
  requestEnvelope?: string | null;
  returnShape?: string | null;
  faultCode?: string | null;
  faultString?: string | null;
  softError?: string | null;
  error?: string | null;
}
