import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8000",
      "/playlists": "http://localhost:8000",
      "/cleanup": "http://localhost:8000",
      "/curate": "http://localhost:8000",
      "/discover": "http://localhost:8000",
      "/taste": "http://localhost:8000",
      "/ai": "http://localhost:8000",
    },
  },
});
