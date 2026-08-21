<script setup lang="ts">
import { computed, inject, ref, watch, type Ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api, type ProcessDetail, type ProcessSummary } from '../api/client';
import { useAsync } from '../composables/useAsync';
import { downloadCsv } from '../composables/useCsv';
import EntityList from '../components/EntityList.vue';
import StateBlock from '../components/StateBlock.vue';
import PermissionBadge from '../components/PermissionBadge.vue';
import PermissionLegend from '../components/PermissionLegend.vue';
import FlowPath from '../components/FlowPath.vue';

const route = useRoute();
const router = useRouter();
const keyword = inject<Ref<string>>('keyword')!;
const showToast = inject<(m: string) => void>('showToast')!;

const list = useAsync<ProcessSummary[]>();
const detail = useAsync<ProcessDetail>();
const highlighted = ref('');

list.run(() => api.listProcesses());

const items = computed(() => {
  const low = keyword.value.trim().toLowerCase();
  return (list.data.value ?? [])
    .filter((p) => !low || p.process_id.toLowerCase().includes(low)
      || (p.process_name ?? '').toLowerCase().includes(low))
    .map((p) => ({ id: p.process_id, name: p.process_name }));
});

function select(id: string) {
  router.push(`/processes/${encodeURIComponent(id)}`);
}

async function copy(text: string) {
  highlighted.value = text;
  try {
    await navigator.clipboard.writeText(text);
    showToast(`已複製 ${text}`);
  } catch {
    showToast('瀏覽器不允許複製，請手動選取');
  }
}

function exportCsv() {
  const process = detail.data.value;
  if (!process) return;
  downloadCsv(
    `${process.process_id}_activities.csv`,
    ['關卡 ID', '關卡名稱', 'BPMN 型別', '執行方式', '執行者', '表單', '按鈕權限', '欄位數'],
    (process.activities ?? []).map((a) => [
      a.id, a.name, a.bpmn_type ?? '', a.perform_type ?? '',
      (a.performers ?? []).join('/'), a.form_id ?? '',
      (a.buttons ?? []).map((b) => `${b.name || b.id}:${b.permission}`).join(' '),
      String((a.fields ?? []).length),
    ]),
  );
}

watch(() => route.params.id, (id) => {
  const processId = typeof id === 'string' ? id : '';
  if (!processId) {
    detail.data.value = null;
    return;
  }
  detail.run(() => api.getProcess(processId));
}, { immediate: true });
</script>

<template>
  <div class="body">
    <StateBlock v-if="list.loading.value || list.error.value"
                :loading="list.loading.value" :error="list.error.value" />
    <EntityList v-else title="流程" :items="items"
                :active-id="String(route.params.id ?? '')" @select="select" />

    <main class="content">
      <div v-if="!route.params.id" class="state">請從左側選擇一支流程</div>

      <StateBlock v-else :loading="detail.loading.value" :error="detail.error.value">
        <template v-if="detail.data.value">
          <div class="card">
            <h2>{{ detail.data.value.process_name }}</h2>
            <div class="sub">
              <span class="mono">{{ detail.data.value.process_id }}</span>
              · v{{ detail.data.value.version }}
              · {{ detail.data.value.flow_type }}
            </div>
            <FlowPath :activities="detail.data.value.activities ?? []" />
          </div>

          <div class="card">
            <div class="toolbar">
              <strong>關卡與按鈕權限</strong>
              <span class="spacer" />
              <RouterLink class="btn"
                          :to="`/matrix/${encodeURIComponent(detail.data.value.process_id)}`">
                看權限矩陣
              </RouterLink>
              <button class="btn" @click="exportCsv">匯出 CSV</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th class="mono">關卡 ID</th><th>關卡名稱</th><th>BPMN 型別</th>
                    <th>執行者</th><th>表單</th><th>按鈕權限</th><th>欄位數</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="activity in detail.data.value.activities" :key="activity.id"
                      :class="{ highlight: activity.id === highlighted }">
                    <td class="mono id" @click="copy(activity.id)">{{ activity.id }}</td>
                    <td>{{ activity.name }}</td>
                    <td class="mono">{{ activity.bpmn_type }}</td>
                    <td>{{ (activity.performers ?? []).join('、') || '—' }}</td>
                    <td class="mono">{{ activity.form_id || '—' }}</td>
                    <td>
                      <template v-if="(activity.buttons ?? []).length">
                        <span v-for="button in activity.buttons" :key="button.id">
                          {{ button.name || button.id }}
                          <PermissionBadge :permission="button.permission"
                                           :orphaned="button.orphaned" />
                        </span>
                      </template>
                      <span v-else class="badge none">—</span>
                    </td>
                    <td>{{ (activity.fields ?? []).length }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <PermissionLegend />
          </div>
        </template>
      </StateBlock>
    </main>
  </div>
</template>
