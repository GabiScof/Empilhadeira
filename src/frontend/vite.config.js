// Configuracao do Vite para o frontend React (roda no navegador do celular).
// `host: true` expoe o dev server na rede local (acesso pelo celular via Wi-Fi).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.js",
  },
});
