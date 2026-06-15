# Achados da Execução do Simulador — Empilhadeira

> Documento gerado ao **rodar de fato** o simulador completo (backend SIM + WebSocket
> + APIs de simulação) em 2026-06-15, não apenas a suíte de testes.
> Os 80 testes (78 originais + 2 novos) passam, mas **rodar o sistema ao vivo expôs
> bugs que os testes não pegavam** porque a suíte exercita os componentes isolados,
> nunca o caminho de runtime real (WebSocket → state → serial_loop).

---

## TL;DR

| # | Achado | Severidade | Status |
|---|--------|-----------|--------|
| 1 | APIs `/sim/*` com corpo JSON retornavam **HTTP 422** (modelo Pydantic virava query param) | 🔴 Bloqueante | ✅ **Corrigido** |
| 2 | `/ws` retornava **HTTP 404** — falta a dependência `websockets` (uvicorn sem suporte a WS) | 🔴 Bloqueante | ✅ **Corrigido** |
| 3 | **AUTOMATICO não rodava em malha fechada** com o frontend real — robô recebia 1 setpoint e congelava | 🔴 Funcional | ✅ **Corrigido** |
| 4 | Parada de segurança (perda de tag) **não travava (latch)** — oscilava PARADO↔AUTOMATICO | 🟠 Segurança | ✅ **Corrigido** |

A suíte estava verde porque **nenhum teste passa pela fiação real**: os testes de
"integração" chamam `nav.compute()` + `sm.step()` + emulador num `for` Python, e as
APIs `/sim/*` não tinham nenhum teste de camada HTTP.

---

## Como rodar (corrigido e verificado)

```bash
# 1. Backend em modo simulação
cd src
python3 -m venv .venv && source .venv/bin/activate   # se ainda não existir
pip install -e ".[dev]"        # agora inclui 'websockets' (necessário p/ /ws)
SIM=1 uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --app-dir pi

# 2. Frontend
cd src/frontend && npm install && npm run dev   # http://localhost:5173 (e /demo)

# 3. Testes
cd src && pytest pi/tests/ -v          # 80 passam
cd src/frontend && npm test            # 11 passam

# 4. Verificação completa (lint + format + testes + build)
bash scripts/verify.sh

# 5. Captura de artefatos do mundo simulado (backend SIM precisa estar no ar)
bash scripts/capture/capture_sim.sh    # grava em src/artifacts/
```

> **Nota importante sobre `--app-dir pi`:** o pacote `app` vive em `pi/app`. Ao rodar o
> uvicorn da raiz `src`, passe `--app-dir pi` (ou rode de dentro de `pi/`), senão
> `app.main` não é encontrado. O README atual omite isso.

---

## Detalhe dos achados

### 1. APIs `/sim/*` retornavam HTTP 422 — 🔴 Corrigido

**Sintoma:** todo `POST /sim/reset-pose` e `POST /sim/inject-fault` respondia
`422 Unprocessable Entity` com `{"detail":[{"loc":["query","req"],"msg":"Field required"}]}`.

**Causa-raiz:** `pi/app/main.py` tem `from __future__ import annotations`, o que torna
todas as anotações **strings adiadas**. O FastAPI resolve essas strings via
`get_type_hints` contra o namespace **global** do módulo. Os modelos `PoseResetRequest`
e `FaultRequest` estavam definidos como **classes locais dentro de `_register_sim_routes`**,
logo não existiam nos globals → o FastAPI não os reconhecia como modelos Pydantic e caía
no fallback de "parâmetro de query".

**Correção:** mover `PoseResetRequest` e `FaultRequest` para o nível de módulo.
Verificado ao vivo: `reset-pose` move o robô, injeções de falha persistem, `clear_all`
reseta. `scripts/capture/capture_sim.sh` agora completa fim-a-fim.

**Regressão coberta por:** `pi/tests/test_sim_api.py` (verifica `requestBody` no OpenAPI).

### 2. `/ws` retornava HTTP 404 — 🔴 Corrigido

**Sintoma:** conectar em `ws://host:8000/ws` falhava com `HTTP 404`. O painel do
operador e o `/demo` nunca recebem telemetria nem enviam comandos.

**Causa-raiz:** `pyproject.toml` listava `uvicorn` puro (não `uvicorn[standard]`) e
nenhuma implementação ASGI de WebSocket (`websockets`/`wsproto`). Sem ela, o uvicorn
sobe sem suporte a WebSocket e rejeita o upgrade com 404.

**Correção:** adicionar `websockets` às dependências em `pyproject.toml`. (Optei por
`websockets` puro em vez de `uvicorn[standard]` para evitar compilar `uvloop`/`httptools`
no Raspberry Pi.) Verificado: WebSocket conecta, telemetria flui a 20 Hz, comandos são
processados.

### 3. AUTOMATICO não rodava em malha fechada com o frontend real — ✅ Corrigido

**Sintoma (ao vivo, antes):** o operador clicava AUTOMATICO uma vez (como o frontend real
faz) e o robô **ficava parado para sempre** — rodas em 0, distância à tag constante em 50 cm.

**Causa-raiz (arquitetural):** a navegação e a máquina de estados são executadas
**dentro do loop de recepção de comando** do WebSocket (`websocket_handler.py`,
`while True: raw = await websocket.receive_text()`). O `serial_loop` roda a 20 Hz e só
**reenvia** o `state.current_setpoint` — que só é recalculado quando chega um comando.

Mas o frontend (`App.jsx`) envia comando **apenas em eventos** (clique de modo,
movimento do joystick, botão do garfo) — não há streaming contínuo. Logo, em AUTOMATICO,
a navegação roda **uma vez** (no clique) e nunca mais. O robô recebe um setpoint
congelado e o `serial_loop` o repete indefinidamente.

> Isso só "funciona" se o cliente enviar comandos a ~20 Hz (foi o que meu cliente de
> teste fez, e aí o robô convergiu). O AGENTS.md (§6/§7) implica um **loop de controle
> @20 Hz** independente do operador, que não existe na implementação.

**Correção aplicada:** criado `pi/app/tasks/control_loop.py` — uma **tarefa de controle
dedicada @20 Hz** (`config.CONTROL_HZ`) que lê `last_vision` + a intenção do operador
(`last_command`), propõe velocidades via cinemática (MANUAL) / navegação (AUTOMATICO),
passa pela máquina de estados e escreve `current_setpoint`. O `websocket_handler` passou
a só **registrar a intenção** do operador (modo/joystick/garfo) e o watchdog/perda de tag
agora vivem no loop de controle. O `main.py` sobe `control_loop` no lugar do antigo
`watchdog_loop`.

**Verificado ao vivo:** com **um único** comando AUTOMATICO (sem streaming), o robô
navega e reduziu ~20 cm em direção à tag (antes: 0 cm / congelava).

**Coberto por:** `pi/tests/test_control_loop.py` (4 testes, incluindo
`test_auto_drives_from_single_command`).

### 4. Parada de segurança não travava (latch) — ✅ Corrigido

**Sintoma (ao vivo, com stream contínuo, antes):** ao ocultar a tag em AUTOMATICO, a
máquina ia a PARADO no 6º frame, mas **no frame seguinte voltava a AUTOMATICO** e oscilava
PARADO↔AUTOMATICO a cada ~300 ms.

**Causa-raiz:** em `state_machine._handle_transition`, a saída PARADO→AUTOMATICO era
incondicional. Com o loop de controle do achado #3 re-propondo o modo selecionado todo
tick (20 Hz), isso reentraria no modo ativo a cada tick — exatamente a condição de
oscilação. Contradiz o requisito ("Sair de PARADO exige ação explícita do operador").

**Correção aplicada:** a máquina de estados ganhou um **latch de segurança**
(`_safety_latched`), ligado ao entrar em PARADO por perda de tag, watchdog ou
`force_stop()`. Enquanto travado, `_handle_transition` **bloqueia** a reativação, mesmo
que o loop re-proponha AUTOMATICO. O latch só é liberado por `acknowledge()`, chamado pelo
`websocket_handler` quando chega um **comando de modo discreto** do operador (o frontend
é orientado a evento, então um comando == ação humana real).

**Verificado ao vivo:** tag oculta → PARADO; a tag voltar **sem novo comando** mantém
PARADO; só um **novo comando** AUTOMATICO reativa.

> **Premissa documentada:** "ação explícita do operador" = um comando de modo recebido
> pelo WebSocket. Isso vale porque o frontend só envia ao interagir. Um cliente que faça
> *streaming* contínuo de comandos liberaria o latch a cada mensagem — se algum dia o
> frontend passar a streamar, trocar o gatilho do `acknowledge` por uma borda de seleção.

**Coberto por:** `pi/tests/test_state_machine.py`
(`test_safety_stop_latches_under_continuous_request`, `test_acknowledge_releases_safety_latch`)
e `pi/tests/test_control_loop.py::test_tag_loss_in_loop_latches_parado`.

---

## Por que a suíte não pegou os achados 1–4

- **APIs `/sim/*`**: zero testes de camada HTTP (agora há `test_sim_api.py` p/ o #1).
- **`/ws` / dependência**: nenhum teste sobe o uvicorn de verdade; usam objetos diretos.
- **#3 e #4**: os testes de "integração" (`test_integration_sim.py`) dirigem o loop
  **manualmente** em Python (`for i in range(2000): nav.compute(...); sm.step(...)`),
  reproduzindo o que a implementação **deveria** fazer — não o que ela faz em runtime.
  Nunca passam por `websocket_handler` + `serial_loop` + cadência real do frontend.

**Cobertura adicionada:** `test_control_loop.py` agora dirige o loop real de controle
(sem streaming) e valida convergência + latch; `test_state_machine.py` cobre o latch de
segurança; `test_sim_api.py` cobre a camada HTTP das rotas `/sim/*`.

**Ainda recomendado:** um teste E2E que suba a app de fato (com `httpx`/`TestClient`) e
dirija via WebSocket real, fechando o último gap (a fiação `websocket_endpoint` em si
ainda não tem teste automatizado — foi validada manualmente ao vivo). Requer adicionar
`httpx` às deps de dev.

---

## O que falta para o hardware real (inalterado da análise original)

- Confirmar todos os parâmetros `TODO(equipe)` com medições no robô montado.
- Calibrar a câmera com xadrez real (intrínsecos) e medir offset extrínseco câmera→garfo.
- Sintonia de PID (Ziegler-Nichols) no hardware.
- Testar serial UART real (pyserial-asyncio) — o caminho `serial_loop_real` nunca rodou.
- Validar FOV e alcance da câmera real (a visão sintética usa FOV/alcance provisórios).
