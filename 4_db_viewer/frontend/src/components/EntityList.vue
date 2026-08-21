<script setup lang="ts">
// 左側清單，表單與流程共用
defineProps<{
  title: string;
  items: { id: string; name: string }[];
  activeId?: string;
}>();
defineEmits<{ select: [id: string] }>();
</script>

<template>
  <aside class="sidebar">
    <div class="group-title">{{ title }}（{{ items.length }}）</div>
    <button
      v-for="item in items"
      :key="item.id"
      :class="{ active: item.id === activeId }"
      @click="$emit('select', item.id)"
    >
      {{ item.name || item.id }}
      <span class="sub">{{ item.id }}</span>
    </button>
    <div v-if="!items.length" class="state">沒有符合的項目</div>
  </aside>
</template>
