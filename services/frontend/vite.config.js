import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite proxies /api → Django (http) and /ws → Django (WebSocket)
 * so the React dev server and Django run on different ports without CORS issues.
 *
 * WHY core-api (not localhost):
 *   Inside Docker, services talk via Docker DNS (service names).
 *   'localhost' inside the frontend container points to itself, not Django.
 *   'core-api' resolves to the Django container on the same Docker network.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://core-api:8000',
        changeOrigin: true,
      },
      '/ws': {
        target:  'ws://core-api:8000',
        ws:      true,
        changeOrigin: true,
      },
    },
  },
})
