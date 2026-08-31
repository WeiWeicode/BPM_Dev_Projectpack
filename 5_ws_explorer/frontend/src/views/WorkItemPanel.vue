<script setup lang="ts">
/**
 * 關卡操作面板：看歷程 → 挑一個「以誰的身分操作」→ 簽收／改表單簽核／轉派／取回／收單。
 *
 * 這組 API 沒有登入概念，操作者一律由參數指定，指定錯了會被擋
 * （acceptWorkItem 的 pUserId 必須是待辦目前擁有者、assigneeReassignWorkItem
 * 的 pRequesterOID 也是）。所以這裡直接把目前關卡的待辦人列出來當身分選擇，
 * 使用者不必自己查是誰、也不必記 Users.OID。
 */
import { computed, inject, ref, watch } from 'vue';
import { api, ApiError } from '../api/client';
import type { ActivityBoard, CurrentPerformer, FormFieldInfo } from '../api/types';

const props = defineProps<{ serialNo: string }>();
const emit = defineEmits<{ (e: 'changed'): void }>();

const showToast = inject<(m: string) => void>('showToast', () => {});

const board = ref<ActivityBoard | null>(null);
const loading = ref(false);
const busy = ref(false);
const actingIndex = ref(0);
const log = ref<{ ok: boolean; text: string }[]>([]);

// 簽核
const comment = ref('');
const editWithComplete = ref(false);
const fields = ref<FormFieldInfo[]>([]);
const edited = ref<Record<string, string>>({});

// 轉派
const reassignMode = ref<'management' | 'assignee' | 'owner'>('management');
const acceptorId = ref('');
const reassignComment = ref('');

// 取回重辦
const reexecuteActivityId = ref('');
const reexecuteComment = ref('');

// 收單
const closeMode = ref<'abort' | 'terminate'>('abort');
const closeComment = ref('');

const acting = computed<CurrentPerformer | null>(
  () => board.value?.currentPerformers[actingIndex.value] || null,
);

const completedActivities = computed(
  () => (board.value?.activities || []).filter((a) => a.state === 'closed.completed' && a.activityId),
);

const changedTags = computed(() =>
  fields.value.filter((f) => (edited.value[f.tag] ?? f.value) !== f.value).map((f) => f.tag),
);

const changes = computed(() => {
  const out: Record<string, string> = {};
  for (const tag of changedTags.value) out[tag] = edited.value[tag] ?? '';
  return out;
});

function note(ok: boolean, text: string) {
  log.value.unshift({ ok, text });
  showToast(text);
}

function fail(err: any) {
  const msg = err instanceof ApiError ? err.message : String(err?.message || err);
  log.value.unshift({ ok: false, text: msg });
  showToast(msg);
}

async function load() {
  if (!props.serialNo) return;
  loading.value = true;
  try {
    board.value = await api.getBoard(props.serialNo);
    actingIndex.value = 0;
    reexecuteActivityId.value = completedActivities.value[0]?.activityId || '';
  } catch (err) {
    board.value = null;
    fail(err);
  } finally {
    loading.value = false;
  }
}

async function loadFields() {
  try {
    const detail = await api.loadEditInstance(props.serialNo);
    fields.value = detail.fields;
    edited.value = {};
    for (const f of detail.fields) edited.value[f.tag] = f.value;
  } catch (err) {
    fields.value = [];
    fail(err);
  }
}

watch(() => props.serialNo, load, { immediate: true });
watch(editWithComplete, (on) => {
  if (on && !fields.value.length) loadFields();
});

async function run(label: string, fn: () => Promise<{ message?: string | null }>) {
  if (!confirmed.value) return showToast('請先勾選確認');
  busy.value = true;
  try {
    const res = await fn();
    note(true, `${label}：${res.message || '完成'}`);
    await load();
    emit('changed');
  } catch (err) {
    fail(err);
  } finally {
    busy.value = false;
  }
}

const confirmed = ref(false);

function acceptItem() {
  const p = acting.value;
  if (!p?.workItemOID) return showToast('這個關卡查不到工作項目 OID');
  return run('簽收', () =>
    api.acceptWorkItem({ workItemOID: p.workItemOID!, userId: p.userId!, confirm: true }));
}

function completeItem() {
  const p = acting.value;
  if (!p?.workItemOID) return showToast('這個關卡查不到工作項目 OID');
  return run('簽核', () =>
    api.completeWorkItem({
      serialNo: props.serialNo,
      workItemOID: p.workItemOID!,
      userId: p.userId!,
      comment: comment.value,
      changes: editWithComplete.value ? changes.value : {},
      confirm: true,
    }));
}

function doReassign() {
  const p = acting.value;
  if (!p?.workItemOID) return showToast('這個關卡查不到工作項目 OID');
  if (!acceptorId.value.trim()) return showToast('請輸入接收者員工編號');
  return run('轉派', () =>
    api.reassignWorkItem({
      workItemOID: p.workItemOID!,
      acceptorId: acceptorId.value.trim(),
      comment: reassignComment.value,
      mode: reassignMode.value,
      requesterId: p.userId || '',
      confirm: true,
    }));
}

function doReexecute() {
  if (!reexecuteActivityId.value) return showToast('請選要取回的關卡');
  return run('取回重辦', () =>
    api.reexecuteActivity({
      serialNo: props.serialNo,
      askUserId: acting.value?.userId || '',
      activityId: reexecuteActivityId.value,
      comment: reexecuteComment.value,
      confirm: true,
    }));
}

function doClose() {
  return run('收單', () =>
    api.closeProcess({
      serialNo: props.serialNo,
      mode: closeMode.value,
      userId: acting.value?.userId || '',
      comment: closeComment.value,
      confirm: true,
    }));
}

function stateText(state?: string | null) {
  if (!state) return '—';
  if (state === 'closed.completed') return '已完成';
  if (state === 'closed.terminated') return '已終止';
  if (state === 'closed.aborted') return '已作廢';
  if (state.startsWith('open.')) return '進行中';
  return state;
}
</script>

<template>
  <div v-if="loading" class="placeholder">讀取關卡中…</div>
  <div v-else-if="!board" class="placeholder">從左邊挑一張單，或直接輸入單號。</div>

  <template v-else>
    <div class="doc-header">
      <div class="doc-title">
        <span class="badge" :class="board.closed ? 'read' : 'write'">
          {{ stateText(board.processState) }}
        </span>
        {{ board.subject || '（無主旨）' }}
      </div>
      <div class="doc-meta mono">
        {{ board.serialNo }} · {{ board.processName }} ·
        {{ board.activities.length }} 個關卡 · 讀取 {{ board.elapsedMs }} ms
      </div>
    </div>

    <!-- 關卡歷程 -->
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 26%">關卡</th>
            <th style="width: 12%">狀態</th>
            <th style="width: 22%">簽核者 / 知會</th>
            <th style="width: 18%">開始時間</th>
            <th>意見</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(a, i) in board.activities" :key="`${a.activityId}-${i}`" :class="{ live: a.running }">
            <td>
              <span class="field-name">{{ a.activityName || '—' }}</span>
              <div class="mono field-id">{{ a.activityId }}</div>
            </td>
            <td>
              <span class="badge" :class="a.running ? 'write' : 'read'">{{ stateText(a.state) }}</span>
            </td>
            <td class="mono small">
              {{ a.performerIds.join('、') || '—' }}
              <div v-if="a.notifiedIds.length" class="dtype">知會 {{ a.notifiedIds.join('、') }}</div>
            </td>
            <td class="mono small">{{ a.startedTime || '—' }}</td>
            <td class="small">{{ a.comments.join(' / ') || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="board.closed" class="callout warn">
      <div class="callout-title">這張單已經結案</div>
      <p>沒有進行中的關卡，簽核／轉派／取回都不適用。表單值仍可在「改既有單」模式修改。</p>
    </div>

    <template v-else>
      <!-- 身分模擬 -->
      <div class="actor-box">
        <div class="actor-title">🎭 以誰的身分操作</div>
        <p class="hint">
          這組 API 沒有登入概念，操作者由參數指定，而且指定錯會被拒絕
          （簽收與自行轉派都要求是待辦目前擁有者）。下面列的是目前關卡實際的待辦人。
        </p>
        <div v-if="!board.currentPerformers.length" class="callout warn">
          <div class="callout-title">目前關卡查不到待辦人</div>
          <p>可能是通知類關卡，或待辦人已離職／未解析出來。</p>
        </div>
        <div v-else class="actor-list">
          <button
            v-for="(p, i) in board.currentPerformers"
            :key="`${p.userId}-${p.activityId}`"
            class="actor-btn"
            :class="{ active: i === actingIndex }"
            @click="actingIndex = i"
          >
            <span class="actor-name">{{ p.userName || '—' }}（{{ p.userId }}）</span>
            <span class="actor-sub mono">{{ p.activityName }} · {{ p.activityId }}</span>
            <span class="actor-sub">
              {{ p.accepted ? '✅ 已簽收' : '⬜ 未簽收' }} ·
              待辦 {{ p.workItemOID ? p.workItemOID.slice(0, 12) + '…' : '查不到' }}
            </span>
          </button>
        </div>
        <div class="hint mono">Users.OID 來源：{{ board.oidSource }}</div>
      </div>

      <div v-if="!board.reassignAvailable" class="callout warn">
        <div class="callout-title">轉派功能不可用</div>
        <p>{{ board.oidSource }} —— 轉派要 Users.OID，只能查唯讀資料庫。其餘操作不受影響。</p>
      </div>

      <!-- 操作區 -->
      <div class="ops-grid">
        <div class="op-card">
          <div class="op-title">① 簽收 / 簽核推進</div>
          <label class="mini-label">簽核意見（pComment）</label>
          <input v-model="comment" type="text" placeholder="同意" />
          <label class="inline-check">
            <input v-model="editWithComplete" type="checkbox" />
            <span>簽核前順便改表單欄位</span>
          </label>
          <div v-if="editWithComplete" class="inline-fields">
            <div v-if="!fields.length" class="hint">讀取欄位中…</div>
            <div v-for="f in fields" :key="f.tag" class="inline-field">
              <span class="inline-field-name">{{ f.name || f.id }}</span>
              <input v-model="edited[f.tag]" class="mono" type="text" />
            </div>
            <div class="hint">
              表單先寫入並讀回驗證，驗證不過就中止簽核、流程不會被推動。
              已改 {{ changedTags.length }} 欄。
            </div>
          </div>
          <div class="btn-row">
            <button :disabled="busy || !acting?.workItemOID" @click="acceptItem">簽收</button>
            <button class="primary" :disabled="busy || !acting?.workItemOID" @click="completeItem">
              簽核推進下一關
            </button>
          </div>
        </div>

        <div class="op-card">
          <div class="op-title">② 轉派</div>
          <label class="mini-label">方式</label>
          <select v-model="reassignMode">
            <option value="management">管理者強制轉派（不需目前擁有者同意）</option>
            <option value="assignee">簽核者自行轉派（以上方身分送出）</option>
            <option value="owner">變更擁有者</option>
          </select>
          <label class="mini-label">接收者員工編號</label>
          <input v-model="acceptorId" class="mono" type="text" placeholder="例如 S094009" />
          <label class="mini-label">轉派意見</label>
          <input v-model="reassignComment" type="text" />
          <div class="btn-row">
            <button
              :disabled="busy || !acting?.workItemOID || !board.reassignAvailable"
              @click="doReassign"
            >
              轉派
            </button>
          </div>
        </div>

        <div class="op-card">
          <div class="op-title">③ 取回重辦</div>
          <p class="hint">
            把已簽核的關卡叫回來。實測效果：目前關卡變<b>已終止</b>，被取回的關卡重新開啟。
          </p>
          <label class="mini-label">要取回的關卡</label>
          <select v-model="reexecuteActivityId">
            <option v-for="a in completedActivities" :key="a.activityId || ''" :value="a.activityId || ''">
              {{ a.activityName }}（{{ a.activityId }}）
            </option>
          </select>
          <label class="mini-label">取回意見</label>
          <input v-model="reexecuteComment" type="text" />
          <div class="btn-row">
            <button :disabled="busy || !reexecuteActivityId" @click="doReexecute">取回重辦</button>
          </div>
        </div>

        <div class="op-card">
          <div class="op-title">④ 收單</div>
          <label class="mini-label">方式</label>
          <select v-model="closeMode">
            <option value="abort">作廢（closed.aborted，不需操作者）</option>
            <option value="terminate">終止（closed.terminated，需有權限的操作者）</option>
          </select>
          <label class="mini-label">意見</label>
          <input v-model="closeComment" type="text" />
          <p class="hint">
            實測：終止會檢查操作者權限，回
            <code>The user(id=…) cannot terminat this process</code> 時改用作廢通常可行。
          </p>
          <div class="btn-row">
            <button class="danger" :disabled="busy" @click="doClose">收掉整張單</button>
          </div>
        </div>
      </div>

      <div class="safety-box">
        <label class="safety-check">
          <input v-model="confirmed" type="checkbox" />
          <span>
            我了解上面每個操作都會<b>實際改變 191 測試區的流程狀態</b>且無法復原，
            並確認要以
            <b>{{ acting ? `${acting.userName}（${acting.userId}）` : '（未選身分）' }}</b>
            的身分送出
          </span>
        </label>
      </div>
    </template>

    <div v-if="log.length" class="result-box">
      <div class="result-title">操作紀錄</div>
      <ul class="log-list">
        <li v-for="(l, i) in log" :key="i" :class="l.ok ? 'ok' : 'bad'">
          {{ l.ok ? '✅' : '❌' }} {{ l.text }}
        </li>
      </ul>
    </div>
  </template>
</template>

<style scoped>
.placeholder {
  color: var(--text-dim);
  padding: 40px 12px;
  text-align: center;
}

.doc-header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
  margin-bottom: 12px;
}

.doc-title {
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.doc-meta {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 5px;
}

.table-scroll {
  overflow-x: auto;
}

.data-table tr.live td {
  background: var(--accent-faint);
}

.field-name {
  font-weight: 500;
}

.field-id,
.small {
  font-size: 11px;
}

.field-id {
  color: var(--text-dim);
  word-break: break-all;
}

.dtype {
  font-size: 10px;
  color: var(--text-faint);
  margin-top: 2px;
}

.actor-box {
  margin-top: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: var(--panel-alt);
}

.actor-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.actor-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0;
}

.actor-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  text-align: left;
  padding: 8px 10px;
}

.actor-btn.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.actor-name {
  font-weight: 600;
  font-size: 13px;
}

.actor-sub {
  font-size: 11px;
  color: var(--text-dim);
}

.ops-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.op-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
}

.op-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
}

.op-card input,
.op-card select {
  width: 100%;
}

.mini-label {
  display: block;
  font-size: 11px;
  color: var(--text-dim);
  margin: 8px 0 3px;
}

.inline-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  margin-top: 10px;
  cursor: pointer;
}

.inline-check input {
  width: auto;
}

.inline-fields {
  margin-top: 8px;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
}

.inline-field {
  margin-bottom: 6px;
}

.inline-field-name {
  display: block;
  font-size: 11px;
  color: var(--text-dim);
}

.hint {
  color: var(--text-dim);
  font-size: 12px;
  margin-top: 6px;
}

.btn-row {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.safety-box {
  margin-top: 14px;
  background: var(--warn-soft);
  border: 1px solid rgba(200, 135, 26, .35);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}

.safety-check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  cursor: pointer;
}

.result-box {
  margin-top: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: var(--panel-alt);
}

.result-title {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
}

.log-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
}

.log-list li.bad {
  color: var(--danger);
}
</style>
