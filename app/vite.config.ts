import { defineConfig } from 'vite';

const api = process.env.VEDA_API_PROXY ?? 'http://127.0.0.1:5000';

export default defineConfig({
  build: {
    target: 'es2020',
    sourcemap: false, // no source maps in the published bundle (IR-A21)
    chunkSizeWarningLimit: 200,
    rollupOptions: {
      output: {
        // Name lazy route chunks after their module (modules/leads/index.ts -> leads-[hash].js).
        chunkFileNames: (chunk) => {
          const m = chunk.facadeModuleId?.match(/modules\/([a-z]+)\/index\.ts$/);
          return `assets/${m ? m[1] : chunk.name}-[hash].js`;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: api, changeOrigin: false },
      '/health': { target: api, changeOrigin: false },
    },
  },
});
