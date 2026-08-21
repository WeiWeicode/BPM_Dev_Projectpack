<script setup lang="ts">
import { onMounted, provide, ref } from 'vue';
import { api, type Health } from './api/client';

const health = ref<Health | null>(null);
const keyword = ref('');
const toast = ref('');

provide('keyword', keyword);
provide('health', health);

function showToast(message: string) {
  toast.value = message;
  window.setTimeout(() => { toast.value = ''; }, 1600);
}
provide('showToast', showToast);

onMounted(async () => {
  try {
    health.value = await api.health();
  } catch {
    health.value = { ok: false, error: '無法連線到後端' } as Health;
  }
});
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>BPM 線上結構檢視器</h1>
      <span v-if="health?.write_enabled" class="writable"
            :title="`可寫入的流程：${(health.writable_processes ?? []).join('、') || '（白名單為空，全部禁止）'}`">
        可編輯
      </span>
      <span v-else class="readonly">唯讀</span>
      <span class="meta">
        <template v-if="health?.ok">{{ health.database }} · 僅 RELEASED</template>
        <template v-else-if="health">連線失敗：{{ health.error }}</template>
        <template v-else>連線中…</template>
      </span>
      <div class="search-box">
        <input v-model="keyword" type="search" placeholder="搜尋 ID 或名稱…">
      </div>
      <nav class="tabs">
        <RouterLink to="/forms" :class="{ active: $route.name === 'forms' }">表單</RouterLink>
        <RouterLink to="/processes" :class="{ active: $route.name === 'processes' }">流程</RouterLink>
        <RouterLink to="/matrix" :class="{ active: $route.name === 'matrix' }">矩陣</RouterLink>
      </nav>
    </header>

    <RouterView />

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>
