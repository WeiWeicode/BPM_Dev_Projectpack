<script setup lang="ts">
import { computed, ref } from 'vue';
import type { FieldCatalog } from '../api/types';

const props = defineProps<{
  catalog: FieldCatalog;
  selected: string[];
  selectedGrids: string[];
}>();

const emit = defineEmits<{
  (e: 'update', fieldIds: string[]): void;
  (e: 'updateGrids', gridIds: string[]): void;
  (e: 'close'): void;
}>();

const keyword = ref('');
const onlyNamed = ref(false);

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  return props.catalog.fields.filter((f) => {
    if (onlyNamed.value && !f.named) return false;
    if (!kw) return true;
    return f.id.toLowerCase().includes(kw) || f.name.toLowerCase().includes(kw);
  });
});

function toggle(fieldId: string) {
  const next = props.selected.includes(fieldId)
    ? props.selected.filter((id) => id !== fieldId)
    : [...props.selected, fieldId];
  emit('update', next);
}

function toggleGrid(gridId: string) {
  const next = props.selectedGrids.includes(gridId)
    ? props.selectedGrids.filter((id) => id !== gridId)
    : [...props.selectedGrids, gridId];
  emit('updateGrids', next);
}

function selectAllVisible() {
  const merged = new Set(props.selected);
  filtered.value.forEach((f) => merged.add(f.id));
  emit('update', [...merged]);
}

function clearAll() {
  emit('update', []);
}

const sourceLabel: Record<string, string> = {
  definition: '表單定義',
  definition_only: '定義有、抽樣單據未出現',
  instance_only: '單據有、定義沒有',
};
</script>

<template>
  <div class="drawer-backdrop" @click.self="emit('close')">
    <aside class="drawer">
      <header class="drawer-head">
        <div>
          <h2>選取欄位</h2>
          <p class="sub">
            勾選的欄位會加進表格、成為可查詢條件，並匯出到「內容」工作表。
          </p>
        </div>
        <button @click="emit('close')">關閉</button>
      </header>

      <div class="coverage">
        <span>
          共 {{ catalog.fields.length }} 個欄位，其中
          <strong>{{ catalog.labelCoverage.named }}</strong> 個查得到中文名稱。
        </span>
        <span class="note">
          查不到名稱的欄位顯示欄位 ID —— 表單定義裡沒有填標籤，不是漏抓。
        </span>
        <span v-if="catalog.parseFailures" class="warn-note">
          抽樣的 {{ catalog.sampled }} 張單中有 {{ catalog.parseFailures }} 張表單解析失敗，
          那些單上的欄位可能沒被列進來。
        </span>
      </div>

      <div class="drawer-tools">
        <input v-model="keyword" placeholder="搜尋欄位名稱或 ID…" />
        <label class="check">
          <input type="checkbox" v-model="onlyNamed" />
          只看有中文名稱的
        </label>
        <button @click="selectAllVisible">全選目前清單</button>
        <button @click="clearAll">清空</button>
      </div>

      <div class="field-list">
        <label v-for="field in filtered" :key="field.id" class="field-row">
          <input
            type="checkbox"
            :checked="selected.includes(field.id)"
            @change="toggle(field.id)"
          />
          <span class="field-name" :class="{ unnamed: !field.named }">
            {{ field.name }}
          </span>
          <code class="field-id">{{ field.id }}</code>
          <span class="field-type">{{ field.type }}</span>
          <span class="field-source">{{ sourceLabel[field.source] || field.source }}</span>
        </label>
        <p v-if="!filtered.length" class="empty">沒有符合的欄位。</p>
      </div>

      <div v-if="catalog.grids.length" class="grid-section">
        <h3>表格明細</h3>
        <p class="sub">
          表格明細一列一筆，匯出時每個表格自成一個工作表，不會塞進單頭的儲存格。
        </p>
        <label v-for="grid in catalog.grids" :key="grid.id" class="grid-row">
          <input
            type="checkbox"
            :checked="selectedGrids.includes(grid.id)"
            @change="toggleGrid(grid.id)"
          />
          <span class="field-name">{{ grid.name }}</span>
          <code class="field-id">{{ grid.id }}</code>
          <span class="field-type">{{ grid.columns.length }} 欄</span>
        </label>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(20, 30, 60, .25);
  z-index: 50;
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: min(620px, 92vw);
  background: var(--panel);
  height: 100%;
  overflow-y: auto;
  padding: 18px 20px 40px;
  box-shadow: var(--shadow);
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.drawer-head h2 {
  margin: 0 0 4px;
  font-size: 16px;
}

.sub {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}

.coverage {
  margin: 14px 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--accent-faint);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.coverage .note {
  color: var(--text-dim);
}

.coverage .warn-note {
  color: var(--warn);
}

.drawer-tools {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.drawer-tools input[type='text'],
.drawer-tools input:not([type]) {
  flex: 1;
  min-width: 180px;
}

.check {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  white-space: nowrap;
}

.field-list {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  max-height: 52vh;
  overflow-y: auto;
}

.field-row,
.grid-row {
  display: grid;
  grid-template-columns: 22px minmax(90px, 1fr) minmax(120px, 1.3fr) 80px 130px;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  cursor: pointer;
}

.field-row:last-child {
  border-bottom: none;
}

.field-row:hover,
.grid-row:hover {
  background: var(--accent-faint);
}

.field-name {
  font-weight: 600;
}

/* 名稱查不到時弱化顯示，避免把欄位 ID 誤讀成中文名稱 */
.field-name.unnamed {
  font-weight: 400;
  color: var(--text-faint);
  font-style: italic;
}

.field-id {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
}

.field-type,
.field-source {
  font-size: 11px;
  color: var(--text-faint);
}

.empty {
  padding: 14px;
  text-align: center;
  color: var(--text-faint);
}

.grid-section {
  margin-top: 20px;
}

.grid-section h3 {
  margin: 0 0 4px;
  font-size: 14px;
}

.grid-row {
  grid-template-columns: 22px minmax(90px, 1fr) minmax(120px, 1.3fr) 80px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-top: 6px;
}
</style>
