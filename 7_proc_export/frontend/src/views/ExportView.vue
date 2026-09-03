<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue';
import { api } from '../api/client';
import type {
  ExportRequest,
  FieldCatalog,
  InstanceDetail,
  MetaInfo,
  ProcessSummary,
  SearchResult,
} from '../api/types';
import FieldPicker from './FieldPicker.vue';
import InstancePanel from './InstancePanel.vue';

const props = defineProps<{ host: string; meta: MetaInfo }>();
const showToast = inject<(msg: string) => void>('showToast', () => {});

// ── 左側：流程 ──────────────────────────────────────────────
const processKeyword = ref('');
const processes = ref<ProcessSummary[]>([]);
const processTotal = ref(0);
const loadingProcesses = ref(false);
const selectedProcess = ref<ProcessSummary | null>(null);

// ── 查詢條件 ────────────────────────────────────────────────
const startDate = ref('');
const endDate = ref('');
const filters = ref({
  processSerialNumber: '',
  formSerialNumber: '',
  requester: '',
  subject: '',
  states: [] as number[],
});
const customValues = ref<Record<string, string>>({});

// ── 欄位 ────────────────────────────────────────────────────
const catalog = ref<FieldCatalog | null>(null);
const loadingCatalog = ref(false);
const selectedFieldIds = ref<string[]>([]);
const selectedGridIds = ref<string[]>([]);
const pickerOpen = ref(false);

// ── 結果 ────────────────────────────────────────────────────
const result = ref<SearchResult | null>(null);
const searching = ref(false);
const page = ref(1);
const pageSize = ref(50);

// ── 明細 ────────────────────────────────────────────────────
const detail = ref<InstanceDetail | null>(null);
const detailLoading = ref(false);
const detailOpen = ref(false);
const activeSerial = ref('');

// ── 匯出 ────────────────────────────────────────────────────
const exportList = ref(true);
const exportContent = ref(true);
const exportSignatures = ref(true);
const exporting = ref(false);
const previewText = ref('');

const STATE_OPTIONS = [
  { value: 1, label: '進行中' },
  { value: 3, label: '已結案' },
  { value: 4, label: '已作廢' },
  { value: 5, label: '已終止' },
];

const selectedFields = computed(() =>
  (catalog.value?.fields || []).filter((f) => selectedFieldIds.value.includes(f.id)),
);

const totalPages = computed(() => {
  if (!result.value) return 1;
  return Math.max(1, Math.ceil(result.value.total / pageSize.value));
});

function defaultDates() {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth() - 3, today.getDate());
  endDate.value = today.toISOString().slice(0, 10);
  startDate.value = start.toISOString().slice(0, 10);
}

async function loadProcesses() {
  loadingProcesses.value = true;
  try {
    const data = await api.processes(props.host, processKeyword.value.trim());
    processes.value = data.processes;
    processTotal.value = data.total;
  } catch (err: any) {
    showToast(err?.message || '載入流程清單失敗');
  } finally {
    loadingProcesses.value = false;
  }
}

async function selectProcess(process: ProcessSummary) {
  selectedProcess.value = process;
  result.value = null;
  detail.value = null;
  detailOpen.value = false;
  selectedFieldIds.value = [];
  selectedGridIds.value = [];
  customValues.value = {};
  previewText.value = '';
  page.value = 1;

  // 有單據的日期範圍就直接套上去，省得使用者猜這支流程有沒有資料
  if (process.firstCreated) startDate.value = process.firstCreated.slice(0, 10);
  if (process.lastCreated) endDate.value = process.lastCreated.slice(0, 10);

  loadingCatalog.value = true;
  catalog.value = null;
  try {
    catalog.value = await api.fields(props.host, process.processId);
    selectedGridIds.value = catalog.value.grids.map((g) => g.id);
  } catch (err: any) {
    showToast(err?.message || '載入欄位清單失敗');
  } finally {
    loadingCatalog.value = false;
  }
  await search(1);
}

function customFilters() {
  return Object.entries(customValues.value)
    .filter(([, value]) => (value || '').trim())
    .map(([fieldId, value]) => ({ fieldId, value: value.trim() }));
}

async function search(targetPage = 1) {
  if (!selectedProcess.value) return;
  searching.value = true;
  page.value = targetPage;
  try {
    result.value = await api.search(props.host, {
      processId: selectedProcess.value.processId,
      startDate: startDate.value,
      endDate: endDate.value,
      filters: filters.value,
      customFilters: customFilters(),
      fieldIds: selectedFieldIds.value,
      page: targetPage,
      pageSize: pageSize.value,
    });
  } catch (err: any) {
    result.value = null;
    showToast(err?.message || '查詢失敗');
  } finally {
    searching.value = false;
  }
}

async function openDetail(serialNumber: string) {
  activeSerial.value = serialNumber;
  detailOpen.value = true;
  detailLoading.value = true;
  try {
    detail.value = await api.instance(props.host, serialNumber);
  } catch (err: any) {
    detail.value = null;
    showToast(err?.message || '載入單據失敗');
  } finally {
    detailLoading.value = false;
  }
}

function exportRequest(): ExportRequest {
  return {
    processId: selectedProcess.value!.processId,
    startDate: startDate.value,
    endDate: endDate.value,
    filters: filters.value,
    customFilters: customFilters(),
    fieldIds: selectedFieldIds.value,
    gridIds: selectedGridIds.value,
    exportList: exportList.value,
    exportContent: exportContent.value,
    exportSignatures: exportSignatures.value,
  };
}

async function previewCount() {
  if (!selectedProcess.value) return;
  try {
    const data = await api.exportPreview(props.host, exportRequest());
    previewText.value = data.exceeded
      ? `符合 ${data.matched.toLocaleString()} 筆，超過上限 ${data.limit.toLocaleString()} 筆，請縮小日期區間再匯出。`
      : `符合 ${data.matched.toLocaleString()} 筆。${data.note}`;
  } catch (err: any) {
    previewText.value = '';
    showToast(err?.message || '預估筆數失敗');
  }
}

async function runExport() {
  if (!selectedProcess.value) return;
  if (!exportList.value && !exportContent.value && !exportSignatures.value) {
    showToast('至少要選一項匯出內容');
    return;
  }
  exporting.value = true;
  try {
    const { blob, filename, rows } = await api.exportDownload(props.host, exportRequest());
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast(`已匯出 ${rows} 筆：${filename}`);
  } catch (err: any) {
    showToast(err?.message || '匯出失敗');
  } finally {
    exporting.value = false;
  }
}

function formatTime(value?: string | null) {
  return value ? value.replace('T', ' ').slice(0, 19) : '';
}

function toggleState(value: number) {
  const states = filters.value.states;
  filters.value.states = states.includes(value)
    ? states.filter((s) => s !== value)
    : [...states, value];
}

watch(selectedFieldIds, () => {
  // 取消勾選的欄位，其查詢條件也要一起清掉，否則會有看不見的條件在生效
  for (const key of Object.keys(customValues.value)) {
    if (!selectedFieldIds.value.includes(key)) delete customValues.value[key];
  }
});

onMounted(() => {
  defaultDates();
  loadProcesses();
});
</script>

<template>
  <div class="layout">
    <!-- 左：流程 -->
    <aside class="side">
      <div class="side-head">
        <input
          v-model="processKeyword"
          placeholder="搜尋流程 ID 或名稱…"
          @keyup.enter="loadProcesses"
        />
        <button @click="loadProcesses" :disabled="loadingProcesses">搜尋</button>
      </div>
      <p class="side-meta">
        {{ loadingProcesses ? '載入中…' : `${processTotal} 支流程有單據` }}
      </p>
      <ul class="process-list">
        <li
          v-for="process in processes"
          :key="process.processId"
          :class="{ active: selectedProcess?.processId === process.processId }"
          @click="selectProcess(process)"
        >
          <div class="p-name">{{ process.processName || '（未命名）' }}</div>
          <code class="p-id">{{ process.processId }}</code>
          <div class="p-meta">
            {{ process.instanceCount.toLocaleString() }} 筆 ·
            {{ (process.firstCreated || '').slice(0, 7) }} ~
            {{ (process.lastCreated || '').slice(0, 7) }}
          </div>
        </li>
      </ul>
    </aside>

    <!-- 中：查詢與結果 -->
    <main class="main">
      <p v-if="!selectedProcess" class="placeholder">
        從左邊挑一支流程開始。清單依單據數由多到少排序。
      </p>

      <template v-else>
        <section class="query">
          <div class="query-row">
            <label>申請日期<span class="req">必填</span></label>
            <input type="date" v-model="startDate" />
            <span class="tilde">~</span>
            <input type="date" v-model="endDate" />
          </div>

          <div class="query-grid">
            <label>流程單號<input v-model="filters.processSerialNumber" placeholder="包含…" /></label>
            <label>表單單號<input v-model="filters.formSerialNumber" placeholder="包含…" /></label>
            <label>申請人<input v-model="filters.requester" placeholder="工號或姓名" /></label>
            <label>標題<input v-model="filters.subject" placeholder="包含…" /></label>
          </div>

          <div class="query-row states">
            <label>狀態</label>
            <label v-for="option in STATE_OPTIONS" :key="option.value" class="check">
              <input
                type="checkbox"
                :checked="filters.states.includes(option.value)"
                @change="toggleState(option.value)"
              />
              {{ option.label }}
            </label>
            <span class="hint-inline">不勾選＝全部</span>
          </div>

          <div v-if="selectedFields.length" class="custom-fields">
            <label v-for="field in selectedFields" :key="field.id">
              <span :class="{ unnamed: !field.named }">{{ field.name }}</span>
              <input v-model="customValues[field.id]" placeholder="包含…" />
            </label>
          </div>

          <div class="query-actions">
            <button class="primary" @click="search(1)" :disabled="searching">
              {{ searching ? '查詢中…' : '查詢' }}
            </button>
            <button @click="pickerOpen = true" :disabled="loadingCatalog || !catalog">
              選取欄位（已選 {{ selectedFieldIds.length }}）
            </button>
            <span v-if="loadingCatalog" class="hint-inline">載入欄位清單中…</span>
            <span v-else-if="catalog" class="hint-inline">
              表單 {{ catalog.forms.map((f) => f.formId).join('、') || '查不到' }} ·
              {{ catalog.labelCoverage.named }}/{{ catalog.labelCoverage.total }} 個欄位有中文名稱
            </span>
          </div>
        </section>

        <section class="export-bar">
          <strong>匯出</strong>
          <label class="check"><input type="checkbox" v-model="exportList" /> 清單</label>
          <label class="check"><input type="checkbox" v-model="exportContent" /> 內容（含表格明細）</label>
          <label class="check"><input type="checkbox" v-model="exportSignatures" /> 簽核名單</label>
          <button @click="previewCount">預估筆數</button>
          <button class="primary" @click="runExport" :disabled="exporting">
            {{ exporting ? '產生中…' : '匯出 Excel' }}
          </button>
          <span v-if="previewText" class="hint-inline">{{ previewText }}</span>
        </section>

        <section class="results">
          <div v-if="result" class="result-meta">
            共 {{ result.total.toLocaleString() }} 筆
            <span v-if="!result.exact">（自訂欄位條件為逐張比對的結果）</span>
            <span v-if="result.note" class="warn-inline">{{ result.note }}</span>
          </div>

          <div class="table-scroll">
            <table class="rows">
              <thead>
                <tr>
                  <th>流程單號</th>
                  <th>表單單號</th>
                  <th>主旨</th>
                  <th>申請人</th>
                  <th>申請部門</th>
                  <th>申請日期</th>
                  <th>狀態</th>
                  <th v-for="field in selectedFields" :key="field.id">
                    <span :class="{ unnamed: !field.named }">{{ field.name }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in result?.rows || []"
                  :key="row.processSerialNumber"
                  :class="{ active: activeSerial === row.processSerialNumber }"
                  @click="openDetail(row.processSerialNumber)"
                >
                  <td class="mono">{{ row.processSerialNumber }}</td>
                  <td class="mono">{{ row.formSerialNumber }}</td>
                  <td class="subject">{{ row.subject }}</td>
                  <td>{{ row.requesterName }} {{ row.requesterId }}</td>
                  <td>{{ row.orgUnitName }}</td>
                  <td>{{ formatTime(row.createdTime) }}</td>
                  <td>{{ row.stateName }}</td>
                  <td v-for="field in selectedFields" :key="field.id">
                    {{ row.values[field.id] || '' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <p v-if="result && !result.rows.length" class="placeholder">
            這個條件查不到單。
          </p>

          <div v-if="result && result.total > pageSize" class="pager">
            <button @click="search(page - 1)" :disabled="page <= 1 || searching">上一頁</button>
            <span>第 {{ page }} / {{ totalPages }} 頁</span>
            <button @click="search(page + 1)" :disabled="page >= totalPages || searching">
              下一頁
            </button>
          </div>
        </section>
      </template>
    </main>

    <!-- 右：單張明細 -->
    <InstancePanel
      v-if="detailOpen"
      :detail="detail"
      :loading="detailLoading"
      :catalog="catalog"
      @close="detailOpen = false"
    />
  </div>

  <FieldPicker
    v-if="pickerOpen && catalog"
    :catalog="catalog"
    :selected="selectedFieldIds"
    :selected-grids="selectedGridIds"
    @update="selectedFieldIds = $event"
    @update-grids="selectedGridIds = $event"
    @close="pickerOpen = false"
  />
</template>

<style scoped>
.layout {
  display: flex;
  height: calc(100vh - 49px);
  overflow: hidden;
}

.side {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--panel);
  display: flex;
  flex-direction: column;
}

.side-head {
  display: flex;
  gap: 6px;
  padding: 10px;
}

.side-head input {
  flex: 1;
  min-width: 0;
  padding: 6px 10px;
}

.side-meta {
  margin: 0;
  padding: 0 12px 8px;
  font-size: 11px;
  color: var(--text-faint);
}

.process-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}

.process-list li {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}

.process-list li:hover {
  background: var(--accent-faint);
}

.process-list li.active {
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  padding-left: 9px;
}

.p-name {
  font-weight: 600;
  font-size: 13px;
}

.p-id {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text-dim);
  word-break: break-all;
}

.p-meta {
  font-size: 11px;
  color: var(--text-faint);
}

.main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 14px 16px;
}

.placeholder {
  color: var(--text-faint);
  padding: 30px 0;
  text-align: center;
}

.query,
.export-bar,
.results {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  margin-bottom: 12px;
}

.query-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.query-row > label {
  font-size: 12px;
  color: var(--text-dim);
}

.req {
  color: var(--danger);
  font-size: 10px;
  margin-left: 4px;
}

.tilde {
  color: var(--text-faint);
}

.query-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.query-grid label,
.custom-fields label {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12px;
  color: var(--text-dim);
}

.query-grid input,
.custom-fields input {
  padding: 6px 10px;
}

.custom-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}

.check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  white-space: nowrap;
}

.states {
  margin-bottom: 10px;
}

.query-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hint-inline {
  font-size: 12px;
  color: var(--text-dim);
}

.warn-inline {
  color: var(--warn);
  margin-left: 8px;
}

.export-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.result-meta {
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 8px;
}

.table-scroll {
  overflow-x: auto;
}

.rows {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.rows th,
.rows td {
  border: 1px solid var(--border);
  padding: 5px 8px;
  text-align: left;
  white-space: nowrap;
}

.rows th {
  background: var(--panel-alt);
  position: sticky;
  top: 0;
}

.rows tbody tr {
  cursor: pointer;
}

.rows tbody tr:hover {
  background: var(--accent-faint);
}

.rows tbody tr.active {
  background: var(--accent-soft);
}

.mono {
  font-family: var(--mono);
}

.subject {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 欄位名稱查不到時弱化，避免把欄位 ID 誤讀成中文名稱 */
.unnamed {
  color: var(--text-faint);
  font-style: italic;
  font-weight: 400;
}

.pager {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
  padding-top: 10px;
  font-size: 12px;
}
</style>
