<script setup lang="ts">
import { computed } from 'vue';
import type { FieldCatalog, InstanceDetail } from '../api/types';

const props = defineProps<{
  detail: InstanceDetail | null;
  loading: boolean;
  catalog: FieldCatalog | null;
}>();

const emit = defineEmits<{ (e: 'close'): void }>();

/** 表格明細的欄位標題取自表單定義的 caption，比單頭欄位可靠得多。 */
const gridColumnNames = computed(() => {
  const names: Record<string, string> = {};
  for (const grid of props.catalog?.grids || []) {
    for (const column of grid.columns) names[column.id] = column.name;
  }
  return names;
});

function gridColumns(rows: Record<string, string>[]): string[] {
  const seen: string[] = [];
  for (const row of rows) {
    for (const key of Object.keys(row)) if (!seen.includes(key)) seen.push(key);
  }
  return seen;
}

function formatTime(value?: string | null) {
  return value ? value.replace('T', ' ').slice(0, 19) : '';
}
</script>

<template>
  <aside class="panel">
    <header class="panel-head">
      <h2>表單內容</h2>
      <button @click="emit('close')">關閉</button>
    </header>

    <p v-if="loading" class="state">載入中…</p>

    <template v-else-if="detail">
      <p v-if="detail.parseError" class="parse-error">
        表單解析失敗：{{ detail.parseError }}
      </p>

      <dl class="summary">
        <div><dt>流程單號</dt><dd>{{ detail.summary.processSerialNumber }}</dd></div>
        <div><dt>表單單號</dt><dd>{{ detail.summary.formSerialNumber || '（無）' }}</dd></div>
        <div><dt>表單</dt><dd>{{ detail.formId || '（查不到）' }}</dd></div>
        <div><dt>主旨</dt><dd>{{ detail.summary.subject || '（空白）' }}</dd></div>
        <div>
          <dt>申請人</dt>
          <dd>{{ detail.summary.requesterName }} {{ detail.summary.requesterId }}</dd>
        </div>
        <div>
          <dt>申請部門</dt>
          <dd>{{ detail.summary.orgUnitName }} {{ detail.summary.orgUnitId }}</dd>
        </div>
        <div><dt>狀態</dt><dd>{{ detail.summary.stateName }}</dd></div>
        <div><dt>申請日期</dt><dd>{{ formatTime(detail.summary.createdTime) }}</dd></div>
        <div v-if="detail.summary.abortComment" class="wide">
          <dt>作廢／終止原因</dt>
          <dd>{{ detail.summary.abortComment }}（{{ detail.summary.abortedBy }}）</dd>
        </div>
      </dl>

      <h3>欄位值<span class="count">{{ detail.fields.length }}</span></h3>
      <table class="kv">
        <tbody>
          <tr v-for="field in detail.fields" :key="field.id">
            <th :class="{ unnamed: !field.named }">
              {{ field.name }}
              <code v-if="field.named">{{ field.id }}</code>
            </th>
            <td>{{ detail.values[field.id] || '' }}</td>
          </tr>
        </tbody>
      </table>

      <template v-for="(rows, gridId) in detail.grids" :key="gridId">
        <h3>
          表格明細 · {{ gridId }}<span class="count">{{ rows.length }} 筆</span>
        </h3>
        <div class="scroll-x">
          <table class="grid">
            <thead>
              <tr>
                <th>#</th>
                <th v-for="column in gridColumns(rows)" :key="column">
                  {{ gridColumnNames[column] || column }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in rows" :key="index">
                <td>{{ index + 1 }}</td>
                <td v-for="column in gridColumns(rows)" :key="column">{{ row[column] || '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!rows.length" class="state">這張單的此表格沒有明細。</p>
      </template>

      <h3>簽核歷程<span class="count">{{ detail.workItems.length }} 關</span></h3>
      <table class="signs">
        <thead>
          <tr>
            <th>#</th><th>關卡</th><th>簽核人</th><th>收件</th><th>完成</th>
            <th>狀態</th><th>意見</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in detail.workItems" :key="index">
            <td>{{ index + 1 }}</td>
            <td>{{ item.workItemName }}</td>
            <td>{{ item.performerName }} {{ item.performerId }}</td>
            <td>{{ formatTime(item.createdTime) }}</td>
            <td>{{ formatTime(item.completedTime) }}</td>
            <td>{{ item.stateName }}</td>
            <td>{{ item.comment }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <p v-else class="state">在左邊的表格點一列，這裡會顯示該張單的表單內容。</p>
  </aside>
</template>

<style scoped>
.panel {
  width: min(560px, 42vw);
  border-left: 1px solid var(--border);
  background: var(--panel);
  overflow-y: auto;
  padding: 14px 16px 40px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  background: var(--panel);
  padding-bottom: 8px;
  z-index: 2;
}

.panel-head h2 {
  margin: 0;
  font-size: 15px;
}

.state {
  color: var(--text-faint);
  font-size: 13px;
  padding: 10px 0;
}

.parse-error {
  background: var(--danger-soft);
  color: var(--danger);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 14px;
  margin: 4px 0 16px;
}

.summary > div.wide {
  grid-column: 1 / -1;
}

.summary dt {
  font-size: 11px;
  color: var(--text-faint);
}

.summary dd {
  margin: 0;
  font-size: 13px;
  word-break: break-all;
}

h3 {
  font-size: 13px;
  margin: 18px 0 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-faint);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.kv th {
  text-align: left;
  width: 42%;
  padding: 4px 8px 4px 0;
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  vertical-align: top;
}

/* 名稱查不到就是欄位 ID，弱化顯示避免誤讀成中文名稱 */
.kv th.unnamed {
  font-weight: 400;
  color: var(--text-faint);
  font-family: var(--mono);
}

.kv th code {
  display: block;
  font-size: 10px;
  color: var(--text-faint);
  font-weight: 400;
}

.kv td {
  padding: 4px 0;
  border-bottom: 1px solid var(--border);
  word-break: break-all;
}

.scroll-x {
  overflow-x: auto;
}

.grid th,
.grid td,
.signs th,
.signs td {
  border: 1px solid var(--border);
  padding: 4px 6px;
  text-align: left;
  white-space: nowrap;
}

.grid th,
.signs th {
  background: var(--panel-alt);
}

.signs td:last-child {
  white-space: normal;
  max-width: 180px;
}
</style>
