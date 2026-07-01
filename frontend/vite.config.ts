import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const backend = {
  target: "https://127.0.0.1:8000",
  secure: false,
  changeOrigin: true,
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/auth": backend,
      "/playlists": backend,
      "/cleanup": backend,
      "/curate": backend,
      "/discover": backend,
      "/taste": backend,
      "/ai": backend,
    },
  },
});
