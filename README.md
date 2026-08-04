# Relatório Diário Automatizado de Progresso de Obra

Pipeline de automação **on-premise** que gera relatórios executivos diários de progresso de obra, cruzando o diário de obras com a previsão do tempo, gerando a análise com um LLM local, sintetizando o áudio e distribuindo em **dois canais** (Telegram + E-mail) — com zero intervenção manual.

**Portal do projeto:** <https://ygorsmc.github.io/daily-construction-report-ai/>

> **Sobre o autor:** Ygor Carvalho, engenheiro civil, em transição para Engenharia de IA. O diagnóstico deste projeto foi construído a partir de normas técnicas, exigências legais e literatura setorial — as fontes estão citadas ao longo da documentação.

---

## O Problema Real

Três decisões recorrentes de uma obra dependem, ao mesmo tempo, **do que já aconteceu no canteiro** e **do que o tempo vai fazer nos próximos dias**:

- **Quando concretar.** A ABNT NBR 14931:2023 condiciona a concretagem sob chuva: precipitação fraca (abaixo de 2,5 mm/h, Tabela 7) dispensa medidas extras, mas acima disso a água interfere na superfície do concreto e a norma exige proteção — sob risco de delaminação, perda de resistência e fissuração.
- **Quando pintar ou impermeabilizar.** A recomendação prática ABRACO RP PAC-001 é explícita: não se aplica pintura sob chuva, neblina ou com umidade relativa acima de 85% — **nem quando houver expectativa de que esse valor seja atingido**. Ou seja, a regra não pede o clima de agora; pede a previsão.
- **Que frente de serviço priorizar.** A alocação de equipes depende do estágio de cada frente (registrado no diário) cruzado com a janela de tempo seco disponível.

O insumo dessas decisões existe e é formalizado: em obra pública, a **Lei nº 14.133/2021 (art. 117, § 1º)** determina que o fiscal do contrato anote "em registro próprio" todas as ocorrências da execução — o diário de obra. *(Ressalva de atualidade: a exigência do **Livro de Ordem** pelo sistema CONFEA/CREA foi **revogada em fevereiro de 2023**; o registro diário permanece por força contratual e, na obra pública, por força da Lei de Licitações.)*

**O problema não é a ausência do dado — é que ele não é consultado na hora de decidir.** A literatura setorial descreve o diário como frequentemente preenchido de forma superficial ou irregular na correria do canteiro, perdendo valor como ferramenta de controle. E o custo de garimpar informação de projeto é mensurável: o estudo *Construction Disconnected* (FMI/PlanGrid, 2018), com cerca de 600 profissionais do setor, apurou **5,5 horas por semana por pessoa apenas procurando dados de projeto** — algo em torno de 66 minutos por dia útil.

Este pipeline elimina esse garimpo para o caso específico do planejamento diário: cruza sozinho o diário de obras com a previsão do tempo, todo dia útil às 06:30, e entrega o resultado em texto e áudio antes do início da jornada.

> **Sobre o baseline de ~40 minutos/dia** usado nos cálculos de ganho e ROI: é uma **premissa de trabalho arbitrada**, não uma medição — ver a nota metodológica na aba *Diagnóstico e Objetivos* do portal, e a análise de sensibilidade em *Métricas e ROI*, que recalcula o retorno para 20, 30 e 40 min/dia.

---

## Como funciona

A orquestração é centralizada exclusivamente no **n8n** (17 nós) e executa todo dia útil, às 06:30:

**Fluxo principal**

1. **Geocodifica** a cidade da obra (OpenStreetMap Nominatim).
2. **Coleta a previsão do tempo** para os próximos 5 dias (OpenWeather API).
3. **Gera a análise** cruzando os apontamentos do dia anterior com a chuva prevista, produzindo um plano de ação para o dia (Ollama `qwen2.5:14b`, rodando localmente).
4. **Sintetiza o áudio** em português do Brasil, localmente e sem API externa, limpando as marcações de Markdown antes da locução (Kokoro TTS ONNX).
5. **Distribui em paralelo:**
   - **Telegram:** texto + áudio via Bot API.
   - **E-mail (Gmail SMTP):** relatório em HTML formatado para a lista de destinatários em CSV.

**Preocupações transversais**

6. **Logging e auditoria:** métricas de execução em JSON + histórico em CSV.
7. **Error handling global:** captura erros de qualquer nó, registra e notifica via Telegram.

> **Tempo de execução:** mediana de **3,5 minutos** ponta a ponta (P50, n = 9 execuções reais; teto de 5 min definido no RNF01).

---

## Prova de conceito

Entrega real do sistema nos dois canais de distribuição — **Telegram** (áudio com player nativo + relatório em texto) e **E-mail** (relatório HTML formatado). Os prints e o trecho de áudio estão na aba **Arquitetura e n8n** do portal, seção *Resultado Final e Prova de Conceito*.

---

## Números do projeto

| Métrica | Valor | Origem |
|---|---|---|
| Latência mediana ponta a ponta (P50) | **3,5 min** | 9 execuções reais medidas |
| Ganho sobre o processo manual | **≈ 11×** (−91%) | vs. baseline arbitrado de ~40 min de compilação manual |
| Aderência ao SLA (< 300 s) | **8 de 9 (88,9%)** | uma execução estourou o teto em 8 s |
| Confiabilidade modelada por execução | **≈ 97,9%** | produto das disponibilidades das dependências |
| Custo de IA por relatório | **R$ 0** | inferência 100% local, sem API paga |

Detalhamento completo (estatística descritiva, modelo de confiabilidade, payback e ROI) na aba **Métricas e ROI**.

---

## Requisitos de Hardware / Software

| Componente | Especificações / Setup | Notas |
|---|---|---|
| **Hardware de referência** | Notebook com **GPU GTX 1660 Ti (6 GB VRAM)**, 16 GB RAM | Máquina em que o projeto foi desenvolvido e medido. O modelo de 14B **excede** os 6 GB e usa *offloading* para RAM/CPU — decisão consciente, ver aba Arquitetura e n8n. |
| Ollama | 0.21 (`qwen2.5:14b`) | Modelo de homologação (testado). O sistema é **agnóstico**: basta alterar o `.env` para usar outros modelos (Llama 3, Phi-3, etc). |
| Node.js & n8n | 18+ / `npm i -g n8n` | Host do orquestrador. |
| Python | 3.12 (`.venv` isolado) | Motor de áudio (Kokoro) + microsserviço de e-mail. |
| espeak-ng | `sudo apt install espeak-ng` | Backend fonético obrigatório do TTS. |

---

## Topologia do Projeto

```
daily-construction-report-ai/
├── data/
│   ├── input/
│   │   └── registros_exemplo.json       # Simulação dos apontamentos de obra
│   ├── output/                          # Relatórios gerados, logs, áudios
│   └── email_recipients.csv             # Lista de destinatários de e-mail
├── docs/                                # Documentação do Projeto (Portal HTML)
├── models/                              # Modelos IA (Kokoro TTS ONNX)
├── n8n/
│   └── Relatório Diário de Obra.json    # Workflow Orquestrador (Multicanal)
├── scripts/
│   ├── generate_audio.py                # Microsserviço de TTS
│   ├── send_email.py                    # Microsserviço de E-mail (Gmail SMTP)
│   └── stress_test.py                   # Testes de stress e performance
├── .env                                 # Configurações de ambiente (ÚNICO ARQUIVO DE SETUP)
├── start_n8n.sh                         # Script de inicialização (Linux/WSL)
└── start_n8n.bat                        # Script de inicialização (Windows)
```

---

## Como rodar o projeto

Guia único de instalação e execução. Ambiente de referência: Linux (ou WSL).

### 1. Modelos de IA (LLM e TTS)

```bash
# Ollama + modelo de linguagem
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b

# Pesos do Kokoro TTS
mkdir -p models && cd models
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ..
```

### 2. Ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install kokoro-onnx soundfile numpy requests
sudo apt install espeak-ng
```

### 3. Configuração (`.env` — fonte única de verdade)

- Renomeie `.env.example` para `.env`.
- Preencha as credenciais: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENWEATHER_API_KEY` e o bloco **SMTP do Gmail**.
- O `.env` concentra também localização da obra, modelo do Ollama e caminhos dos modelos TTS.
- Edite `data/email_recipients.csv` com os destinatários do e-mail, no formato `nome,email` (uma linha por destinatário).

### 4. Subir o n8n e importar o workflow

```bash
chmod +x start_n8n.sh
./start_n8n.sh          # no Windows: execute start_n8n.bat
```

1. Acesse `http://localhost:5678`.
2. Importe o workflow `n8n/Relatório Diário de Obra.json`.
3. Marque o toggle **Active** no canto superior direito para que o cron diário passe a rodar.

### 5. Testar

- Com o workflow aberto no n8n, clique em **"Test Workflow"**: o sistema lê o diário de obras, consulta o clima, gera o relatório com a IA local, sintetiza o áudio, envia ao Telegram **e** dispara o e-mail para os destinatários configurados.
- Dry-run isolado do canal de e-mail:

```bash
python3 scripts/send_email.py --body-file data/output/temp_tts.txt \
  --recipients data/email_recipients.csv \
  --subject "Teste" --dry-run
```

### 6. Testes de stress (opcional)

```bash
python3 scripts/stress_test.py --all --rounds 3      # todos (requer Ollama rodando)
python3 scripts/stress_test.py --email-only --rounds 5
python3 scripts/stress_test.py --ollama-only --rounds 3
python3 scripts/stress_test.py --all --dry-run       # sem conexões reais
```

O relatório é salvo em `data/output/stress_test_report.json`.

---

## Licença

Distribuído sob a licença MIT — ver [LICENSE](LICENSE).
