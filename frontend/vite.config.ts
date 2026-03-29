import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'

const portFile = path.resolve(__dirname, '../backend/.daena-port')

/**
 * Canonical frontend dev proxy source: backend/.daena-port written by backend/run.py.
 * A warning fallback is kept for standalone frontend work, but the supported dev
 * startup path is start-daena.bat or start-backend.bat -> backend/run.py.
 */
function getBackendUrl(): string {
  // Environment variable override takes priority (useful when port file is stale)
  if (process.env.DAENA_BACKEND_PORT) {
    return `http://localhost:${process.env.DAENA_BACKEND_PORT}`
  }
  try {
    const port = Number.parseInt(fs.readFileSync(portFile, 'utf-8').trim(), 10)
    if (port > 0 && port < 65536) {
      return `http://localhost:${port}`
    }
  } catch {
    // The canonical start path writes the port file before Vite starts.
  }
  const fallbackUrl = 'http://localhost:8000'
  console.warn(
    `[Daena frontend] Missing backend port file at ${portFile}. ` +
      `Falling back to ${fallbackUrl}. Start the backend with backend/run.py to restore the canonical contract.`,
  )
  return fallbackUrl
}

const backendUrl = getBackendUrl()

console.info(`[Daena frontend] Proxy target ${backendUrl} (source: ${portFile})`)

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (
            id.includes('/react/') ||
            id.includes('/react-dom/') ||
            id.includes('/scheduler/') ||
            id.includes('/use-sync-external-store/')
          ) {
            return 'vendor-react'
          }
          if (
            id.includes('/react-router/') ||
            id.includes('/react-router-dom/') ||
            id.includes('/@remix-run/')
          ) {
            return 'vendor-router'
          }
          if (
            id.includes('/zustand/') ||
            id.includes('/axios/')
          ) {
            return 'vendor-state-data'
          }
          if (id.includes('framer-motion')) {
            return 'vendor-motion'
          }
          if (id.includes('lucide-react')) {
            return 'vendor-icons'
          }
          return undefined
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/ws': {
        target: backendUrl.replace('http://', 'ws://'),
        ws: true,
      },
    },
  },
})
