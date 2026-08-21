<script setup lang="ts">
import { computed } from 'vue';
import type { Permission } from '../api/client';

const props = defineProps<{
  permission?: Permission | null;
  orphaned?: boolean;
}>();

// 權限值來自資料庫實測：ENABLED / INVISIBLE / FULL_CONTROL，未列出則沿用表單預設
const cls = computed(() => {
  switch (props.permission) {
    case 'ENABLED': return 'enabled';
    case 'INVISIBLE': return 'invisible';
    case 'FULL_CONTROL': return 'full';
    default: return 'none';
  }
});
</script>

<template>
  <span
    class="badge"
    :class="[cls, { orphaned }]"
    :title="orphaned ? '此元件在目前表單版本中不存在（流程與表單版本脫節）' : undefined"
  >{{ permission ?? '—' }}</span>
</template>
