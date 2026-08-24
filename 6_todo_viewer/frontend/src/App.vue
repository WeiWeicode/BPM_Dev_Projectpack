<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import InstanceDrawer from './components/InstanceDrawer.vue';
import {
  activeHost, api, formatTime, setActiveHost, stateClass,
} from './api/client';
import type {
  HandledList, HostOption, RequestedList, TodoList, UserCandidate,
} from './api/client';

const PAGE_SIZE = 50;

const hosts = ref<HostOption[]>([]);
const keyword = ref('');
const candidates = ref<UserCandidate[]>([]);
const selected = ref<UserCandidate | null>(null);
const searched = ref(false);
const loading = ref(false);
const error = ref('');

const tab = ref<'todo' | 'requested' | 'handled'>('todo');
const todo = ref<TodoList | null>(null);
const requested = ref<RequestedList | null>(null);
const handled = ref<HandledList | null>(null);
const requestedState = ref<string>('');
const requestedOffset = ref(0);
const handledOffset = ref(0);
const openSerial = ref('');

const currentHost = computed(() =>
  hosts.value.find((h) => h.key === activeHost.value) ?? hosts.value[0]);

async function loadHosts() {
  hosts.value = await api.hosts();
  if (!activeHost.value && hosts.value.length) setActiveHost(hosts.value[0].key);
}

async function search() {
  const q = keyword.value.trim();
  if (!q) return;
  loading.value = true;
  error.value = '';
  selected.value = null;
  candidates.value = [];
  try {
    candidates.value = await api.searchUsers(q);
    searched.value = true;
    // 只有一筆才自動選；多筆一律讓人自己挑 —— 同一個人常有多個公司別帳號
    if (candidates.value.length === 1) await select(candidates.value[0]);
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

async function select(user: UserCandidate) {
  selected.value = user;
  requestedOffset.value = 0;
  handledOffset.value = 0;
  await reload();
}

async function reload() {
  if (!selected.value) return;
  const id = selected.value.id;
  loading.value = true;
  error.value = '';
  try {
    if (tab.value === 'todo') {
      todo.value = await api.todo(id);
    } else if (tab.value === 'requested') {
      const state = requestedState.value === '' ? undefined : Number(requestedState.value);
      requested.value = await api.requested(id, requestedOffset.value, PAGE_SIZE, state);
    } else {
      handled.value = await api.handled(id, handledOffset.value, PAGE_SIZE);
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

function switchTab(next: typeof tab.value) {
  tab.value = next;
  reload();
}

function changeHost(event: Event) {
  setActiveHost((event.target as HTMLSelectElement).value);
  candidates.value = [];
  selected.value = null;
  searched.value = false;
  todo.value = requested.value = handled.value = null;
}

watch(requestedState, () => { requestedOffset.value = 0; reload(); });

onMounted(loadHosts);
</script>

<template>
  <div class="app">
    <header class="app-header">
      <h1 class="app-title">📋 BPM 待辦與流程查詢器</h1>
      <span v-if="currentHost" :class="['host-badge', { production: currentHost.production }]">
        {{ currentHost.label }}{{ currentHost.production ? '（正式區）' : '' }}
      </span>
      <span class="spacer"></span>
      <div class="search-bar">
        <select :value="activeHost" @change="changeHost">
          <option v-for="host in hosts" :key="host.key" :value="host.key">{{ host.label }}</option>
        </select>
        <input v-model="keyword" placeholder="員工編號、姓名或信箱" @keyup.enter="search" />
        <button class="primary" :disabled="loading || !keyword.trim()" @click="search">查詢</button>
      </div>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <!-- 候選清單：同一個人常有多個公司別帳號，一律讓人自己挑 -->
    <section v-if="searched && candidates.length" class="panel">
      <div class="panel-head">
        使用者候選（{{ candidates.length }}）
        <span v-if="candidates.length > 1" class="note">同名或同人多帳號，請選一個</span>
      </div>
      <div class="panel-body candidates">
        <button v-for="user in candidates" :key="user.oid" class="candidate"
                :class="{ active: selected?.oid === user.oid }"
                :title="`${user.id} ${user.user_name}`" @click="select(user)">
          <div><span class="cid">{{ user.id }}</span> {{ user.user_name }}</div>
          <div class="cmeta">
            {{ user.mail_address || '—' }}<span v-if="user.left">・已離職</span>
          </div>
        </button>
      </div>
    </section>
    <p v-else-if="searched && !candidates.length" class="empty">查無使用者</p>

    <template v-if="selected">
      <nav class="tabs">
        <button class="tab" :class="{ active: tab === 'todo' }" @click="switchTab('todo')">
          待簽核 <span v-if="todo" class="count">{{ todo.total }}</span>
        </button>
        <button class="tab" :class="{ active: tab === 'requested' }" @click="switchTab('requested')">
          我申請的 <span v-if="requested" class="count">{{ requested.total }}</span>
        </button>
        <button class="tab" :class="{ active: tab === 'handled' }" @click="switchTab('handled')">
          我經辦過的 <span v-if="handled" class="count">{{ handled.total }}</span>
        </button>
      </nav>

      <section class="panel">
        <p v-if="loading" class="empty">載入中…</p>

        <!-- ---------------------------------------------- 待簽核 -->
        <template v-else-if="tab === 'todo'">
          <p v-if="todo && todo.abnormal_total" class="note warn">
            另有 {{ todo.abnormal_total }} 筆卡住的異常關卡（狀態 97），BPM 不計入待辦數，
            清單中以「異常」標示。
          </p>
          <p v-if="!todo?.items.length" class="empty">查無待簽核項目</p>
          <table v-else>
            <thead>
              <tr>
                <th>單號</th><th>流程 / 關卡</th><th>主旨</th><th>派送時間</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in todo!.items" :key="item.work_item_oid + item.serial_number">
                <td class="serial">
                  <button class="link-serial" @click="openSerial = item.serial_number">
                    {{ item.serial_number || '—' }}
                  </button>
                  <div v-if="item.abnormal" class="badge abnormal">異常 97</div>
                </td>
                <td>
                  {{ item.process_instance_name }}
                  <div class="cmeta">{{ item.work_item_name }}</div>
                </td>
                <td class="subject">{{ item.subject }}</td>
                <td class="time">{{ formatTime(item.created_time) }}</td>
                <td class="links">
                  <a v-if="item.perform_url" class="go-bpm" :href="item.perform_url" target="_blank"
                     rel="noopener">簽核</a>
                  <a v-if="item.trace_url" class="go-bpm subtle" :href="item.trace_url"
                     target="_blank" rel="noopener">追蹤</a>
                  <span v-if="!item.perform_url && !item.trace_url" class="no-link">無可用連結</span>
                </td>
              </tr>
            </tbody>
          </table>
        </template>

        <!-- ---------------------------------------------- 我申請的 -->
        <template v-else-if="tab === 'requested'">
          <div class="panel-head">
            <label>流程狀態</label>
            <select v-model="requestedState">
              <option value="">全部</option>
              <option value="1">進行中（未結案）</option>
              <option value="3">已結案</option>
              <option value="4">已撤銷</option>
              <option value="5">已中止</option>
            </select>
          </div>
          <p v-if="!requested?.items.length" class="empty">查無資料</p>
          <table v-else>
            <thead>
              <tr><th>單號</th><th>流程</th><th>主旨</th><th>目前關卡</th><th>狀態</th><th>建立時間</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in requested!.items" :key="item.serial_number">
                <td class="serial">
                  <button class="link-serial" @click="openSerial = item.serial_number">
                    {{ item.serial_number }}
                  </button>
                </td>
                <td>{{ item.process_instance_name }}</td>
                <td class="subject">{{ item.subject }}</td>
                <td>{{ item.current_activities.join('、') || '—' }}</td>
                <td>
                  <span :class="['badge', stateClass(item.process_state)]">
                    {{ item.process_state_label }}
                  </span>
                </td>
                <td class="time">{{ formatTime(item.created_time) }}</td>
                <td class="links">
                  <a v-if="item.trace_url" class="go-bpm" :href="item.trace_url" target="_blank"
                     rel="noopener">追蹤</a>
                  <span v-else class="no-link">無可用連結</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="requested" class="pager">
            <button :disabled="requestedOffset === 0"
                    @click="requestedOffset -= PAGE_SIZE; reload()">上一頁</button>
            <span>{{ requestedOffset + 1 }}–{{ requestedOffset + requested.items.length }}
              / 共 {{ requested.total }} 筆</span>
            <button :disabled="requestedOffset + PAGE_SIZE >= requested.total"
                    @click="requestedOffset += PAGE_SIZE; reload()">下一頁</button>
          </div>
        </template>

        <!-- ---------------------------------------------- 我經辦過的 -->
        <template v-else>
          <p v-if="!handled?.items.length" class="empty">查無資料</p>
          <table v-else>
            <thead>
              <tr><th>單號</th><th>流程 / 關卡</th><th>主旨</th><th>簽核意見</th><th>完成時間</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in handled!.items" :key="item.work_item_oid">
                <td class="serial">
                  <button class="link-serial" @click="openSerial = item.serial_number">
                    {{ item.serial_number || '—' }}
                  </button>
                </td>
                <td>
                  {{ item.process_instance_name }}
                  <div class="cmeta">{{ item.work_item_name }}</div>
                </td>
                <td class="subject">{{ item.subject }}</td>
                <td class="subject">{{ item.executive_comment }}</td>
                <td class="time">{{ formatTime(item.completed_time) }}</td>
                <td class="links">
                  <a v-if="item.trace_url" class="go-bpm" :href="item.trace_url" target="_blank"
                     rel="noopener">追蹤</a>
                  <span v-else class="no-link">無可用連結</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="handled" class="pager">
            <button :disabled="handledOffset === 0"
                    @click="handledOffset -= PAGE_SIZE; reload()">上一頁</button>
            <span>{{ handledOffset + 1 }}–{{ handledOffset + handled.items.length }}
              / 共 {{ handled.total }} 筆</span>
            <button :disabled="handledOffset + PAGE_SIZE >= handled.total"
                    @click="handledOffset += PAGE_SIZE; reload()">下一頁</button>
          </div>
        </template>
      </section>
    </template>

    <InstanceDrawer v-if="openSerial" :serial-number="openSerial"
                    :user-id="selected?.id ?? ''" @close="openSerial = ''" />
  </div>
</template>
