<script setup lang="ts">
import { computed, inject, ref, watch, type Ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { activeHost, api, type FormDetail, type FormSummary, type FormUsage }
  from '../api/client';
import { useAsync } from '../composables/useAsync';
import { downloadCsv } from '../composables/useCsv';
import EntityList from '../components/EntityList.vue';
import StateBlock from '../components/StateBlock.vue';

const route = useRoute();
const router = useRouter();
const keyword = inject<Ref<string>>('keyword')!;
const showToast = inject<(m: string) => void>('showToast')!;

const list = useAsync<FormSummary[]>();
const detail = useAsync<FormDetail>();
const usage = useAsync<FormUsage[]>();
const highlighted = ref('');

list.run(() => api.listForms());

// 切換資料庫主機後整份清單都要重撈
watch(activeHost, () => list.run(() => api.listForms()));

const items = computed(() => {
  const low = keyword.value.trim().toLowerCase();
  return (list.data.value ?? [])
    .filter((f) => !low || f.form_id.toLowerCase().includes(low)
      || (f.form_name ?? '').toLowerCase().includes(low))
    .map((f) => ({ id: f.form_id, name: f.form_name }));
});

// 這張表單被哪些流程的哪些關卡使用（去重後的顯示標籤）
const usedBy = computed(() => [...new Set(
  (usage.data.value ?? []).map(
    (u) => `${u.process_name || u.process_id}／${u.activity_name || u.activity_id}`),
)]);

function select(id: string) {
  router.push(`/forms/${encodeURIComponent(id)}`);
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
  const form = detail.data.value;
  if (!form) return;
  downloadCsv(
    `${form.form_id}_fields.csv`,
    ['元件 ID', '名稱', '型別'],
    (form.fields ?? []).map((f) => [f.id, f.name, f.type]),
  );
}

watch(() => route.params.id, (id) => {
  const formId = typeof id === 'string' ? id : '';
  if (!formId) {
    detail.data.value = null;
    return;
  }
  detail.run(() => api.getForm(formId));
  usage.run(() => api.getFormUsage(formId));
}, { immediate: true });
</script>

<template>
  <div class="body">
    <StateBlock v-if="list.loading.value || list.error.value"
                :loading="list.loading.value" :error="list.error.value" />
    <EntityList v-else title="表單" :items="items"
                :active-id="String(route.params.id ?? '')" @select="select" />

    <main class="content">
      <div v-if="!route.params.id" class="state">請從左側選擇一張表單</div>

      <StateBlock v-else :loading="detail.loading.value" :error="detail.error.value">
        <div v-if="detail.data.value" class="card">
          <h2>{{ detail.data.value.form_name }}</h2>
          <div class="sub">
            <span class="mono">{{ detail.data.value.form_id }}</span>
            · v{{ detail.data.value.version }}
            · {{ detail.data.value.field_count }} 個元件
          </div>
        </div>

        <div v-if="detail.data.value" class="card">
          <div class="toolbar">
            <strong>元件清單</strong>
            <span class="spacer" />
            <button class="btn" @click="exportCsv">匯出 CSV</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th class="mono">元件 ID</th><th>名稱</th><th>型別</th></tr>
              </thead>
              <tbody>
                <tr v-for="field in detail.data.value.fields" :key="field.id"
                    :class="{ highlight: field.id === highlighted }">
                  <td class="mono id" @click="copy(field.id)">{{ field.id }}</td>
                  <td>{{ field.name }}</td>
                  <td class="mono">{{ field.type }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="toolbar"><strong>被哪些關卡使用</strong></div>
          <StateBlock :loading="usage.loading.value" :error="usage.error.value"
                      :empty="!usedBy.length" empty-text="沒有任何已發佈流程使用這張表單">
            <ul>
              <li v-for="label in usedBy" :key="label">{{ label }}</li>
            </ul>
          </StateBlock>
        </div>
      </StateBlock>
    </main>
  </div>
</template>
