import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI runner (python -m gremlin.dashboard) serves live data on :8000.
// In dev we proxy the API + WebSocket there so `npm run dev` is a full app.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/start": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  build: { outDir: "dist" },
});
