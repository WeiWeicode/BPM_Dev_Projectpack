<script setup lang="ts">
import { onMounted, provide, ref } from 'vue';
import { api } from './api/client';
import type { OverviewSummary } from './api/types';
import FormEditView from './views/FormEditView.vue';
import GuideView from './views/GuideView.vue';
import ManualView from './views/ManualView.vue';
import SeedsView from './views/SeedsView.vue';
import WorkbenchView from './views/WorkbenchView.vue';

const currentTab = ref<'manual' | 'workbench' | 'formEdit' | 'guide' | 'seeds'>('manual');
const overview = ref<OverviewSummary | null>(null);
const keyword = ref('');
const toast = ref('');

const targetWorkbenchOp = ref<string>('');
const targetWorkbenchMsg = ref<string>('');

provide('keyword', keyword);

function showToast(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    if (toast.value === message) toast.value = '';
  }, 2200);
}
provide('showToast', showToast);

async function loadOverview() {
  try {
    overview.value = await api.getOverview();
  } catch (err: any) {
    showToast('無法連線到後端 API 服務');
  }
}

function handleSelectWorkbench(opName: string, inputMsg?: string) {
  targetWorkbenchOp.value = opName;
  targetWorkbenchMsg.value = inputMsg || '';
  currentTab.value = 'workbench';
}

onMounted(loadOverview);
</script>

<template>
  <div class="app-container">
    <!-- 頂部導航列 -->
    <header class="app-header">
      <div class="header-left">
        <h1 class="app-title">
          <span>⚡ BPM WorkflowService API 檢視與實測工具</span>
        </h1>
        <span class="endpoint-badge">
          {{ overview?.endpoint || '10.10.130.191:8080' }}
        </span>
        <div v-if="overview" class="stats-pills">
          <span class="stat-pill">方法總數 <b>{{ overview.operationCount }}</b></span>
          <span class="stat-pill">已實測 <b>{{ overview.verifiedCount }}</b></span>
          <span class="stat-pill">已分析 <b>{{ overview.documentedCount }}</b></span>
          <span class="stat-pill">唯讀 <b>{{ overview.levelCounts.read }}</b> / 寫入 <b>{{ overview.levelCounts.write }}</b></span>
        </div>
      </div>

      <div class="header-right">
        <!-- 搜尋列（在手冊頁生效） -->
        <div v-if="currentTab === 'manual'" class="global-search">
          <span class="search-icon">🔍</span>
          <input
            v-model="keyword"
            type="search"
            placeholder="搜尋方法、參數或用途…"
          />
        </div>

        <!-- 頁籤導航 -->
        <nav class="nav-tabs">
          <button
            class="nav-tab"
            :class="{ active: currentTab === 'manual' }"
            @click="currentTab = 'manual'"
          >
            📑 API 手冊與目錄
          </button>
          <button
            class="nav-tab"
            :class="{ active: currentTab === 'workbench' }"
            @click="currentTab = 'workbench'"
          >
            ⚡ 即時實測工作台
          </button>
          <button
            class="nav-tab"
            :class="{ active: currentTab === 'formEdit' }"
            @click="currentTab = 'formEdit'"
          >
            📝 改單工作台
          </button>
          <button
            class="nav-tab"
            :class="{ active: currentTab === 'guide' }"
            @click="currentTab = 'guide'"
          >
            📖 呼叫前必讀
          </button>
          <button
            class="nav-tab"
            :class="{ active: currentTab === 'seeds' }"
            @click="currentTab = 'seeds'"
          >
            ⚙️ 種子資料庫
          </button>
        </nav>
      </div>
    </header>

    <!-- 視圖呈現 -->
    <main class="view-content">
      <ManualView
        v-if="currentTab === 'manual'"
        @select-workbench="handleSelectWorkbench"
      />
      <WorkbenchView
        v-else-if="currentTab === 'workbench'"
        :initial-operation-name="targetWorkbenchOp"
        :initial-input-message="targetWorkbenchMsg"
      />
      <FormEditView v-else-if="currentTab === 'formEdit'" />
      <GuideView v-else-if="currentTab === 'guide'" />
      <SeedsView v-else-if="currentTab === 'seeds'" />
    </main>

    <!-- Toast 訊息提示 -->
    <div v-if="toast" class="toast-msg">{{ toast }}</div>
  </div>
</template>
