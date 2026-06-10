// frontend/vite.config.js
// Local development proxy mirrors the nginx production config exactly.
// When you run `npm run dev`, Vite intercepts these paths and
// forwards them to the local API server.
// In Docker / production, nginx handles the same routing.

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // /api/* → FastAPI on port 8000
      // Matches nginx: location /api/ { proxy_pass http://api:8000/api/; }
      '/api': {
        target:      'http://localhost:8000',
        changeOrigin: true,
      },
      // /health → FastAPI health endpoint
      '/health': {
        target:      'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})