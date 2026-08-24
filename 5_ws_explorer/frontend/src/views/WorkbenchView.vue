<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue';
import { api } from '../api/client';
import type { InvokeResult, OperationDetail, OperationSummary } from '../api/types';

const props = defineProps<{
  initialOperationName?: string;
  initialInputMessage?: string;
}>();

const showToast = inject<(msg: string) => void>('showToast', () => {});

const operations = ref<OperationSummary[]>([]);
const selectedName = ref<string>('');
const selectedInputMsg = ref<string>('');
const currentOp = ref<OperationDetail | null>(null);
const loadingDetail = ref(false);

const paramValues = ref<Record<string, any>>({});
const allowWrite = ref(false);
const executing = ref(false);
const result = ref<InvokeResult | null>(null);

const activeResultTab = ref<'value' | 'envelope' | 'raw' | 'shape'>('value');

const history = ref<Array<{
  timestamp: string;
  name: string;
  status: string;
  elapsedMs: number;
  result: InvokeResult;
}>>([]);

async function loadOperations() {
  try {
    operations.value = await api.listOperations();
    const targetName = props.initialOperationName || (operations.value[0]?.name ?? '');
    const targetMsg = props.initialInputMessage || '';
    if (targetName) {
      selectOperation(targetName, targetMsg);
    }
  } catch (err: any) {
    showToast(err.message || '載入方法失敗');
  }
}

async function selectOperation(name: string, inputMessage?: string) {
  if (!name) return;
  selectedName.value = name;
  selectedInputMsg.value = inputMessage || '';
  loadingDetail.value = true;
  allowWrite.value = false;
  result.value = null;

  try {
    const detail = await api.getOperation(name, inputMessage);
    currentOp.value = detail;

    // 填入預設種子參數
    const initParams: Record<string, any> = {};
    for (const p of detail.parameters) {
      initParams[p.name] = p.defaultValue !== undefined && p.defaultValue !== null ? p.defaultValue : '';
    }
    paramValues.value = initParams;
  } catch (err: any) {
    showToast(err.message || '載入方法明細失敗');
  } finally {
    loadingDetail.value = false;
  }
}

function resetToSeeds() {
  if (!currentOp.value) return;
  const initParams: Record<string, any> = {};
  for (const p of currentOp.value.parameters) {
    initParams[p.name] = p.defaultValue !== undefined && p.defaultValue !== null ? p.defaultValue : '';
  }
  paramValues.value = initParams;
  showToast('已重設為預設種子參數');
}

function clearParams() {
  if (!currentOp.value) return;
  const initParams: Record<string, any> = {};
  for (const p of currentOp.value.parameters) {
    initParams[p.name] = '';
  }
  paramValues.value = initParams;
  showToast('已清空參數');
}

function insertFormFieldTemplate(paramName: string) {
  const tpl = `<SP_DetectionOPForm>\n  <EmailSubjectTextBox id="EmailSubjectTextBox" dataType="java.lang.String" perDataProId="">主旨</EmailSubjectTextBox>\n  <ControlPlanApplyDate id="ControlPlanApplyDate" dataType="java.util.Date">2026/08/24</ControlPlanApplyDate>\n</SP_DetectionOPForm>`;
  paramValues.value[paramName] = tpl;
  showToast(`已填入 ${paramName} 範本`);
}

async function executeInvoke() {
  if (!currentOp.value) return;

  if (currentOp.value.level === 'write' && !allowWrite.value) {
    showToast('此方法具副作用，請先勾選確認開關');
    return;
  }

  executing.value = true;
  result.value = null;

  try {
    const res = await api.invoke({
      operationName: currentOp.value.name,
      inputMessage: currentOp.value.inputMessage,
      params: paramValues.value,
      allowWrite: allowWrite.value,
    });
    result.value = res;

    // 加進歷史紀錄
    history.value.unshift({
      timestamp: new Date().toLocaleTimeString(),
      name: currentOp.value.name,
      status: res.status,
      elapsedMs: res.elapsedMs,
      result: res,
    });
    if (history.value.length > 20) history.value.pop();

    if (res.status === 'ok') {
      activeResultTab.value = 'value';
    } else if (res.status === 'fault') {
      activeResultTab.value = 'raw';
    }
  } catch (err: any) {
    showToast(err.message || '呼叫失敗');
  } finally {
    executing.value = false;
  }
}

function copyText(text: string, label: string) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`已複製 ${label}`);
  });
}

function restoreFromHistory(item: typeof history.value[0]) {
  result.value = item.result;
}

watch(
  () => props.initialOperationName,
  (newVal) => {
    if (newVal && newVal !== selectedName.value) {
      selectOperation(newVal, props.initialInputMessage);
    }
  }
);

onMounted(loadOperations);
</script>

<template>
  <div class="workbench-layout">
    <!-- 左半部：參數輸入與執行控制 -->
    <section class="left-panel">
      <!-- 方法選擇器 -->
      <div class="op-select-box">
        <label class="panel-label">🎯 選擇測試方法 (共 {{ operations.length }} 支)：</label>
        <select
          class="op-dropdown"
          :value="selectedName"
          @change="selectOperation(($event.target as HTMLSelectElement).value)"
        >
          <optgroup label="唯讀方法 (Read-only)">
            <option
              v-for="op in operations.filter(o => o.level === 'read')"
              :key="op.inputMessage || op.name"
              :value="op.name"
            >
              {{ op.name }} ({{ op.parameterCount }} 參數) — {{ op.purpose || op.statusLabel }}
            </option>
          </optgroup>
          <optgroup label="寫入 / 具副作用方法 (Write / Side-effects)">
            <option
              v-for="op in operations.filter(o => o.level === 'write')"
              :key="op.inputMessage || op.name"
              :value="op.name"
            >
              ⚡ {{ op.name }} ({{ op.parameterCount }} 參數) — {{ op.purpose || '未分析' }}
            </option>
          </optgroup>
        </select>
      </div>

      <div v-if="currentOp" class="op-summary-card">
        <div class="op-summary-header">
          <span class="op-signature-text">{{ currentOp.signature }}</span>
          <span class="badge" :class="currentOp.level">{{ currentOp.level === 'read' ? '唯讀' : '副作用' }}</span>
        </div>
        <p v-if="currentOp.purpose" class="op-summary-purpose">{{ currentOp.purpose }}</p>
      </div>

      <!-- 參數表單 -->
      <div class="params-container">
        <div class="params-header">
          <span class="panel-label">⚙️ 請求參數設定：</span>
          <div class="params-actions">
            <button class="btn-xs" @click="resetToSeeds">🔄 帶入預設種子</button>
            <button class="btn-xs" @click="clearParams">🧹 清空</button>
          </div>
        </div>

        <div v-if="currentOp && currentOp.parameters.length > 0" class="params-form">
          <div
            v-for="(p, idx) in currentOp.parameters"
            :key="p.name"
            class="param-field"
          >
            <div class="param-field-label">
              <span class="param-order">#{{ idx + 1 }}</span>
              <span class="param-name-tag">{{ p.name }}</span>
              <span class="type-tag">{{ p.type }}</span>
              <span v-if="p.description" class="param-desc-hint" :title="p.description">
                {{ p.description }}
              </span>

              <button
                v-if="p.name === 'pFormFieldValue' || p.name.includes('XML') || p.name.includes('Xml')"
                class="btn-inline-tpl"
                @click="insertFormFieldTemplate(p.name)"
              >
                + 填入 XML 樣板
              </button>
            </div>

            <!-- 輸入元件判斷 -->
            <div class="param-input-wrap">
              <!-- boolean -->
              <select
                v-if="p.type === 'boolean'"
                v-model="paramValues[p.name]"
                class="input-control"
              >
                <option value="true">true</option>
                <option value="false">false</option>
                <option value="">（空值 / 預設）</option>
              </select>

              <!-- 多行文字 -->
              <textarea
                v-else-if="p.name === 'pFormFieldValue' || p.name.includes('XML') || p.name.includes('Xml') || String(paramValues[p.name] || '').length > 40"
                v-model="paramValues[p.name]"
                rows="4"
                class="input-control mono"
                :placeholder="`請輸入 ${p.name} (${p.type})`"
              ></textarea>

              <!-- 一般單行文字 / 數字 -->
              <input
                v-else
                v-model="paramValues[p.name]"
                type="text"
                class="input-control mono"
                :placeholder="`請輸入 ${p.name} (${p.type})`"
              />
            </div>
          </div>
        </div>

        <div v-else-if="currentOp" class="no-params-hint">
          此方法無需傳入任何參數 (void)
        </div>
      </div>

      <!-- 安全防呆開關 (針對 write 操作) -->
      <div v-if="currentOp && currentOp.level === 'write'" class="safety-box">
        <div class="safety-title">⚠️ 副作用安全防呆警示</div>
        <div class="safety-desc">
          此方法屬於寫入或狀態變更操作（開單、簽核、轉派、作廢等），會在 191 測試區產生真實單據。
        </div>
        <label class="safety-checkbox-label">
          <input v-model="allowWrite" type="checkbox" />
          <span>我確認已了解副作用，同意向 191 測試區發送執行請求</span>
        </label>
      </div>

      <!-- 執行按鈕列 -->
      <div class="invoke-bar">
        <div class="endpoint-note">
          連線目標：<code>10.10.130.191:8080</code>（190 正式區已永久鎖定）
        </div>
        <button
          class="primary invoke-btn"
          :disabled="executing || (currentOp?.level === 'write' && !allowWrite)"
          @click="executeInvoke"
        >
          <span v-if="executing">⏳ 正在連線 191 測試區…</span>
          <span v-else>🚀 發送 SOAP 請求實測</span>
        </button>
      </div>

      <!-- 歷史紀錄 -->
      <div v-if="history.length > 0" class="history-box">
        <div class="history-title">⏱️ 本次連線實測紀錄 ({{ history.length }})</div>
        <div class="history-list">
          <div
            v-for="(item, hIdx) in history"
            :key="hIdx"
            class="history-item"
            @click="restoreFromHistory(item)"
          >
            <span class="badge" :class="`st-${item.status}`">{{ item.status }}</span>
            <span class="history-name">{{ item.name }}</span>
            <span class="history-time">{{ item.elapsedMs }} ms</span>
            <span class="history-ts">{{ item.timestamp }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 右半部：實測結果與封包檢視 -->
    <section class="right-panel">
      <div class="result-header">
        <div class="result-title-row">
          <span class="panel-label">📊 實測回應結果</span>
          <div v-if="result" class="result-status-badges">
            <span class="badge" :class="`st-${result.status}`">
              {{ result.status === 'ok' ? '🟢 200 OK 成功' : result.status === 'soft_error' ? '🟡 假成功 (Soft Error)' : result.status === 'fault' ? '🔴 SOAP Fault' : '❌ 錯誤' }}
            </span>
            <span class="elapsed-badge">⏱️ {{ result.elapsedMs }} ms</span>
          </div>
        </div>

        <!-- 結果分頁標籤 -->
        <div v-if="result" class="result-tabs">
          <button
            class="res-tab"
            :class="{ active: activeResultTab === 'value' }"
            @click="activeResultTab = 'value'"
          >
            📜 解析回傳值
          </button>
          <button
            class="res-tab"
            :class="{ active: activeResultTab === 'shape' }"
            @click="activeResultTab = 'shape'"
          >
            🧭 資料結構輪廓
          </button>
          <button
            class="res-tab"
            :class="{ active: activeResultTab === 'envelope' }"
            @click="activeResultTab = 'envelope'"
          >
            ✉️ SOAP 請求封包
          </button>
          <button
            class="res-tab"
            :class="{ active: activeResultTab === 'raw' }"
            @click="activeResultTab = 'raw'"
          >
            📦 原始 SOAP 回應
          </button>
        </div>
      </div>

      <div class="result-body">
        <div v-if="executing" class="running-placeholder">
          <div class="spinner"></div>
          <p>正在呼叫 191 測試區 Apache Axis 1.3 服務，請稍候…</p>
        </div>

        <div v-else-if="result" class="result-view-content">
          <!-- 假成功提示 -->
          <div v-if="result.status === 'soft_error'" class="callout warn">
            <div class="callout-title">⚠️ 偵測到假成功（Soft Error / 例外字串）</div>
            <div>服務回傳 HTTP 200，但回傳字串內含例外：<code>{{ result.softError }}</code></div>
          </div>

          <!-- SOAP Fault 提示 -->
          <div v-if="result.status === 'fault'" class="callout danger">
            <div class="callout-title">🔴 SOAP Fault 失敗</div>
            <div>代碼：<code>{{ result.faultCode }}</code></div>
            <div>訊息：<code>{{ result.faultString }}</code></div>
          </div>

          <!-- 系統錯誤提示 -->
          <div v-if="result.status === 'error'" class="callout danger">
            <div class="callout-title">❌ 執行 / 連線錯誤</div>
            <div><code>{{ result.error }}</code></div>
          </div>

          <!-- Tab 1: 解析回傳值 -->
          <div v-if="activeResultTab === 'value'" class="tab-pane">
            <div class="pane-header">
              <span>回傳值純文字 / XML (長度: {{ (result.value || '').length }} 字元)</span>
              <button
                v-if="result.value"
                class="copy-btn-inline"
                @click="copyText(result.value!, '回傳值')"
              >
                📋 複製回傳值
              </button>
            </div>
            <pre v-if="result.value" class="code-box-full"><code>{{ result.value }}</code></pre>
            <div v-else class="text-faint empty-box">此方法回傳值為空 (void / null)</div>
          </div>

          <!-- Tab 2: 資料結構輪廓 -->
          <div v-if="activeResultTab === 'shape'" class="tab-pane">
            <div class="pane-header">
              <span>XML 標籤階層輪廓 (Tag Path)</span>
            </div>
            <div v-if="result.returnShape" class="shape-display">
              <code>{{ result.returnShape }}</code>
            </div>
            <div v-else class="text-faint empty-box">無 XML 結構輪廓</div>
          </div>

          <!-- Tab 3: SOAP Request Envelope -->
          <div v-if="activeResultTab === 'envelope'" class="tab-pane">
            <div class="pane-header">
              <span>向 Axis 1.3 發送的真實 rpc/encoded SOAP Envelope 封包</span>
              <button
                v-if="result.requestEnvelope"
                class="copy-btn-inline"
                @click="copyText(result.requestEnvelope!, '請求封包')"
              >
                📋 複製 Envelope
              </button>
            </div>
            <pre v-if="result.requestEnvelope" class="code-box-full"><code>{{ result.requestEnvelope }}</code></pre>
          </div>

          <!-- Tab 4: 原始 SOAP Response -->
          <div v-if="activeResultTab === 'raw'" class="tab-pane">
            <div class="pane-header">
              <span>伺服器回傳之完整 HTTP SOAP Body (長度: {{ (result.rawResponse || '').length }} 字元)</span>
              <button
                v-if="result.rawResponse"
                class="copy-btn-inline"
                @click="copyText(result.rawResponse!, '原始回應')"
              >
                📋 複製原始回應
              </button>
            </div>
            <pre v-if="result.rawResponse" class="code-box-full"><code>{{ result.rawResponse }}</code></pre>
            <div v-else class="text-faint empty-box">無原始回應內容</div>
          </div>
        </div>

        <div v-else class="initial-placeholder">
          <div class="placeholder-icon">⚡</div>
          <h3>即時實測工作台</h3>
          <p>請於左側設定參數後點選「發送 SOAP 請求實測」，將即時連線 191 測試區並呈現回傳結果與封包。</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.workbench-layout {
  display: flex;
  flex: 1;
  height: calc(100vh - 53px);
  overflow: hidden;
}

.left-panel {
  width: 480px;
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  padding: 16px 20px;
  gap: 14px;
}

.panel-label {
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
  margin-bottom: 6px;
  display: block;
}

.op-select-box {
  display: flex;
  flex-direction: column;
}
.op-dropdown {
  width: 100%;
  font-size: 13px;
  font-family: var(--mono);
}

.op-summary-card {
  background: var(--panel-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}
.op-summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.op-signature-text {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.op-summary-purpose {
  margin: 6px 0 0 0;
  font-size: 12px;
  color: var(--text-dim);
}

.params-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.params-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.params-actions {
  display: flex;
  gap: 6px;
}
.btn-xs {
  font-size: 11px;
  padding: 2px 8px;
}

.params-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--bg);
  padding: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.param-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.param-order {
  color: var(--text-faint);
  font-size: 11px;
}
.param-name-tag {
  font-family: var(--mono);
  font-weight: 600;
  color: var(--text);
}
.type-tag {
  font-family: var(--mono);
  font-size: 11px;
  background: var(--panel);
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid var(--border);
  color: #c7254e;
}
.param-desc-hint {
  color: var(--text-dim);
  font-size: 11px;
  margin-left: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}
.btn-inline-tpl {
  font-size: 10px;
  padding: 1px 6px;
  margin-left: auto;
  color: var(--accent);
  border-color: var(--accent);
}

.input-control {
  width: 100%;
  font-size: 12px;
}
.input-control.mono {
  font-family: var(--mono);
}

.no-params-hint {
  padding: 16px;
  text-align: center;
  color: var(--text-faint);
  background: var(--bg);
  border-radius: var(--radius-sm);
}

.safety-box {
  background: #fff8e6;
  border: 1px solid #ffe58f;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}
.safety-title {
  font-weight: 700;
  font-size: 12px;
  color: #d46b08;
  margin-bottom: 4px;
}
.safety-desc {
  font-size: 12px;
  color: #873800;
  margin-bottom: 8px;
}
.safety-checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #d46b08;
  cursor: pointer;
}

.invoke-bar {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.endpoint-note {
  font-size: 11px;
  color: var(--text-dim);
}
.endpoint-note code {
  font-family: var(--mono);
}
.invoke-btn {
  width: 100%;
  justify-content: center;
  padding: 10px;
  font-size: 14px;
}

.history-box {
  border-top: 1px solid var(--border);
  padding-top: 10px;
}
.history-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 120px;
  overflow-y: auto;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  padding: 4px 6px;
  border-radius: 4px;
  background: var(--bg);
  cursor: pointer;
}
.history-item:hover {
  background: var(--accent-faint);
}
.history-name {
  font-family: var(--mono);
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-time {
  color: var(--text-dim);
}
.history-ts {
  color: var(--text-faint);
  font-size: 10px;
}

/* ---------------- 右側面板 ---------------- */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--panel);
}

.result-header {
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-alt);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.result-status-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}
.elapsed-badge {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--panel);
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
}

.result-tabs {
  display: flex;
  gap: 6px;
}
.res-tab {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--panel);
  color: var(--text-dim);
}
.res-tab.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  font-weight: 600;
}

.result-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.tab-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
}
.pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
}
.copy-btn-inline {
  font-size: 11px;
  padding: 3px 8px;
}

.code-box-full {
  background: #1e2430;
  color: #e6edf3;
  padding: 14px;
  border-radius: var(--radius-sm);
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 600px;
  overflow: auto;
}

.shape-display {
  background: var(--accent-faint);
  padding: 16px;
  border-radius: var(--radius-sm);
  font-family: var(--mono);
  font-size: 13px;
  color: var(--accent);
  border: 1px solid var(--border);
}

.initial-placeholder, .running-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
  color: var(--text-dim);
}
.placeholder-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.initial-placeholder h3 {
  margin: 0 0 8px 0;
  color: var(--text);
}
.initial-placeholder p {
  max-width: 420px;
  font-size: 13px;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-box {
  padding: 32px;
  text-align: center;
}
</style>
