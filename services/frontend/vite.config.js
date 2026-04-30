import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite proxies /api → Django (http) and /ws → Django (WebSocket)
 * so the React dev server and Django run on different ports without CORS issues.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target:  'ws://localhost:8000',
        ws:      true,
        changeOrigin: true,
      },
    },
  },
})
