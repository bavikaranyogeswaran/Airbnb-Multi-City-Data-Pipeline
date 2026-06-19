import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // loadEnv reads .env / .env.local / .env.<mode> from the project root
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.API_TARGET ?? 'http://localhost:8000';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        // All /api/* calls are forwarded to FastAPI, stripping the /api prefix
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
});
