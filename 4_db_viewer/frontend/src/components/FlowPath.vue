<script setup lang="ts">
import type { Activity } from '../api/client';
defineProps<{ activities: Activity[] }>();
</script>

<template>
  <div class="flow-path">
    <template v-for="(activity, index) in activities" :key="activity.id">
      <b>{{ activity.name || activity.id }}</b><span v-if="index < activities.length - 1"> → </span>
    </template>
  </div>
</template>
