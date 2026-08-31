<script setup lang="ts">
/**
 * 流程工作台，兩種模式共用同一份欄位編輯表：
 *
 *   改既有單  查流程 → 選單 → 改欄位 → 送出 → 讀回驗證（updateFormValueBySerialNember）
 *   建立新單  查流程 → 取空白範本 → 填欄位 → 開單 → 讀回驗證（invokeProcess）
 *
 * 兩邊都刻意不讓人手貼表單 XML。updateFormValueBySerialNember 是整份覆寫、
 * invokeProcess 不驗證欄位 id，手拼錯了都會靜默寫入、延後爆炸（實測踩過）。
 * XML 一律由後端依 getFormFieldTemplate 或現值組出來。
 */
import { computed, inject, onMounted, ref } from 'vue';
import { api, ApiError } from '../api/client';
import WorkItemPanel from './WorkItemPanel.vue';
import type {
  CreateInstanceResult,
  FormEditSubmitResult,
  InstanceDetail,
  InstanceSummary,
  NewFormTemplate,
  OrgUnitOption,
  ProcessOption,
} from '../api/types';

const showToast = inject<(m: string) => void>('showToast', () => {});

// 兩種模式共用左邊的流程搜尋，右邊換成不同的編輯面板
const mode = ref<'edit' | 'create' | 'activity'>('edit');

// ── 步驟一：找流程 ──
const processKeyword = ref('');
const processes = ref<ProcessOption[]>([]);
const processSource = ref('');
const processTotal = ref(0);
const selectedProcessId = ref('');

// ── 步驟二：找單 ──
const scope = ref<'all' | 'running' | 'closed'>('all');
const dateBasis = ref<'created' | 'closed'>('created');
const startTime = ref('');
const endTime = ref('');
const instances = ref<InstanceSummary[]>([]);
const instanceMethod = ref('');
const serialInput = ref('');

// ── 步驟三：改欄位 ──
const detail = ref<InstanceDetail | null>(null);
const edited = ref<Record<string, string>>({});
const confirmWrite = ref(false);
const submitting = ref(false);
const loading = ref(false);
const result = ref<FormEditSubmitResult | null>(null);
const backup = ref<{ serialNo: string; xml: string } | null>(null);
const showRawXml = ref(false);

const changedTags = computed(() => {
  if (!detail.value) return [];
  return detail.value.fields
    .filter((f) => (edited.value[f.tag] ?? f.value) !== f.value)
    .map((f) => f.tag);
});

const changes = computed(() => {
  const out: Record<string, string> = {};
  for (const tag of changedTags.value) out[tag] = edited.value[tag] ?? '';
  return out;
});

const attrWarnings = computed(() =>
  (detail.value?.fields || []).filter((f) => f.attrBacked && changedTags.value.includes(f.tag)),
);

function fail(err: any) {
  showToast(err instanceof ApiError ? err.message : String(err?.message || err));
}

async function searchProcesses() {
  try {
    const res = await api.listEditProcesses(processKeyword.value);
    processes.value = res.processes;
    processTotal.value = res.total;
    processSource.value = res.source || '';
    if (!res.processes.length) showToast('沒有符合的流程');
  } catch (err) {
    fail(err);
  }
}

async function searchInstances(processId?: string) {
  const pid = processId || selectedProcessId.value;
  if (!pid) return showToast('請先選一支流程');
  selectedProcessId.value = pid;
  try {
    const res = await api.listEditInstances({
      processId: pid,
      scope: scope.value,
      startTime: startTime.value,
      endTime: endTime.value,
      dateBasis: dateBasis.value,
    });
    instances.value = res.instances;
    instanceMethod.value = `${res.method}，${res.total} 筆，${res.elapsedMs} ms`;
    if (!res.total) showToast('這支流程在此條件下沒有單');
  } catch (err) {
    fail(err);
  }
}

async function openInstance(serialNo: string) {
  if (!serialNo) return showToast('請輸入單號');
  loading.value = true;
  result.value = null;
  try {
    const data = await api.loadEditInstance(serialNo);
    detail.value = data;
    serialInput.value = data.header.serialNo || serialNo;
    edited.value = {};
    for (const f of data.fields) edited.value[f.tag] = f.value;
    confirmWrite.value = false;
    if (data.corruption) showToast('這張單的表單值有異常，請看上方紅框說明');
  } catch (err) {
    detail.value = null;
    fail(err);
  } finally {
    loading.value = false;
  }
}

function resetField(tag: string) {
  const field = detail.value?.fields.find((f) => f.tag === tag);
  if (field) edited.value[tag] = field.value;
}

function resetAll() {
  if (!detail.value) return;
  for (const f of detail.value.fields) edited.value[f.tag] = f.value;
  showToast('已還原成讀取當下的值（尚未送出任何變更）');
}

async function submit() {
  if (!detail.value) return;
  if (!confirmWrite.value) return showToast('請先勾選確認');
  if (!changedTags.value.length && !detail.value.corruption) {
    return showToast('沒有任何欄位被改動');
  }
  submitting.value = true;
  try {
    const res = await api.submitEdit({
      serialNo: detail.value.header.serialNo || serialInput.value,
      changes: changes.value,
      confirm: true,
    });
    result.value = res;
    if (res.backupFormXml && res.serialNo) {
      backup.value = { serialNo: res.serialNo, xml: res.backupFormXml };
    }
    showToast(res.message || '已送出');
    await openInstance(res.serialNo || serialInput.value);
  } catch (err) {
    fail(err);
  } finally {
    submitting.value = false;
  }
}

async function restoreBackup() {
  if (!backup.value) return;
  submitting.value = true;
  try {
    const res = await api.submitEdit({
      serialNo: backup.value.serialNo,
      rawFormXml: backup.value.xml,
      confirm: true,
    });
    result.value = res;
    showToast(res.verified ? '已還原成送出前的內容' : '還原後讀回比對有落差，請檢查');
    await openInstance(backup.value.serialNo);
  } catch (err) {
    fail(err);
  } finally {
    submitting.value = false;
  }
}

// ── 建立新單 ──
const template = ref<NewFormTemplate | null>(null);
const newValues = ref<Record<string, string>>({});
const requesterId = ref('S112009');
const orgUnits = ref<OrgUnitOption[]>([]);
const orgUnitId = ref('');
const orgId = ref('');
const newSubject = ref('');
const confirmCreate = ref(false);
const creating = ref(false);
const createResult = ref<CreateInstanceResult | null>(null);

async function loadTemplate(processId?: string) {
  const pid = processId || selectedProcessId.value;
  if (!pid) return showToast('請先選一支流程');
  selectedProcessId.value = pid;
  loading.value = true;
  createResult.value = null;
  try {
    const data = await api.loadNewForm(pid);
    template.value = data;
    newValues.value = {};
    for (const f of data.fields) newValues.value[f.tag] = f.value;
    confirmCreate.value = false;
    if (!orgUnits.value.length) await lookupOrgUnits();
  } catch (err) {
    template.value = null;
    fail(err);
  } finally {
    loading.value = false;
  }
}

async function lookupOrgUnits() {
  if (!requesterId.value.trim()) return showToast('請輸入申請人員工編號');
  try {
    const res = await api.listOrgUnits(requesterId.value.trim());
    orgUnits.value = res.orgUnits;
    const main = res.orgUnits.find((u) => u.isMain) || res.orgUnits[0];
    orgUnitId.value = main?.id || '';
  } catch (err) {
    orgUnits.value = [];
    orgUnitId.value = '';
    fail(err);
  }
}

async function create() {
  if (!template.value) return;
  if (!confirmCreate.value) return showToast('請先勾選確認');
  creating.value = true;
  try {
    const res = await api.createInstance({
      processId: template.value.processId || selectedProcessId.value,
      requesterId: requesterId.value.trim(),
      orgUnitId: orgUnitId.value.trim(),
      subject: newSubject.value,
      values: newValues.value,
      orgId: orgId.value.trim() || undefined,
      confirm: true,
    });
    createResult.value = res;
    showToast(res.message || '已開單');
  } catch (err) {
    fail(err);
  } finally {
    creating.value = false;
  }
}

function openCreated() {
  if (!createResult.value?.serialNo) return;
  mode.value = 'edit';
  openInstance(createResult.value.serialNo);
}

function switchMode(next: 'edit' | 'create' | 'activity') {
  mode.value = next;
  if (next === 'create' && selectedProcessId.value && !template.value) {
    loadTemplate();
  }
}

// 關卡操作面板改動了流程狀態，改單模式手上的表單快照就過期了
async function onActivityChanged() {
  if (detail.value?.header.serialNo) await openInstance(detail.value.header.serialNo);
}

function pickProcess(processId: string) {
  if (mode.value === 'create') {
    template.value = null;
    loadTemplate(processId);
  } else {
    // 改單與關卡操作都要先挑到一張單
    searchInstances(processId);
  }
}

function stateLabel(state?: string | null) {
  if (!state) return '—';
  if (state.startsWith('open.')) return '進行中';
  if (state === 'closed.completed') return '已結案';
  if (state === 'closed.terminated') return '已終止';
  if (state === 'closed.aborted') return '已作廢';
  return state;
}

onMounted(searchProcesses);
</script>

<template>
  <div class="edit-layout">
    <!-- 左欄：找流程 -->
    <section class="finder-panel">
      <div class="step-block mode-block">
        <div class="mode-switch">
          <button
            class="mode-btn"
            :class="{ active: mode === 'edit' }"
            @click="switchMode('edit')"
          >
            ✏️ 改既有單
          </button>
          <button
            class="mode-btn"
            :class="{ active: mode === 'create' }"
            @click="switchMode('create')"
          >
            ➕ 建立新單
          </button>
          <button
            class="mode-btn"
            :class="{ active: mode === 'activity' }"
            @click="switchMode('activity')"
          >
            🔀 關卡操作
          </button>
        </div>
        <div class="hint">
          {{ mode === 'edit'
            ? '改已開單的表單欄位值（updateFormValueBySerialNember），不推動流程、不簽核。'
            : mode === 'create'
            ? '用流程的空白表單範本開一張新單（invokeProcess），會產生真實單據與待辦。'
            : '看關卡歷程，以該關卡的待辦人身分簽收、改表單簽核、轉派、取回重辦或收單。' }}
        </div>
      </div>

      <div class="step-block">
        <div class="step-title"><span class="step-no">1</span> 找流程</div>
        <div class="row">
          <input
            v-model="processKeyword"
            type="search"
            placeholder="流程 id、流程名稱或表單名稱…"
            @keyup.enter="searchProcesses"
          />
          <button @click="searchProcesses">搜尋</button>
        </div>
        <div v-if="processSource" class="hint">{{ processSource }}，符合 {{ processTotal }} 支</div>
        <div v-if="processes.length" class="scroll-list">
          <button
            v-for="p in processes"
            :key="p.processId || ''"
            class="list-row"
            :class="{ picked: p.processId === selectedProcessId }"
            @click="pickProcess(p.processId || '')"
          >
            <span class="row-main">{{ p.processName || '（無名稱）' }}</span>
            <span class="row-sub mono">{{ p.processId }}</span>
            <span v-if="p.formNames.length" class="row-tag">表單：{{ p.formNames.join('、') }}</span>
          </button>
        </div>
      </div>

      <div v-if="mode !== 'create'" class="step-block">
        <div class="step-title"><span class="step-no">2</span> 找單號</div>
        <div class="row wrap">
          <select v-model="scope" @change="selectedProcessId && searchInstances()">
            <option value="all">全部</option>
            <option value="running">只看進行中</option>
            <option value="closed">只看已結案</option>
          </select>
          <select v-model="dateBasis" @change="selectedProcessId && searchInstances()">
            <option value="created">依建立時間</option>
            <option value="closed">依結案時間</option>
          </select>
        </div>
        <div class="row wrap">
          <input v-model="startTime" type="text" placeholder="起 yyyy/MM/dd HH:mm:ss" />
          <input v-model="endTime" type="text" placeholder="迄 yyyy/MM/dd HH:mm:ss" />
          <button :disabled="!selectedProcessId" @click="searchInstances()">重查</button>
        </div>
        <div v-if="instanceMethod" class="hint">{{ instanceMethod }}</div>
        <div v-if="instances.length" class="scroll-list">
          <button
            v-for="inst in instances"
            :key="inst.serialNo || ''"
            class="list-row"
            :class="{ picked: inst.serialNo === detail?.header.serialNo }"
            @click="openInstance(inst.serialNo || '')"
          >
            <span class="row-main">
              <span class="badge" :class="inst.state?.startsWith('open.') ? 'write' : 'read'">
                {{ stateLabel(inst.state) }}
              </span>
              {{ inst.subject || '（無主旨）' }}
            </span>
            <span class="row-sub mono">{{ inst.serialNo }}</span>
            <span class="row-tag">{{ inst.requesterName }}（{{ inst.requesterId }}）· {{ inst.createdTime }}</span>
          </button>
        </div>
      </div>

      <div v-if="mode !== 'create'" class="step-block">
        <div class="step-title"><span class="step-no">3</span> 或直接輸入單號</div>
        <div class="row">
          <input
            v-model="serialInput"
            class="mono"
            type="text"
            placeholder="例如 SpecialtyAdhesivesConcessionProcess00000003"
            @keyup.enter="openInstance(serialInput)"
          />
          <button class="primary" @click="openInstance(serialInput)">讀取</button>
        </div>
      </div>

      <div v-if="mode === 'create'" class="step-block">
        <div class="step-title"><span class="step-no">2</span> 開單資訊</div>
        <label class="mini-label">申請人員工編號（pRequesterId）</label>
        <div class="row">
          <input v-model="requesterId" class="mono" type="text" @keyup.enter="lookupOrgUnits" />
          <button @click="lookupOrgUnits">查部門</button>
        </div>
        <label class="mini-label">申請部門（pOrgUnitId）</label>
        <select v-model="orgUnitId">
          <option v-if="!orgUnits.length" value="">（先查部門）</option>
          <option v-for="u in orgUnits" :key="u.id || ''" :value="u.id || ''">
            {{ u.id }} {{ u.name }}{{ u.isMain ? '（主要）' : '' }} · {{ u.orgName }}
          </option>
        </select>
        <label class="mini-label">公司別（pOrgId，留空則用 invokeProcess）</label>
        <input v-model="orgId" class="mono" type="text" placeholder="例如 GIGASOLAR" />
        <label class="mini-label">主旨（pSubject）</label>
        <input v-model="newSubject" type="text" placeholder="流程若設了主旨範本，這裡送的值會被蓋掉" />
      </div>
    </section>

    <!-- 右欄：欄位編輯 -->
    <section class="editor-panel">
      <!-- 關卡操作：排在 loading 之前，否則改單模式的讀取旗標會把這個面板
           卸載重建，面板自己的操作紀錄與勾選狀態就跟著消失（實測踩到）。 -->
      <WorkItemPanel
        v-if="mode === 'activity'"
        :serial-no="detail?.header.serialNo || serialInput"
        @changed="onActivityChanged"
      />

      <div v-else-if="loading" class="placeholder">讀取中…</div>

      <!-- 建立新單 -->
      <template v-else-if="mode === 'create'">
        <div v-if="!template" class="placeholder">
          <p>從左邊挑一支流程，取出它的空白表單範本。</p>
          <p class="hint">
            欄位結構一律取自 <code>getFormFieldTemplate</code> ——
            <code>invokeProcess</code> 不驗證欄位 id，自己拼的欄位會被靜默寫入，
            要到之後讀取表單時才爆。
          </p>
        </div>

        <template v-else>
          <div class="doc-header">
            <div class="doc-title">
              <span class="badge write">建立新單</span>
              {{ selectedProcessId }}
            </div>
            <div class="doc-meta mono">
              表單 {{ template.formId }} · OID {{ template.formOid }} ·
              {{ template.fields.length }} 欄 · 範本讀取 {{ template.elapsedMs }} ms
            </div>
          </div>

          <div v-if="!template.labelsAvailable" class="callout warn">
            <div class="callout-title">欄位中文名稱不可用</div>
            <p>{{ template.labelSource }}</p>
          </div>

          <div class="table-scroll">
            <table class="data-table field-table">
              <thead>
                <tr>
                  <th style="width: 24%">欄位名稱</th>
                  <th style="width: 26%">欄位 id</th>
                  <th style="width: 12%">型別</th>
                  <th>欄位數據</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in template.fields" :key="f.tag">
                  <td>
                    <span class="field-name">{{ f.name || '—' }}</span>
                    <span v-if="f.attrBacked" class="attr-flag" title="此欄位另有 label / hidden 屬性存顯示名稱與 OID">
                      ⚠ 屬性欄位
                    </span>
                  </td>
                  <td class="mono field-id">{{ f.id }}</td>
                  <td>
                    <span class="type-chip">{{ f.fieldType || '—' }}</span>
                    <div class="dtype mono">{{ f.dataType || '' }}</div>
                  </td>
                  <td>
                    <textarea
                      v-if="f.fieldType === 'TEXTAREA' || (newValues[f.tag] || '').length > 60"
                      v-model="newValues[f.tag]"
                      rows="3"
                      class="mono"
                    ></textarea>
                    <input v-else v-model="newValues[f.tag]" type="text" class="mono" />
                    <div v-if="Object.keys(f.extraAttributes).length" class="attrs mono">
                      <span v-for="(v, k) in f.extraAttributes" :key="k">{{ k }}="{{ v }}"</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="submit-bar">
            <div class="callout warn">
              <div class="callout-title">開單前先知道這三件事</div>
              <p>
                1. 會在 191 測試區產生<b>真實單據與待辦</b>，下一關的人會收到。<br />
                2. <b>開單失敗一樣會消耗單號</b>，失敗不代表沒留下痕跡。<br />
                3. 主旨若流程設了範本，<code>pSubject</code> 送的值會被蓋掉，
                送出後會列出實際主旨供比對。
              </p>
            </div>

            <div class="safety-box">
              <label class="safety-check">
                <input v-model="confirmCreate" type="checkbox" />
                <span>
                  我確認要以 {{ requesterId }}／{{ orgUnitId || '（未選部門）' }}
                  在 191 測試區開一張 {{ selectedProcessId }} 的新單
                </span>
              </label>
              <div class="btn-row">
                <button
                  class="primary"
                  :disabled="creating || !confirmCreate || !orgUnitId"
                  @click="create"
                >
                  {{ creating ? '開單中…' : '開單並讀回驗證' }}
                </button>
              </div>
            </div>
          </div>

          <div v-if="createResult" class="result-box">
            <div class="result-title">
              <span class="badge" :class="createResult.verified ? 'st-ok' : 'st-fault'">
                {{ createResult.verified ? '讀回驗證通過' : '讀回比對有落差' }}
              </span>
              {{ createResult.message }}
              <span class="hint">{{ createResult.method }} · {{ createResult.elapsedMs }} ms</span>
            </div>
            <div class="hint">
              新單號 <code>{{ createResult.serialNo }}</code> ·
              {{ createResult.fieldCount }} 欄
              <button class="btn-xs" @click="openCreated">切到改單模式開啟它</button>
            </div>
            <div v-if="createResult.subjectOverridden" class="callout info">
              <div class="callout-title">主旨被流程的主旨範本覆寫</div>
              <p>
                送出 <code>{{ createResult.requestedSubject }}</code>，
                實際 <code>{{ createResult.actualSubject }}</code>。
              </p>
            </div>
            <div v-if="createResult.systemFilled.length" class="callout info">
              <div class="callout-title">這幾欄由流程自己填入（不是寫入失敗）</div>
              <ul>
                <li v-for="s in createResult.systemFilled" :key="s.tag">
                  <code>{{ s.tag }}</code>：送出空值，BPM 回填 <b>{{ s.actual }}</b>
                </li>
              </ul>
            </div>
            <div v-if="createResult.mismatches.length" class="callout danger">
              <div class="callout-title">這幾欄開單後讀回來不一樣</div>
              <ul>
                <li v-for="m in createResult.mismatches" :key="m.tag">
                  <code>{{ m.tag }}</code>：預期 <b>{{ m.expected }}</b>，實際 <b>{{ m.actual }}</b>
                </li>
              </ul>
            </div>
          </div>
        </template>
      </template>

      <div v-else-if="!detail" class="placeholder">
        <p>從左邊挑一張單，或直接輸入單號讀取。</p>
        <p class="hint">
          改單模式只做一件事：把已開單的表單欄位值改掉
          （<code>updateFormValueBySerialNember</code>）。
          它不會推動流程、不會簽核、不會改簽核歷程。
        </p>
      </div>

      <template v-else>
        <div class="doc-header">
          <div class="doc-title">
            <span class="badge" :class="detail.closed ? 'read' : 'write'">
              {{ stateLabel(detail.header.state) }}
            </span>
            {{ detail.header.subject || '（無主旨）' }}
          </div>
          <div class="doc-meta mono">
            {{ detail.header.serialNo }} · {{ detail.header.processName }} ·
            申請人 {{ detail.header.requesterName }}（{{ detail.header.requesterId }}）·
            {{ detail.header.createdTime }} · 表單 {{ detail.formId }}
          </div>
        </div>

        <div v-if="detail.corruption" class="callout danger">
          <div class="callout-title">⚠️ 這張單的表單值結構異常</div>
          <p>{{ detail.corruption }}</p>
          <p>下方欄位已是挖出來的真實內容，直接勾選確認並送出即可寫回正確結構。</p>
        </div>

        <div v-if="detail.closed" class="callout warn">
          <div class="callout-title">這是已結案的單</div>
          <p>
            API 仍然改得動已結案單的表單值，但簽核歷程不會有任何記錄 ——
            事後看不出誰改的、什麼時候改的。確認這是你要的再送出。
          </p>
        </div>

        <div v-if="!detail.labelsAvailable" class="callout warn">
          <div class="callout-title">欄位中文名稱不可用</div>
          <p>{{ detail.labelSource }}</p>
        </div>

        <div class="table-scroll">
          <table class="data-table field-table">
            <thead>
              <tr>
                <th style="width: 24%">欄位名稱</th>
                <th style="width: 26%">欄位 id</th>
                <th style="width: 12%">型別</th>
                <th>欄位數據</th>
                <th style="width: 60px"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="f in detail.fields"
                :key="f.tag"
                :class="{ changed: changedTags.includes(f.tag) }"
              >
                <td>
                  <span class="field-name">{{ f.name || '—' }}</span>
                  <span v-if="f.attrBacked" class="attr-flag" title="此欄位另有 label / hidden 屬性存顯示名稱與 OID，只改值畫面不會同步">
                    ⚠ 屬性欄位
                  </span>
                </td>
                <td class="mono field-id">{{ f.id }}</td>
                <td>
                  <span class="type-chip">{{ f.fieldType || '—' }}</span>
                  <div class="dtype mono">{{ f.dataType || '' }}</div>
                </td>
                <td>
                  <textarea
                    v-if="f.fieldType === 'TEXTAREA' || (edited[f.tag] || '').length > 60"
                    v-model="edited[f.tag]"
                    rows="3"
                    class="mono"
                  ></textarea>
                  <input v-else v-model="edited[f.tag]" type="text" class="mono" />
                  <div v-if="changedTags.includes(f.tag)" class="before-line">
                    原值：<code>{{ f.value || '（空）' }}</code>
                  </div>
                  <div v-if="Object.keys(f.extraAttributes).length" class="attrs mono">
                    <span v-for="(v, k) in f.extraAttributes" :key="k">{{ k }}="{{ v }}"</span>
                  </div>
                </td>
                <td>
                  <button
                    v-if="changedTags.includes(f.tag)"
                    class="btn-xs"
                    @click="resetField(f.tag)"
                  >
                    復原
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="attrWarnings.length" class="callout warn">
          <div class="callout-title">這幾欄只改了值，屬性沒有跟著改</div>
          <p>
            {{ attrWarnings.map((f) => `${f.name || f.id}（${f.id}）`).join('、') }}
            的顯示名稱存在 <code>label</code>、OID 存在 <code>hidden</code> 屬性裡。
            只改內文的話，畫面上仍會顯示舊的姓名。本頁不改屬性，需要換人請走通用實測工作台。
          </p>
        </div>

        <div class="submit-bar">
          <div class="submit-info">
            <span v-if="changedTags.length" class="changed-count">
              已改 {{ changedTags.length }} 欄：{{ changedTags.join('、') }}
            </span>
            <span v-else class="hint">尚未改動任何欄位</span>
            <button class="btn-xs" @click="resetAll">全部復原</button>
            <button class="btn-xs" @click="showRawXml = !showRawXml">
              {{ showRawXml ? '收合' : '看目前的表單 XML' }}
            </button>
          </div>

          <div class="safety-box">
            <label class="safety-check">
              <input v-model="confirmWrite" type="checkbox" />
              <span>
                我了解 <code>updateFormValueBySerialNember</code> 是<b>整份覆寫</b>且無法復原，
                同意寫入 191 測試區的 {{ detail.header.serialNo }}
              </span>
            </label>
            <div class="btn-row">
              <button
                class="primary"
                :disabled="submitting || !confirmWrite"
                @click="submit"
              >
                {{ submitting ? '寫入中…' : '送出並讀回驗證' }}
              </button>
              <button
                v-if="backup && backup.serialNo === detail.header.serialNo"
                class="danger"
                :disabled="submitting"
                @click="restoreBackup"
              >
                還原成上次送出前
              </button>
            </div>
          </div>
        </div>

        <div v-if="showRawXml" class="code-box">
          <pre>{{ detail.rawFormXml }}</pre>
        </div>

        <div v-if="result" class="result-box" :class="result.status">
          <div class="result-title">
            <span class="badge" :class="result.verified ? 'st-ok' : 'st-fault'">
              {{ result.verified ? '讀回驗證通過' : '讀回比對有落差' }}
            </span>
            {{ result.message }}
            <span class="hint">{{ result.elapsedMs }} ms</span>
          </div>
          <div v-if="result.fieldCountBefore != null" class="hint">
            欄位數 {{ result.fieldCountBefore }} → {{ result.fieldCountAfter }}
            <span v-if="result.corruptionCleared">· 結構異常已修復</span>
          </div>
          <table v-if="result.diff.length" class="data-table">
            <thead>
              <tr><th>欄位</th><th>改前</th><th>改後</th></tr>
            </thead>
            <tbody>
              <tr v-for="d in result.diff" :key="d.tag">
                <td class="mono">{{ d.tag }}</td>
                <td>{{ d.before || '（空）' }}</td>
                <td>{{ d.after || '（空）' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="result.systemFilled.length" class="callout info">
            <div class="callout-title">這幾欄由流程自己填入（不是寫入失敗）</div>
            <ul>
              <li v-for="s in result.systemFilled" :key="s.tag">
                <code>{{ s.tag }}</code>：送出空值，BPM 回填 <b>{{ s.actual }}</b>
              </li>
            </ul>
          </div>
          <div v-if="result.mismatches.length" class="callout danger">
            <div class="callout-title">這幾欄寫進去後讀回來不一樣</div>
            <ul>
              <li v-for="m in result.mismatches" :key="m.tag">
                <code>{{ m.tag }}</code>：預期 <b>{{ m.expected }}</b>，實際 <b>{{ m.actual }}</b>
              </li>
            </ul>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.edit-layout {
  display: flex;
  flex: 1;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  gap: 16px;
  padding: 16px 20px;
}

.finder-panel {
  width: 380px;
  flex-shrink: 0;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 4px;
}

.step-block {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 12px;
  flex-shrink: 0;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 10px;
}

.step-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
}

.row {
  display: flex;
  gap: 6px;
}

.row.wrap {
  flex-wrap: wrap;
  margin-top: 6px;
}

.row input,
.row select {
  flex: 1;
  min-width: 0;
}

.hint {
  color: var(--text-dim);
  font-size: 12px;
  margin-top: 6px;
}

.scroll-list {
  margin-top: 8px;
  max-height: 240px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.list-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  text-align: left;
  width: 100%;
  padding: 7px 9px;
  background: var(--panel-alt);
  border: 1px solid var(--border);
}

.list-row.picked {
  border-color: var(--accent);
  background: var(--accent-faint);
}

.row-main {
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}

.row-sub {
  font-size: 11px;
  color: var(--text-dim);
}

.row-tag {
  font-size: 11px;
  color: var(--text-faint);
}

.editor-panel {
  flex: 1;
  min-width: 0;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 20px 24px 80px;
}

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

.field-table td {
  vertical-align: top;
}

.field-table tr.changed td {
  background: var(--accent-faint);
}

.field-name {
  font-weight: 500;
}

.attr-flag {
  display: block;
  font-size: 11px;
  color: var(--warn);
}

.field-id {
  font-size: 11px;
  word-break: break-all;
}

.type-chip {
  font-size: 11px;
  background: var(--panel-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1px 5px;
}

.dtype {
  font-size: 10px;
  color: var(--text-faint);
  margin-top: 3px;
}

.field-table input,
.field-table textarea {
  width: 100%;
  font-size: 12px;
}

.before-line {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 4px;
}

.attrs {
  font-size: 10px;
  color: var(--text-faint);
  margin-top: 3px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.btn-xs {
  font-size: 11px;
  padding: 3px 7px;
}

.submit-bar {
  margin-top: 14px;
  border-top: 1px solid var(--border);
  padding-top: 12px;
}

.submit-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.changed-count {
  font-size: 12px;
  color: var(--accent);
  font-weight: 500;
}

.safety-box {
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

.btn-row {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.result-box {
  margin-top: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: var(--panel-alt);
}

.result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
}

.mode-block {
  padding: 10px 12px;
}

.mode-switch {
  display: flex;
  gap: 6px;
}

.mode-btn {
  flex: 1;
  font-size: 13px;
}

.mode-btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.mini-label {
  display: block;
  font-size: 11px;
  color: var(--text-dim);
  margin: 8px 0 3px;
}

.step-block > select,
.step-block > input {
  width: 100%;
}

@media (max-width: 1100px) {
  .edit-layout {
    flex-direction: column;
    overflow-y: auto;
    height: 100%;
  }

  .finder-panel {
    width: 100%;
    height: auto;
    overflow-y: visible;
    flex-shrink: 0;
    padding-right: 0;
  }

  .editor-panel {
    width: 100%;
    height: auto;
    overflow-y: visible;
    flex-shrink: 0;
  }
}
</style>
