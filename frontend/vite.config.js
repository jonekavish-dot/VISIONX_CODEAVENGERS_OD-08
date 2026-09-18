import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/evidence': 'http://localhost:8000',
      '/scenarios': 'http://localhost:8000',
      '/demo-media': 'http://localhost:8000'
    }
  }
})
