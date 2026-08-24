<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { api, formatTime, stateClass } from '../api/client';
import type { InstanceDetail } from '../api/client';

// userId 只用來讓後端組追蹤網址（hdnCurrentUserId），不參與查詢條件
const props = defineProps<{ serialNumber: string; userId?: string }>();
const emit = defineEmits<{ (event: 'close'): void }>();

const detail = ref<InstanceDetail | null>(null);
const loading = ref(false);
const error = ref('');

async function load() {
  loading.value = true;
  error.value = '';
  detail.value = null;
  try {
    detail.value = await api.instance(props.serialNumber, props.userId ?? '');
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close');
}

onMounted(() => window.addEventListener('keydown', onKeydown));
onUnmounted(() => window.removeEventListener('keydown', onKeydown));

watch(() => props.serialNumber, load, { immediate: true });
</script>

<template>
  <div class="modal-mask" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" @click.stop>
      <div class="modal-head">
        <strong class="serial">{{ serialNumber }}</strong>
        <span v-if="detail" :class="['badge', stateClass(detail.process_state)]">
          {{ detail.process_state_label }}
        </span>
        <span class="spacer"></span>
        <a v-if="detail?.trace_url" class="go-bpm" :href="detail.trace_url" target="_blank"
           rel="noopener">在 BPM 追蹤</a>
        <button @click="emit('close')">關閉</button>
      </div>

      <div class="modal-body">
        <p v-if="loading" class="empty">載入中…</p>
        <p v-else-if="error" class="error">{{ error }}</p>

        <template v-else-if="detail">
          <h3>基本資料</h3>
          <div class="kv">
            <div class="kv-item"><span class="k">流程</span><span class="v">{{ detail.process_instance_name }}</span></div>
            <div class="kv-item"><span class="k">表單單號</span><span class="v">{{ detail.fi_serial_number || '—' }}</span></div>
            <div class="kv-item"><span class="k">申請人</span><span class="v">{{ detail.requester_name }} {{ detail.requester_id }}</span></div>
            <div class="kv-item"><span class="k">建立時間</span><span class="v">{{ formatTime(detail.created_time) }}</span></div>
          </div>
          <div class="kv-item" style="margin-top: 6px;"><span class="k">主旨</span><span class="v">{{ detail.subject }}</span></div>

          <!-- 解析失敗要說出來，不能顯示成「這張單沒有欄位」 -->
          <p v-if="detail.form_parse_error" class="error">{{ detail.form_parse_error }}</p>
          <p v-if="detail.label_source_error" class="note warn">{{ detail.label_source_error }}</p>

          <h3>
            表單欄位（{{ detail.field_values?.length ?? 0 }}）
            <span v-if="detail.form_name" class="form-src">
              {{ detail.form_name }} · {{ detail.form_id }}
            </span>
          </h3>
          <p v-if="!detail.field_values?.length" class="empty">查無表單欄位</p>
          <div v-else class="kv">
            <div v-for="field in detail.field_values" :key="field.id" class="kv-item">
              <!-- 定義裡查不到中文名時顯示 ID，不編造名稱 -->
              <span class="k">
                {{ field.name || field.id }}
                <em v-if="field.name" class="fid">{{ field.id }}</em>
              </span>
              <span class="v">{{ field.value || '—' }}</span>
            </div>
          </div>

          <template v-for="grid in detail.grid_values ?? []" :key="grid.id">
            <h3>
              {{ grid.name || grid.id }}
              <em v-if="grid.name" class="fid">{{ grid.id }}</em>
              （{{ grid.rows.length }} 列）
            </h3>
            <div class="table-wrap">
              <table v-if="grid.rows.length">
                <thead>
                  <tr><th v-for="col in grid.columns" :key="col">{{ col }}</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(row, index) in grid.rows" :key="index">
                    <td v-for="col in grid.columns" :key="col">{{ row[col] }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <h3>附件（{{ detail.attachments?.length ?? 0 }}）</h3>
          <p v-if="!detail.attachments?.length" class="empty">無附件</p>
          <div v-else class="table-wrap">
            <table>
              <thead><tr><th>原始檔名</th><th>型別</th><th>大小</th><th>上傳者</th><th>關卡</th></tr></thead>
              <tbody>
                <tr v-for="att in detail.attachments" :key="att.oid">
                  <td>{{ att.original_file_name || att.file_name }}</td>
                  <td>{{ att.file_type }}</td>
                  <td>{{ att.file_size }}</td>
                  <td>{{ att.creator_name }}</td>
                  <td>{{ att.activity_name }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h3>簽核歷程（{{ detail.approval_history?.length ?? 0 }}）</h3>
          <ul class="timeline">
            <li v-for="(step, index) in detail.approval_history" :key="index"
                :class="step.completed_time ? 'done' : 'pending'">
              <div class="step-name">{{ step.work_item_name }}</div>
              <div class="step-meta">
                <template v-if="step.performer_name">
                  {{ step.performer_name }} {{ step.performer_id }}
                </template>
                <!-- performerOID 只在關卡完成時才寫入；沒有執行者又已完成的是系統關卡 -->
                <template v-else>{{ step.completed_time ? '系統執行' : '尚未執行' }}</template>
                ・{{ step.completed_time
                      ? `完成於 ${formatTime(step.completed_time)}`
                      : `派送於 ${formatTime(step.created_time)}` }}
              </div>
              <div v-if="step.executive_comment" class="step-comment">{{ step.executive_comment }}</div>
            </li>
          </ul>
        </template>
      </div>
    </div>
  </div>
</template>
