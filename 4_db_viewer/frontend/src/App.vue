<script setup lang="ts">
import { onMounted, provide, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { activeHost, api, setActiveHost, type Health } from './api/client';

const route = useRoute();
const router = useRouter();
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

async function loadHealth() {
  try {
    health.value = await api.health();
    // 首次進站沒有選過主機，就採用後端的預設值
    if (!activeHost.value && health.value?.host) setActiveHost(health.value.host);
  } catch {
    health.value = { ok: false, error: '無法連線到後端' } as Health;
  }
}

/** 切換主機：清掉選定的項目，回到清單首頁重新載入。 */
function switchHost(key: string) {
  if (key === activeHost.value) return;
  setActiveHost(key);
  loadHealth();
  router.replace(`/${String(route.name ?? 'forms')}`);
}

onMounted(loadHealth);
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>BPM 線上結構檢視器</h1>
      <select v-if="(health?.hosts ?? []).length" class="host-select"
              :class="{ production: health?.production }"
              :value="health?.host"
              @change="switchHost(($event.target as HTMLSelectElement).value)">
        <option v-for="option in health?.hosts ?? []" :key="option.key" :value="option.key">
          {{ option.label }}（{{ option.address }}）
        </option>
      </select>
      <span v-if="health?.production" class="prod-flag">正式區</span>
      <span v-if="health?.write_allowed_here" class="writable"
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
