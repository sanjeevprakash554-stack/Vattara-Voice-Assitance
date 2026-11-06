import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            // Gracefully handle backend offline without polluting terminal with ECONNREFUSED stack traces
            if (res && typeof res.writeHead === 'function' && !res.headersSent) {
              try {
                res.writeHead(503, { 'Content-Type': 'application/json' });
                res.end(
                  JSON.stringify({
                    error: 'Backend offline',
                    detail: 'FastAPI server is not responding on 127.0.0.1:8000. Start backend in terminal: cd backend; .\\venv\\Scripts\\activate; uvicorn app.main:app --reload',
                  })
                );
              } catch (_) {
                // response stream already closed
              }
            }
          });
        },
      },
    },
  },
});

