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
  confidence: 'verified' | 'verified_write' | 'external' | 'guess' | 'none';
  confidenceLabel: string;
  status: 'ok' | 'fault' | 'error' | 'soft_error' | 'skipped' | 'refused';
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
  confidence: 'verified' | 'verified_write' | 'external' | 'guess' | 'none';
  confidenceLabel: string;
  status: 'ok' | 'fault' | 'error' | 'soft_error' | 'skipped' | 'refused';
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

// ── 改單工作台（對應後端 schemas.py 的改單模型）──────────────────

export interface ProcessOption {
  processId?: string | null;
  processName?: string | null;
  version?: number | null;
  formIds: string[];
  formNames: string[];
}

export interface ProcessListResult {
  processes: ProcessOption[];
  total: number;
  truncated: boolean;
  source?: string | null;
}

export interface InstanceSummary {
  serialNo?: string | null;
  oid?: string | null;
  state?: string | null;
  subject?: string | null;
  requesterId?: string | null;
  requesterName?: string | null;
  createdTime?: string | null;
  processId?: string | null;
  processName?: string | null;
}

export interface InstanceListResult {
  instances: InstanceSummary[];
  total: number;
  method?: string | null;
  elapsedMs: number;
}

export interface FormFieldInfo {
  tag: string;
  id: string;
  value: string;
  name?: string | null;
  dataType?: string | null;
  fieldType?: string | null;
  attrBacked: boolean;
  attributes: Record<string, string>;
  extraAttributes: Record<string, string>;
}

export interface InstanceDetail {
  header: InstanceSummary;
  formId?: string | null;
  formIdFromResponse?: string | null;
  formSerialNumber?: string | null;
  fields: FormFieldInfo[];
  rawFormXml: string;
  labelSource?: string | null;
  labelsAvailable: boolean;
  corruption?: string | null;
  closed: boolean;
  elapsedMs: number;
}

export interface FieldDiff {
  tag: string;
  before?: string | null;
  after?: string | null;
}

export interface FieldMismatch {
  tag: string;
  expected?: string | null;
  actual?: string | null;
}

export interface FormEditPreviewResult {
  serialNo?: string | null;
  diff: FieldDiff[];
  fieldCount: number;
  pFormValue: string;
  unchanged: boolean;
}

export interface FormEditSubmitResult {
  status: 'ok' | 'mismatch' | 'unchanged';
  serialNo?: string | null;
  diff: FieldDiff[];
  verified: boolean;
  mismatches: FieldMismatch[];
  backupFormXml?: string | null;
  pFormValue?: string | null;
  fieldCountBefore?: number | null;
  fieldCountAfter?: number | null;
  corruptionCleared: boolean;
  elapsedMs: number;
  message?: string | null;
}
