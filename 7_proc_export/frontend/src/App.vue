<script setup lang="ts">
import { onMounted, provide, ref } from 'vue';
import { api } from './api/client';
import type { MetaInfo } from './api/types';
import ExportView from './views/ExportView.vue';

const meta = ref<MetaInfo | null>(null);
const host = ref('');
const toast = ref('');
const loadError = ref('');

function showToast(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    if (toast.value === message) toast.value = '';
  }, 3000);
}
provide('showToast', showToast);

async function loadMeta() {
  try {
    meta.value = await api.meta();
    host.value = meta.value.defaultHost || meta.value.hosts[0]?.key || '';
  } catch (err: any) {
    loadError.value = err?.message || '無法取得服務設定';
  }
}

function currentHost() {
  return meta.value?.hosts.find((h) => h.key === host.value) || null;
}

onMounted(loadMeta);
</script>

<template>
  <header class="app-header">
    <div class="brand">BPM 流程與表單匯出</div>

    <select v-if="meta" v-model="host" class="host-select">
      <option v-for="h in meta.hosts" :key="h.key" :value="h.key">{{ h.label }}</option>
    </select>

    <span class="tag readonly">唯讀</span>
    <span v-if="currentHost()?.production" class="tag production">正式區資料</span>
    <span v-if="currentHost()" class="addr">{{ currentHost()!.address }}</span>

    <div class="spacer"></div>
    <span v-if="meta" class="hint">
      單次匯出上限 {{ meta.maxExportRows.toLocaleString() }} 筆
    </span>
  </header>

  <p v-if="loadError" class="fatal">{{ loadError }}</p>

  <ExportView v-else-if="meta && host" :host="host" :meta="meta" :key="host" />

  <div v-if="toast" class="toast">{{ toast }}</div>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 20;
}

.brand {
  font-weight: 700;
  font-size: 15px;
}

.host-select {
  padding: 5px 10px;
}

.tag {
  font-size: 12px;
  padding: 2px 9px;
  border-radius: 20px;
  font-weight: 600;
}

.tag.readonly {
  background: var(--ok-soft);
  color: var(--ok);
}

/* 正式區用警示色：唯讀歸唯讀，人得一眼看出自己正在看哪一區的資料 */
.tag.production {
  background: var(--danger-soft);
  color: var(--danger);
}

.addr {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text-faint);
}

.spacer {
  flex: 1;
}

.hint {
  font-size: 12px;
  color: var(--text-dim);
}

.fatal {
  margin: 40px auto;
  max-width: 560px;
  padding: 16px 18px;
  border-radius: var(--radius);
  background: var(--danger-soft);
  color: var(--danger);
}

.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--text);
  color: #fff;
  padding: 10px 18px;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow);
  z-index: 100;
  max-width: 70vw;
}
</style>
