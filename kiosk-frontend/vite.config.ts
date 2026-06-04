import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backendUrl = process.env.BACKEND_URL || 'http://localhost:5000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true, // Needed to expose port from container,
    server: {
      allowedHosts: [
        '.ngrok-free.dev'
      ]
    },
    proxy: {
      '/login': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/logout': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/socket.io': {
        target: backendUrl,
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
