import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

import runtimeErrorOverlay from '@replit/vite-plugin-runtime-error-modal';

// PORT/BASE_PATH задаёт Replit. Вне Replit берём значения по умолчанию,
// иначе сборка падает ещё до старта (см. отчёт о сборке).
const rawPort = process.env.PORT ?? '5173';

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

const basePath = process.env.BASE_PATH ?? '/';
const apiProxy = {
  '/api': {
    target: 'http://127.0.0.1:5000',
    changeOrigin: true,
  },
};
const immutableAssetCache = 'public, max-age=31536000, immutable';
const htmlShellCache = 'no-cache';
const staticCacheHeaders = () => ({
  name: 'intellect-static-cache-headers',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      setStaticCacheHeader(req.url || '', res);
      next();
    });
  },
  configurePreviewServer(server) {
    server.middlewares.use((req, res, next) => {
      setStaticCacheHeader(req.url || '', res);
      next();
    });
  },
});

function setStaticCacheHeader(url: string, res: { setHeader: (name: string, value: string) => void }) {
  const path = url.split('?')[0] || '/';
  if (path.startsWith('/assets/')) {
    res.setHeader('Cache-Control', immutableAssetCache);
    return;
  }
  if (path === '/' || path.endsWith('.html') || !path.includes('.')) {
    res.setHeader('Cache-Control', htmlShellCache);
  }
}

export default defineConfig({
  base: basePath,
  plugins: [
    staticCacheHeaders(),
    react(),
    tailwindcss(),
    runtimeErrorOverlay(),
    ...(process.env.NODE_ENV !== 'production' &&
    process.env.REPL_ID !== undefined
      ? [
          await import('@replit/vite-plugin-cartographer').then((m) =>
            m.cartographer({
              root: path.resolve(import.meta.dirname, '..'),
            }),
          ),
          await import('@replit/vite-plugin-dev-banner').then((m) =>
            m.devBanner(),
          ),
        ]
      : []),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
      '@assets': path.resolve(
        import.meta.dirname,
        '..',
        '..',
        'attached_assets',
      ),
    },
    dedupe: ['react', 'react-dom'],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist/public'),
    emptyOutDir: true,
  },
  server: {
    port,
    strictPort: true,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: apiProxy,
    fs: {
      strict: true,
    },
  },
  preview: {
    port,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: apiProxy,
  },
});
