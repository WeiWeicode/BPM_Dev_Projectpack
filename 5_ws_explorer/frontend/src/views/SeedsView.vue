<script setup lang="ts">
import { inject, onMounted, ref } from 'vue';
import { api } from '../api/client';
import type { SeedsData } from '../api/types';

const showToast = inject<(msg: string) => void>('showToast', () => {});
const seedsData = ref<SeedsData | null>(null);
const loading = ref(false);

async function loadSeeds() {
  loading.value = true;
  try {
    seedsData.value = await api.getSeeds();
  } catch (err: any) {
    showToast(err.message || '載入種子資料失敗');
  } finally {
    loading.value = false;
  }
}

function copyText(text: string, label: string) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`已複製 ${label}`);
  });
}

onMounted(loadSeeds);
</script>

<template>
  <div class="seeds-container">
    <div class="seeds-header">
      <h2>⚙️ 實測參數種子資料庫 (seeds.json)</h2>
      <p class="seeds-subtitle">
        提供 65 支方法實測時共用的參數預設值。記錄各參數的來源出處（從哪支 API 取得），換測試環境或流程時可依循更新。
      </p>
    </div>

    <div v-if="loading" class="loading-box">載入中…</div>
    <div v-else-if="seedsData" class="seeds-content">
      <!-- 1. 共用種子表 -->
      <div class="section-card">
        <h3 class="section-title">
          📌 全域共用參數種子 (共 {{ Object.keys(seedsData.seeds).length }} 項)
        </h3>

        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 25%">參數名稱 (WSDL 欄位名)</th>
              <th style="width: 35%">預設值</th>
              <th style="width: 40%">來源出處說明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(val, key) in seedsData.seeds" :key="key">
              <td>
                <code class="param-key">{{ key }}</code>
              </td>
              <td>
                <div class="val-cell">
                  <code class="param-val">{{ val }}</code>
                  <button class="btn-copy-mini" @click="copyText(String(val), String(key))">複製</button>
                </div>
              </td>
              <td class="source-desc">
                {{ seedsData.sources[key] || '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 2. 特定方法覆寫 -->
      <div class="section-card">
        <h3 class="section-title">
          🔀 依方法獨立覆寫 (_overrides)
        </h3>
        <p class="text-dim-desc">
          同名參數在不同方法需要不同狀態的單據（例如作廢註記只有已終止的單才能查到），在此個別覆寫：
        </p>

        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 30%">方法名稱</th>
              <th style="width: 70%">覆寫參數與設定值</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(overrideObj, methodName) in seedsData.overrides" :key="methodName">
              <td>
                <code class="method-key">{{ methodName }}</code>
              </td>
              <td>
                <div v-for="(oVal, oKey) in overrideObj" :key="oKey" class="override-item">
                  <span class="param-key">{{ oKey }}</span> = <code class="param-val">{{ oVal }}</code>
                  <button class="btn-copy-mini" @click="copyText(String(oVal), String(oKey))">複製</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.seeds-container {
  flex: 1;
  overflow-y: auto;
  padding: 32px 48px;
  max-width: 960px;
  margin: 0 auto;
}

.seeds-header {
  margin-bottom: 24px;
}
.seeds-header h2 {
  margin: 0 0 8px 0;
  font-size: 22px;
  color: var(--text);
}
.seeds-subtitle {
  margin: 0;
  color: var(--text-dim);
  font-size: 14px;
}

.section-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 15px;
  color: var(--text);
}

.text-dim-desc {
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 12px;
}

.param-key {
  font-family: var(--mono);
  font-weight: 600;
  color: var(--accent);
}
.param-val {
  font-family: var(--mono);
  color: var(--text);
  background: var(--bg);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.val-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: space-between;
}

.btn-copy-mini {
  font-size: 10px;
  padding: 1px 6px;
  flex-shrink: 0;
}

.source-desc {
  color: var(--text-dim);
  font-size: 12px;
}

.method-key {
  font-family: var(--mono);
  font-weight: 600;
  color: #d46b08;
}

.override-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.loading-box {
  padding: 60px;
  text-align: center;
  color: var(--text-faint);
}
</style>
