// 非同步載入的共用狀態：loading / error / data。失敗一律顯示，不靜默吞掉。
import { ref, shallowRef } from 'vue';

export function useAsync<T>() {
  const data = shallowRef<T | null>(null);
  const loading = ref(false);
  const error = ref('');

  async function run(producer: () => Promise<T>) {
    loading.value = true;
    error.value = '';
    try {
      data.value = await producer();
    } catch (err) {
      data.value = null;
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      loading.value = false;
    }
  }

  return { data, loading, error, run };
}
