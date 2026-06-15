# RELATÓRIO DE SIMULAÇÃO — Empilhadeira Robótica

> Gerado a partir dos testes automatizados e cenários de simulação.
> Backend rodando com `SIM=1`, sem hardware real.

---

## 1. Resumo

O sistema completo (Pi + Emulador + Visão Sintética + Frontend) foi implementado
e testado em modo simulação (`SIM=1`). Todos os módulos de controle, comunicação,
navegação e simulação estão operacionais.

## 2. Resultados dos Testes — Pi (pytest)

| Módulo | Testes | Status |
|--------|--------|--------|
| CRC-8/MAXIM (`test_crc8`) | 8 | ✅ Todos passam |
| Protocolo serial (`test_protocol`) | 9 | ✅ Todos passam |
| Cinemática (`test_kinematics`) | 8 | ✅ Todos passam |
| Navegação (`test_navigation`) | 10 | ✅ Todos passam |
| Máquina de estados (`test_state_machine`) | 11 | ✅ Todos passam |
| Máquina de estados — latch segurança (`test_state_machine`) | +2 | ✅ Novos |
| Filtro de Kalman (`test_kalman`) | 5 | ✅ Todos passam |
| Visão sintética (`test_vision_sim`) | 7 | ✅ Todos passam |
| Emulador firmware (`test_firmware_emulator`) | 11 | ✅ Todos passam |
| Integração E2E (`test_integration_sim`) | 6 | ✅ Todos passam |
| Loop de controle @20Hz (`test_control_loop`) | 4 | ✅ Novos |
| APIs de simulação HTTP (`test_sim_api`) | 2 | ✅ Novos |
| **Total** | **86** | **✅ 86/86** |

## 3. Resultados dos Testes — Frontend (Vitest)

| Componente | Testes | Status |
|------------|--------|--------|
| ModeSelector | 4 | ✅ Todos passam |
| ForkControl | 4 | ✅ Todos passam |
| TelemetryPanel | 3 | ✅ Todos passam |
| **Total** | **11** | **✅ 11/11** |

## 4. Qualidade de Código

| Ferramenta | Status |
|------------|--------|
| `ruff check` (Python) | ✅ Sem erros |
| `black --check` (Python) | ✅ Formatado |

## 5. Matriz de Cenários

| # | Cenário | Testado em | Status |
|---|---------|-----------|--------|
| 1 | Manual: joystick move o robô | `test_manual_drives` | ✅ |
| 2 | Auto: converge ao Zref | `test_auto_converges_to_zref` | ✅ |
| 3 | Auto: perda de tag → PARADO | `test_tag_loss_triggers_stop` | ✅ |
| 4 | Garfo: respeita fim-de-curso | `test_fork_respects_limits` | ✅ |
| 5 | Pose inicial arbitrária → convergência | `test_arbitrary_initial_pose` | ✅ |
| 6 | Sensores do emulador são válidos | `test_sensors_frame_valid` | ✅ |
| 7 | PID converge ao setpoint | `test_pid_converges` | ✅ |
| 8 | Anti-windup limita integral | `test_anti_windup` | ✅ |
| 9 | Watchdog 200ms zera motores | `test_watchdog_stops_motors` | ✅ |
| 10 | Serial drop (falha injetada) | `test_serial_drop` | ✅ |
| 11 | CRC do Pi == CRC do firmware | `test_crc8_cross_check` | ✅ |
| 12 | Ressincronização no `\n` | `test_sensors_frame_decoder_resync` | ✅ |
| 13 | Kalman filtra ruído | `test_kalman_filters_noise` | ✅ |
| 14 | Navegação primária vs fallback | `test_controller_uses_fallback_near_z` | ✅ |
| 15 | Sair de PARADO exige ação explícita | `test_exit_parado_requires_explicit_action` | ✅ |
| 16 | Watchdog de comando no MANUAL | `test_command_watchdog` | ✅ |
| 17 | Tag oculta (injeção) → não detectada | `test_tag_hidden` | ✅ |
| 18 | Visão determinística com seed | `test_deterministic_with_seed` | ✅ |

## 6. Modos de Falha Demonstrados

- **Queda de serial**: emulador para de aceitar setpoints → motores zeram (watchdog).
- **Perda de tag**: >5 frames sem detecção em AUTO → transição para PARADO.
- **Watchdog de comando**: sem comando no MANUAL com robô andando → PARADO.
- **Fim-de-curso do garfo**: garfo bloqueado no sentido proibido (topo/base).
- **Tag oculta (injeção)**: visão sintética retorna não-detecção sob demanda.
- **Slip de roda**: multiplicador por roda altera a odometria.
- **Ambiguidade de pitch**: ruído extra adicionado quando pitch perto de zero.

## 7. Parâmetros Provisórios

Todos marcados com `# PROVISÓRIO — TODO(equipe): confirmar` em `pi/app/config.py`.
Ver tabela completa no `pi/README.md`.

## 8. Como Reproduzir

```bash
# Backend em modo simulação (note o --app-dir pi: o pacote vive em pi/app)
cd src && pip install -e ".[dev]"
SIM=1 uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --app-dir pi

# Frontend
cd src/frontend && npm install && npm run dev

# Testes
cd src && pytest pi/tests/ -v
cd src/frontend && npm test

# Captura de artefatos (backend SIM precisa estar no ar)
bash scripts/capture/capture_sim.sh
```

## 8.1 Achados ao rodar o sistema ao vivo

> Rodar o backend de fato (não só a suíte) expôs bugs que os testes não pegavam.
> Todos foram **corrigidos e verificados ao vivo**. Ver **`ACHADOS_SIM.md`** para o
> detalhe completo. Resumo:
>
> - 🔴 **Corrigido**: APIs `/sim/*` retornavam 422 (modelo Pydantic virava query param).
> - 🔴 **Corrigido**: `/ws` retornava 404 — faltava a dependência `websockets`.
> - 🔴 **Corrigido**: AUTOMATICO não rodava em malha fechada — criado um **loop de
>   controle @20 Hz** dedicado (`tasks/control_loop.py`), desacoplado da cadência de comando.
> - 🟠 **Corrigido**: parada de segurança agora **trava** (`_safety_latched`); só um
>   comando de modo do operador (`acknowledge`) reativa.

## 9. O que falta para o hardware real

- Confirmar todos os parâmetros `TODO(equipe)` com medições no robô montado.
- Calibrar a câmera com xadrez real (intrínsecos).
- Medir offset extrínseco câmera→garfo.
- Sintonia de PID com Ziegler-Nichols no hardware.
- Testar com serial UART real (pyserial-asyncio).
- Validar FOV e alcance da câmera real.
