import { defineConfig, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'

const portFile = path.resolve(__dirname, '../backend/.daena-port')

/**
 * Canonical frontend dev proxy source: backend/.daena-port written by backend/run.py.
 *
 * Dynamic target (2026-04-18): the Vite proxy used to freeze the backend
 * URL at boot. That broke the moment the backend was restarted on a
 * different port — the frontend was stuck ECONNREFUSED-ing the OLD port
 * forever, because http-proxy reads ``options.target`` at boot and Vite
 * never re-read the port file. Users had to restart Vite to recover.
 *
 * The fix: we hand the proxy an options object whose ``target`` field
 * gets MUTATED every time ``.daena-port`` changes on disk. ``http-proxy``
 * reads ``options.target`` on every ``proxy.web()`` call, so mutating the
 * same object reference makes the next request follow the live backend
 * automatically — no Vite restart required.
 */
const HOST = '127.0.0.1'
// We always use 127.0.0.1 rather than "localhost". Node 17+ resolves
// ``localhost`` to ``::1`` (IPv6) first, and the WSL port-relay
// (``wslrelay.exe`` on Windows hosts) only binds IPv4. That mismatch
// produced ECONNREFUSED errors in the Vite proxy even though ``curl
// http://127.0.0.1:<port>/api/v1/health`` returned 200. Forcing IPv4
// loopback eliminates the dual-stack race entirely.

function readPortFromFile(): number | null {
  try {
    const raw = fs.readFileSync(portFile, 'utf-8').trim()
    const port = Number.parseInt(raw, 10)
    if (Number.isFinite(port) && port > 0 && port < 65536) return port
  } catch {
    /* file missing or unreadable */
  }
  return null
}

function resolveInitialBackendUrl(): string {
  if (process.env.DAENA_BACKEND_PORT) {
    const url = `http://${HOST}:${process.env.DAENA_BACKEND_PORT}`
    console.info(`[Daena frontend] Using env override: ${url}`)
    return url
  }
  const port = readPortFromFile()
  if (port !== null) {
    console.info(`[Daena frontend] Proxy -> http://${HOST}:${port} (from ${portFile})`)
    return `http://${HOST}:${port}`
  }
  const fallbackUrl = `http://${HOST}:8000`
  console.warn(
    `[Daena frontend] Missing backend port file at ${portFile}. ` +
      `Starting with ${fallbackUrl}; will auto-follow once backend writes the port.`,
  )
  return fallbackUrl
}

const backendUrl = resolveInitialBackendUrl()

// The options objects below are kept at module scope so the fs.watch
// callback (registered inside `configure`) can mutate ``target`` on the
// SAME reference that http-proxy uses for every request.
const apiProxyOptions = {
  target: backendUrl,
  changeOrigin: true,
  configure: (_proxy: unknown, options: ProxyOptions) => {
    const applyFreshPort = () => {
      const port = readPortFromFile()
      if (port === null) return
      const next = `http://${HOST}:${port}`
      if (options.target !== next) {
        console.info(`[Daena frontend] Proxy target updated -> ${next} (port file changed)`)
        options.target = next
      }
    }
    // Re-read once on startup in case the file appeared between config
    // load and server start (common when frontend races backend boot).
    applyFreshPort()
    // fs.watch can fire twice for the same change on some filesystems;
    // we guard by comparing target strings above so a redundant mutation
    // is a no-op.
    try {
      fs.watch(portFile, { persistent: false }, applyFreshPort)
    } catch (err) {
      // Non-fatal: port-file directory may not exist yet. The proxy
      // still works with the initial target; operators can restart to
      // force a re-read if desired.
      console.warn(`[Daena frontend] fs.watch(${portFile}) failed:`, err)
    }
    // Poll every 2s as a belt-and-suspenders backup — some Windows-side
    // SMB-mounted file systems under WSL don't emit fs.watch events
    // reliably when a WSL process writes the file.
    setInterval(applyFreshPort, 2000).unref?.()
  },
}

const wsProxyOptions = {
  target: backendUrl.replace('http://', 'ws://'),
  ws: true,
  changeOrigin: true,
  configure: (_proxy: unknown, options: ProxyOptions) => {
    const applyFreshPort = () => {
      const port = readPortFromFile()
      if (port === null) return
      const next = `ws://${HOST}:${port}`
      if (options.target !== next) options.target = next
    }
    applyFreshPort()
    try {
      fs.watch(portFile, { persistent: false }, applyFreshPort)
    } catch {
      /* see apiProxyOptions comment */
    }
    setInterval(applyFreshPort, 2000).unref?.()
  },
}

console.info(`[Daena frontend] Proxy target ${backendUrl} (source: ${portFile}; self-healing)`)

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
    // Proxy targets are shared object references mutated by fs.watch on
    // `.daena-port`. When the backend restarts with a different port, the
    // file changes, the watcher updates `target`, and the next request
    // goes to the new backend without restarting Vite.
    proxy: {
      '/api': apiProxyOptions,
      '/ws': wsProxyOptions,
    },
  },
})
