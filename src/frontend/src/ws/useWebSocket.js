// useWebSocket.js — Hook de conexao WebSocket com o Pi.
//
// Responsabilidades (a implementar):
//  - Conectar ao Pi (ws://<IP_DO_PI>:<porta>) e reconectar em queda.
//  - Enviar Command (contrato 1) e receber Telemetry (contrato 2) @20 Hz.
//  - Expor estado de conexao para a UI poder refletir perda de link.
//
// [ref: Secao 6 da AGENTS.md] · tipos em ../types/contracts.ts
// Fase de scaffolding: stub sem conexao real.

/**
 * @param {string} url URL do WebSocket do Pi (ex.: ws://192.168.0.10:8000/ws).
 * @returns {{ telemetry: object|null, connected: boolean, sendCommand: (cmd: object) => void }}
 */
export function useWebSocket(url) {
  // TODO: implementar conexao, reconexao, parse de telemetria e envio de comando.
  void url;
  return {
    telemetry: null,
    connected: false,
    sendCommand: () => {
      // TODO: enviar Command serializado pelo socket.
    },
  };
}
