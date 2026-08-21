import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// 開發時把 /api 轉給後端，正式部署則由後端直接吐靜態檔，同源不需要 proxy
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
