import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    // Do not silently move to another port. A single explicit port prevents a
    // forwarded workspace tab from accidentally serving a second Vite instance.
    port: 5173,
    strictPort: true,
    // Forwarded development URLs must always receive the current HTML/module
    // graph, rather than a browser or intermediary's cached copy.
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
      "Pragma": "no-cache",
    },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
        ws: true,
      },
      "/ai": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
});
