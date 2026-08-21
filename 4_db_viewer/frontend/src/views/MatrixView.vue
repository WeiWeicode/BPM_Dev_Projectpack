<script setup lang="ts">
import { computed, inject, ref, watch, type Ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  api, PERMISSION_LABELS, WRITABLE_VALUES,
  type Health, type Matrix, type PermissionChange, type PermissionItem,
  type ProcessSummary, type WritablePermission,
} from '../api/client';
import { useAsync } from '../composables/useAsync';
import { downloadCsv } from '../composables/useCsv';
import EntityList from '../components/EntityList.vue';
import StateBlock from '../components/StateBlock.vue';
import PermissionBadge from '../components/PermissionBadge.vue';
import PermissionLegend from '../components/PermissionLegend.vue';

const route = useRoute();
const router = useRouter();
const keyword = inject<Ref<string>>('keyword')!;
const showToast = inject<(m: string) => void>('showToast')!;
const health = inject<Ref<Health | null>>('health')!;

const list = useAsync<ProcessSummary[]>();
const matrix = useAsync<Matrix>();
const only = ref<'all' | 'button' | 'field'>('all');
const highlighted = ref('');

// --- 編輯狀態：key 為 `${關卡ID}|${元件ID}` ---
const editing = ref(false);
const pending = ref(new Map<string, WritablePermission>());
const diff = ref<PermissionChange[] | null>(null);
const applying = ref(false);
const writeError = ref('');
const lastBackupId = ref('');

const processId = computed(() => String(route.params.id ?? ''));

// 後端沒開旗標、或這支流程不在白名單，就完全不顯示編輯功能
const canWrite = computed(() =>
  Boolean(health.value?.write_enabled)
  && (health.value?.writable_processes ?? []).includes(processId.value));

const items = computed(() => {
  const low = keyword.value.trim().toLowerCase();
  return (list.data.value ?? [])
    .filter((p) => !low || p.process_id.toLowerCase().includes(low)
      || (p.process_name ?? '').toLowerCase().includes(low))
    .map((p) => ({ id: p.process_id, name: p.process_name }));
});

list.run(() => api.listProcesses());

function select(id: string) {
  resetEditing();
  router.push(`/matrix/${encodeURIComponent(id)}`);
}

function load() {
  if (!processId.value) {
    matrix.data.value = null;
    return;
  }
  matrix.run(() => api.getMatrix(processId.value, only.value));
}

function cellKey(activityId: string, fieldId: string) {
  return `${activityId}|${fieldId}`;
}

function currentValue(activityId: string, fieldId: string,
                      stored: string | null | undefined): WritablePermission {
  const staged = pending.value.get(cellKey(activityId, fieldId));
  if (staged) return staged;
  // 未列出 = 唯讀(Disable)，不是「沿用預設」
  return (stored ?? 'DISABLE') as WritablePermission;
}

function isPending(activityId: string, fieldId: string) {
  return pending.value.has(cellKey(activityId, fieldId));
}

function stage(activityId: string, fieldId: string,
               stored: string | null | undefined, value: WritablePermission) {
  const key = cellKey(activityId, fieldId);
  const original = (stored ?? 'DISABLE') as WritablePermission;
  const next = new Map(pending.value);
  if (value === original) next.delete(key);
  else next.set(key, value);
  pending.value = next;
  diff.value = null;
}

/** 整欄套用：同一關卡的所有可見元件設成同一個值。 */
function applyColumn(activityId: string, value: WritablePermission) {
  const data = matrix.data.value;
  if (!data) return;
  const index = (data.columns ?? []).findIndex((c) => c.id === activityId);
  if (index < 0) return;
  const next = new Map(pending.value);
  for (const row of data.rows ?? []) {
    const cell = (row.cells ?? [])[index];
    if (!cell?.applicable) continue;          // 不屬於此關卡表單的元件不能設
    const stored = cell.permission ?? 'DISABLE';
    const key = cellKey(activityId, row.id);
    if (value === stored) next.delete(key);
    else next.set(key, value);
  }
  pending.value = next;
  diff.value = null;
}

function resetEditing() {
  pending.value = new Map();
  diff.value = null;
  writeError.value = '';
  lastBackupId.value = '';
}

/** pending 依關卡分組，因為 API 是一個關卡一次。 */
function groupPending(): Map<string, PermissionItem[]> {
  const grouped = new Map<string, PermissionItem[]>();
  for (const [key, permission] of pending.value) {
    const [activityId, fieldId] = key.split('|');
    const list = grouped.get(activityId) ?? [];
    list.push({ id: fieldId, permission });
    grouped.set(activityId, list);
  }
  return grouped;
}

async function preview() {
  writeError.value = '';
  const changes: PermissionChange[] = [];
  try {
    for (const [activityId, group] of groupPending()) {
      const result = await api.previewPermissions(processId.value, activityId, group);
      changes.push(...result.changes.filter((c) => c.changed));
    }
    diff.value = changes;
    if (!changes.length) showToast('沒有實際變更');
  } catch (err) {
    diff.value = null;
    writeError.value = err instanceof Error ? err.message : String(err);
  }
}

async function applyChanges() {
  applying.value = true;
  writeError.value = '';
  try {
    let backupId = '';
    for (const [activityId, group] of groupPending()) {
      // token 必須是套用當下取得的，過期代表資料被別人改過
      const previewed = await api.previewPermissions(processId.value, activityId, group);
      const result = await api.applyPermissions(processId.value, activityId, group,
                                                previewed.token);
      if (result.applied) backupId = result.backup_id;
    }
    lastBackupId.value = backupId;
    pending.value = new Map();
    diff.value = null;
    showToast(backupId ? `已套用，備份 ${backupId}` : '沒有實際變更');
    load();
  } catch (err) {
    writeError.value = err instanceof Error ? err.message : String(err);
  } finally {
    applying.value = false;
  }
}

async function restoreLast() {
  if (!lastBackupId.value) return;
  try {
    await api.restoreBackup(lastBackupId.value);
    showToast('已還原');
    lastBackupId.value = '';
    load();
  } catch (err) {
    writeError.value = err instanceof Error ? err.message : String(err);
  }
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
  const data = matrix.data.value;
  if (!data) return;
  downloadCsv(
    `${data.process_id}_matrix.csv`,
    ['元件 ID', '名稱', '型別', ...(data.columns ?? []).map((c) => c.name || c.id)],
    (data.rows ?? []).map((row) => [
      row.id, row.name ?? '', row.type ?? '',
      ...(row.cells ?? []).map((cell) => cell.permission ?? ''),
    ]),
  );
}

watch(() => [route.params.id, only.value], load, { immediate: true });
</script>

<template>
  <div class="body">
    <StateBlock v-if="list.loading.value || list.error.value"
                :loading="list.loading.value" :error="list.error.value" />
    <EntityList v-else title="流程" :items="items"
                :active-id="processId" @select="select" />

    <main class="content">
      <div v-if="!processId" class="state">請從左側選擇一支流程</div>

      <StateBlock v-else :loading="matrix.loading.value" :error="matrix.error.value">
        <template v-if="matrix.data.value">
          <div class="card">
            <h2>{{ matrix.data.value.process_name }}</h2>
            <div class="sub">
              <span class="mono">{{ matrix.data.value.process_id }}</span>
              · v{{ matrix.data.value.version }}
              · 關卡 × 元件權限矩陣
            </div>
          </div>

          <div class="card">
            <div class="toolbar">
              <button class="btn" :class="{ on: only === 'all' }" @click="only = 'all'">全部</button>
              <button class="btn" :class="{ on: only === 'button' }" @click="only = 'button'">
                只看按鈕
              </button>
              <button class="btn" :class="{ on: only === 'field' }" @click="only = 'field'">
                只看欄位
              </button>
              <span class="spacer" />
              <button v-if="canWrite" class="btn" :class="{ on: editing }"
                      @click="editing = !editing; resetEditing()">
                {{ editing ? '離開編輯' : '編輯權限' }}
              </button>
              <button class="btn" @click="exportCsv">匯出 CSV</button>
            </div>

            <div v-if="editing" class="edit-bar">
              <strong>{{ pending.size }} 項待套用</strong>
              <span class="spacer" />
              <button class="btn" :disabled="!pending.size" @click="preview">預覽差異</button>
              <button class="btn" :disabled="!pending.size || applying"
                      @click="applyChanges">
                {{ applying ? '套用中…' : '套用' }}
              </button>
              <button class="btn" :disabled="!pending.size" @click="resetEditing">
                全部取消
              </button>
              <button v-if="lastBackupId" class="btn" @click="restoreLast">
                還原這次變更
              </button>
            </div>

            <div v-if="writeError" class="state error">
              寫入被拒絕
              <pre>{{ writeError }}</pre>
            </div>

            <div v-if="diff" class="diff-box">
              <strong>將套用 {{ diff.length }} 項變更</strong>
              <div v-for="change in diff" :key="change.id" class="diff-row">
                <span class="mono">{{ change.id }}</span>
                <span v-if="change.name">（{{ change.name }}）</span>
                <span class="badge none">{{ change.before }}</span>
                →
                <span class="badge enabled">{{ change.after }}</span>
              </div>
              <div v-if="!diff.length" class="sub">沒有實際變更</div>
            </div>

            <StateBlock :empty="!(matrix.data.value.rows ?? []).length"
                        empty-text="這支流程沒有設定任何欄位權限">
              <div class="table-wrap">
                <table class="matrix">
                  <thead>
                    <tr>
                      <th class="sticky mono">元件</th>
                      <th v-for="column in matrix.data.value.columns" :key="column.id">
                        {{ column.name || column.id }}
                        <select v-if="editing" class="col-apply"
                                @change="applyColumn(column.id,
                                  ($event.target as HTMLSelectElement).value as WritablePermission);
                                  ($event.target as HTMLSelectElement).value = ''">
                          <option value="">整欄設為…</option>
                          <option v-for="value in WRITABLE_VALUES" :key="value" :value="value">
                            {{ PERMISSION_LABELS[value] }}
                          </option>
                        </select>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in matrix.data.value.rows" :key="row.id"
                        :class="{ 'is-button': row.is_button, highlight: row.id === highlighted }">
                      <td class="sticky mono id" @click="copy(row.id)">
                        {{ row.id }}
                        <span v-if="row.name" style="color: var(--text-dim)">（{{ row.name }}）</span>
                      </td>
                      <td v-for="(cell, index) in row.cells" :key="index"
                          :class="{ staged: editing
                                      && isPending(matrix.data.value.columns[index].id, row.id),
                                    na: !cell.applicable }">
                        <span v-if="!cell.applicable" class="badge none"
                              title="此元件不屬於該關卡所掛的表單">N/A</span>
                        <select v-else-if="editing"
                                :value="currentValue(matrix.data.value.columns[index].id,
                                                     row.id, cell.permission)"
                                @change="stage(matrix.data.value.columns[index].id, row.id,
                                  cell.permission,
                                  ($event.target as HTMLSelectElement).value as WritablePermission)">
                          <option v-for="value in WRITABLE_VALUES" :key="value" :value="value">
                            {{ PERMISSION_LABELS[value] }}
                          </option>
                        </select>
                        <PermissionBadge v-else :permission="cell.permission"
                                         :orphaned="cell.orphaned" />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <PermissionLegend />
            </StateBlock>
          </div>
        </template>
      </StateBlock>
    </main>
  </div>
</template>
