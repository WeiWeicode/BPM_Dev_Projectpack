<script setup lang="ts">
import { computed, inject, onMounted, ref, watch, type Ref } from 'vue';
import { api } from '../api/client';
import type { OperationDetail, OperationSummary } from '../api/types';

const emit = defineEmits<{
  (e: 'select-workbench', operationName: string, inputMessage?: string): void;
}>();

const globalKeyword = inject<Ref<string>>('keyword', ref(''));
const showToast = inject<(msg: string) => void>('showToast', () => {});

const operations = ref<OperationSummary[]>([]);
const loadingList = ref(false);
const loadingDetail = ref(false);
const selectedOp = ref<OperationDetail | null>(null);
const selectedName = ref<string>('');
const selectedInputMsg = ref<string>('');

const filterLevel = ref<string>('all');
const filterConfidence = ref<string>('all');
const filterStatus = ref<string>('all');

const counts = computed(() => {
  const all = operations.value;
  return {
    total: all.length,
    read: all.filter(o => o.level === 'read').length,
    write: all.filter(o => o.level === 'write').length,
    ok: all.filter(o => o.status === 'ok').length,
    fault: all.filter(o => o.status === 'fault' || o.status === 'error').length,
    soft_error: all.filter(o => o.status === 'soft_error').length,
    skipped: all.filter(o => o.status === 'skipped').length,
  };
});

const filteredOperations = computed(() => {
  let list = operations.value;
  const kw = globalKeyword.value.trim().toLowerCase();

  if (kw) {
    list = list.filter(op => {
      const pNames = op.parameters.map(p => p.name).join(' ');
      return (
        op.name.toLowerCase().includes(kw) ||
        (op.purpose || '').toLowerCase().includes(kw) ||
        pNames.toLowerCase().includes(kw)
      );
    });
  }

  if (filterLevel.value !== 'all') {
    list = list.filter(op => op.level === filterLevel.value);
  }
  if (filterConfidence.value !== 'all') {
    list = list.filter(op => op.confidence === filterConfidence.value);
  }
  if (filterStatus.value !== 'all') {
    list = list.filter(op => op.status === filterStatus.value);
  }

  return list;
});

async function loadOperations() {
  loadingList.value = true;
  try {
    operations.value = await api.listOperations();
    if (operations.value.length > 0 && !selectedName.value) {
      selectOperation(operations.value[0].name, operations.value[0].inputMessage);
    }
  } catch (err: any) {
    showToast(err.message || '載入方法清單失敗');
  } finally {
    loadingList.value = false;
  }
}

async function selectOperation(name: string, inputMessage?: string) {
  selectedName.value = name;
  selectedInputMsg.value = inputMessage || '';
  loadingDetail.value = true;
  try {
    selectedOp.value = await api.getOperation(name, inputMessage);
  } catch (err: any) {
    showToast(err.message || '載入方法明細失敗');
  } finally {
    loadingDetail.value = false;
  }
}

function copyText(text: string, label: string) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`已複製 ${label}`);
  });
}

function goToWorkbench() {
  if (selectedOp.value) {
    emit('select-workbench', selectedOp.value.name, selectedOp.value.inputMessage);
  }
}

onMounted(loadOperations);
</script>

<template>
  <div class="manual-layout">
    <!-- 左側清單 -->
    <aside class="sidebar">
      <div class="filter-bar">
        <div class="filter-pills">
          <button
            class="pill-btn"
            :class="{ active: filterLevel === 'all' && filterStatus === 'all' }"
            @click="filterLevel = 'all'; filterStatus = 'all'"
          >
            全部 ({{ counts.total }})
          </button>
          <button
            class="pill-btn read"
            :class="{ active: filterLevel === 'read' }"
            @click="filterLevel = 'read'; filterStatus = 'all'"
          >
            唯讀 ({{ counts.read }})
          </button>
          <button
            class="pill-btn write"
            :class="{ active: filterLevel === 'write' }"
            @click="filterLevel = 'write'; filterStatus = 'all'"
          >
            寫入/副作用 ({{ counts.write }})
          </button>
          <button
            class="pill-btn ok"
            :class="{ active: filterStatus === 'ok' }"
            @click="filterStatus = 'ok'; filterLevel = 'all'"
          >
            實測成功 ({{ counts.ok }})
          </button>
        </div>

        <div class="filter-selects">
          <select v-model="filterConfidence" class="mini-select">
            <option value="all">全部信心水準</option>
            <option value="verified">✅ 已實測</option>
            <option value="verified_write">✅ 已實測（副作用已驗證）</option>
            <option value="external">☑️ 既有服務驗證</option>
            <option value="guess">⚠️ 僅推測</option>
            <option value="none">⚠️ 尚未分析</option>
          </select>
          <select v-model="filterStatus" class="mini-select">
            <option value="all">全部實測狀態</option>
            <option value="ok">實測成功</option>
            <option value="fault">SOAP Fault</option>
            <option value="soft_error">假成功</option>
            <option value="error">連線錯誤</option>
            <option value="skipped">未實測</option>
            <option value="refused">刻意未執行</option>
          </select>
        </div>
      </div>

      <div class="op-list">
        <div
          v-for="op in filteredOperations"
          :key="op.inputMessage || op.name"
          class="op-item"
          :class="{ active: selectedName === op.name && (!selectedInputMsg || selectedInputMsg === op.inputMessage) }"
          @click="selectOperation(op.name, op.inputMessage)"
        >
          <div class="op-item-header">
            <span class="op-item-name" :title="op.name">{{ op.name }}</span>
            <span class="badge" :class="op.level">{{ op.level === 'read' ? '唯讀' : '寫入' }}</span>
          </div>
          <div v-if="op.purpose" class="op-item-purpose" :title="op.purpose">
            {{ op.purpose }}
          </div>
          <div class="op-item-footer">
            <span class="badge" :class="`conf-${op.confidence}`">{{ op.confidenceLabel }}</span>
            <span class="badge" :class="`st-${op.status}`">{{ op.statusLabel }}</span>
            <span v-if="op.elapsedMs" class="op-item-time">{{ op.elapsedMs }} ms</span>
          </div>
        </div>

        <div v-if="filteredOperations.length === 0" class="empty-list">
          無符合條件的方法
        </div>
      </div>
    </aside>

    <!-- 右側詳細內容 -->
    <main class="detail-container">
      <div v-if="loadingDetail" class="loading-box">載入中…</div>
      <div v-else-if="selectedOp" class="detail-content">
        <!-- 頂部標題與按鈕 -->
        <div class="detail-header">
          <div>
            <div class="detail-title-row">
              <h2 class="detail-title">{{ selectedOp.name }}</h2>
              <span class="badge" :class="selectedOp.level">
                {{ selectedOp.level === 'read' ? '唯讀 (Read-only)' : '具有副作用 (Write / Side-effect)' }}
              </span>
              <span class="badge" :class="`conf-${selectedOp.confidence}`">
                {{ selectedOp.confidenceLabel }}
              </span>
              <span class="badge" :class="`st-${selectedOp.status}`">
                {{ selectedOp.statusLabel }}
              </span>
              <span v-if="selectedOp.elapsedMs" class="elapsed-tag">
                ⏱️ {{ selectedOp.elapsedMs }} ms
              </span>
            </div>
            <div v-if="selectedOp.inputMessage && selectedOp.inputMessage !== `${selectedOp.name}Request`" class="sub-msg">
              多載標記：{{ selectedOp.inputMessage }}
            </div>
          </div>

          <div class="detail-actions">
            <button class="primary" @click="goToWorkbench">
              ⚡ 載入至實測工作台
            </button>
            <button @click="copyText(selectedOp.signature, '方法簽章')">
              📋 複製簽章
            </button>
          </div>
        </div>

        <!-- 方法簽章 -->
        <div class="signature-box">
          <code>{{ selectedOp.signature }}</code>
          <button class="copy-btn" @click="copyText(selectedOp.signature, '方法簽章')">複製</button>
        </div>

        <!-- 用途與備註 -->
        <div class="section-card">
          <h3 class="section-title">📌 功能用途說明</h3>
          <p v-if="selectedOp.purpose" class="purpose-text">{{ selectedOp.purpose }}</p>
          <p v-else class="text-faint">尚未確認用途語意，未臆測。</p>

          <div v-if="selectedOp.remarks" class="callout warn">
            <div class="callout-title">⚠️ 注意事項 / 備註</div>
            <div>{{ selectedOp.remarks }}</div>
          </div>
        </div>

        <!-- 參數表格 -->
        <div class="section-card">
          <h3 class="section-title">
            📥 傳入參數列表
            <span class="badge-count">{{ selectedOp.parameters.length }} 個參數</span>
          </h3>

          <table v-if="selectedOp.parameters.length > 0" class="data-table">
            <thead>
              <tr>
                <th style="width: 25%">參數名稱 (順序)</th>
                <th style="width: 15%">WSDL 型別</th>
                <th style="width: 35%">用途說明</th>
                <th style="width: 25%">測試預設值 (seeds)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, idx) in selectedOp.parameters" :key="p.name">
                <td>
                  <span class="param-order">#{{ idx + 1 }}</span>
                  <code class="param-name">{{ p.name }}</code>
                </td>
                <td><span class="type-tag">{{ p.type }}</span></td>
                <td>{{ p.description || '未確認' }}</td>
                <td>
                  <code v-if="p.defaultValue !== null && p.defaultValue !== undefined" class="seed-val">
                    {{ p.defaultValue }}
                  </code>
                  <span v-else class="text-faint">—</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="text-faint">本方法無傳入參數 (void)</p>
        </div>

        <!-- 回傳說明 -->
        <div class="section-card">
          <h3 class="section-title">📤 回傳結果定義</h3>
          <div class="return-box">
            <div class="return-type-row">
              <span class="return-label">宣告型別：</span>
              <span class="type-tag">{{ selectedOp.returns?.type || 'void' }}</span>
            </div>
            <div class="return-desc-row">
              <span class="return-label">內容說明：</span>
              <span>{{ selectedOp.returns?.description || '未確認' }}</span>
            </div>
          </div>
        </div>

        <!-- 實測結果與樣本 -->
        <div class="section-card">
          <h3 class="section-title">
            🧪 191 測試區實測記錄
          </h3>

          <div v-if="selectedOp.returnShape" class="shape-row">
            <span class="shape-label">資料結構輪廓：</span>
            <code class="shape-val">{{ selectedOp.returnShape }}</code>
          </div>

          <div v-if="selectedOp.softError" class="callout warn">
            <div class="callout-title">🟡 假成功警示 (Soft Error)</div>
            <div>服務回傳 HTTP 200，但回傳字串內含例外：<code>{{ selectedOp.softError }}</code></div>
          </div>

          <div v-if="selectedOp.faultString" class="callout danger">
            <div class="callout-title">🔴 SOAP Fault 原文</div>
            <div><code>{{ selectedOp.faultCode }}: {{ selectedOp.faultString }}</code></div>
          </div>

          <div v-if="selectedOp.error" class="callout danger">
            <div class="callout-title">❌ 連線 / 執行錯誤</div>
            <div><code>{{ selectedOp.error }}</code></div>
          </div>

          <div v-if="selectedOp.reason && selectedOp.status === 'skipped'" class="callout info">
            <div class="callout-title">ℹ️ 未實測原因</div>
            <div>{{ selectedOp.reason }}</div>
          </div>

          <div v-if="selectedOp.payloadSample" class="sample-box">
            <div class="sample-header">
              <span>📄 回傳字串樣本 (來自 {{ selectedOp.payloadPath }})</span>
              <button class="copy-btn" @click="copyText(selectedOp.payloadSample!, '回傳樣本')">複製完整樣本</button>
            </div>
            <pre class="code-box"><code>{{ selectedOp.payloadSample }}</code></pre>
          </div>
        </div>
      </div>
      <div v-else class="empty-detail">
        請由左側選取方法以查看手冊與規格
      </div>
    </main>
  </div>
</template>

<style scoped>
.manual-layout {
  display: flex;
  flex: 1;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.sidebar {
  width: 380px;
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.filter-bar {
  padding: 12px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-alt);
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

.filter-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.pill-btn {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--panel);
  color: var(--text-dim);
}
.pill-btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.pill-btn.read.active { background: var(--ok); border-color: var(--ok); }
.pill-btn.write.active { background: var(--warn); border-color: var(--warn); }
.pill-btn.ok.active { background: var(--ok); border-color: var(--ok); }

.filter-selects {
  display: flex;
  gap: 6px;
}
.mini-select {
  flex: 1;
  font-size: 12px;
  padding: 4px 8px;
}

.op-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 60px;
}

.op-item {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.op-item:hover {
  background: var(--bg);
}
.op-item.active {
  background: var(--accent-faint);
  border-left: 4px solid var(--accent);
}

.op-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.op-item-name {
  font-family: var(--mono);
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.op-item-purpose {
  font-size: 12px;
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.op-item-footer {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}
.op-item-time {
  margin-left: auto;
  color: var(--text-faint);
  font-size: 11px;
}

.empty-list {
  padding: 24px;
  text-align: center;
  color: var(--text-faint);
}

.detail-container {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  padding: 24px 32px 60px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.detail-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.detail-title {
  margin: 0;
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}
.sub-msg {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 4px;
  font-family: var(--mono);
}

.detail-actions {
  display: flex;
  gap: 8px;
}

.signature-box {
  background: #1e2430;
  color: #79c0ff;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-family: var(--mono);
  font-size: 13px;
  position: relative;
  margin-bottom: 20px;
}

.section-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.badge-count {
  font-size: 11px;
  font-weight: normal;
  color: var(--text-dim);
  background: var(--bg);
  padding: 2px 6px;
  border-radius: 999px;
}

.purpose-text {
  font-size: 14px;
  color: var(--text);
  line-height: 1.6;
}

.param-order {
  color: var(--text-faint);
  font-size: 11px;
  margin-right: 6px;
}
.param-name {
  font-family: var(--mono);
  font-weight: 600;
  color: var(--accent);
}
.type-tag {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--panel-alt);
  padding: 2px 6px;
  border-radius: 4px;
  color: #c7254e;
  border: 1px solid var(--border);
}
.seed-val {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text-dim);
}

.return-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}
.return-label {
  font-weight: 600;
  color: var(--text-dim);
  width: 80px;
  display: inline-block;
}

.shape-row {
  margin-bottom: 12px;
  font-size: 13px;
}
.shape-label {
  font-weight: 600;
  color: var(--text-dim);
}
.shape-val {
  font-family: var(--mono);
  color: var(--accent);
  background: var(--accent-soft);
  padding: 2px 8px;
  border-radius: 4px;
}

.sample-box {
  margin-top: 12px;
}
.sample-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
}

.empty-detail, .loading-box {
  padding: 60px;
  text-align: center;
  color: var(--text-faint);
  font-size: 15px;
}
</style>
