import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('error', (err, req) => {
            console.log(`[Vite Proxy ERROR] ${req.method || '?'} ${req.url} → ${err.message}`)
          })
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log(`[Vite Proxy] ${req.method} ${req.url} → http://127.0.0.1:5000${req.url}`)
          })
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log(`[Vite Proxy] ${req.method} ${req.url} ← ${proxyRes.statusCode}`)
          })
        }
      }
    }
  }
})
