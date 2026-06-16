// Configuracao do Vite para o frontend React (roda no navegador do celular).
// `host: true` expoe o dev server na rede local (acesso pelo celular via Wi-Fi).
// `envDir: '../'` carrega o .env da raiz do monorepo (src/) onde fica VITE_PI_WS_URL.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  envDir: "../",
  server: {
    host: true,
    port: 5173,
  },
});
