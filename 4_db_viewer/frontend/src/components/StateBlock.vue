<script setup lang="ts">
defineProps<{ loading?: boolean; error?: string; empty?: boolean; emptyText?: string }>();
</script>

<template>
  <div v-if="loading" class="state">
    <div class="skeleton" style="width: 40%" />
    <div class="skeleton" style="width: 70%" />
    <div class="skeleton" style="width: 55%" />
  </div>
  <div v-else-if="error" class="state error">
    載入失敗
    <pre>{{ error }}</pre>
  </div>
  <div v-else-if="empty" class="state">{{ emptyText ?? '沒有資料' }}</div>
  <slot v-else />
</template>
