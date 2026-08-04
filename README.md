# Relatório Diário Automatizado de Progresso de Obra

Pipeline de automação **on-premise** que gera relatórios executivos diários de progresso de obra, cruzando o diário de obras com a previsão do tempo, gerando a análise com um LLM local, sintetizando o áudio e distribuindo em **dois canais** (Telegram + E-mail) — com zero intervenção manual.

**Portal do projeto:** <https://ygorsmc.github.io/daily-construction-report-ai/>

> **Sobre o autor:** Ygor Carvalho, engenheiro civil com atuação como engenheiro residente, em transição para Engenharia de IA. O diagnóstico, o baseline de ~40 minutos/dia e as decisões de escopo deste projeto vêm da rotina real de preencher e consultar diário de obras em canteiro.

---

## O Problema Real

O engenheiro responsável por uma obra precisa, diariamente, decidir **quando concretar**, **quando pintar ou impermeabilizar** e **que frentes de serviço priorizar**. Para isso ele releria o diário de obras dos últimos dias, consultaria a previsão do tempo e cruzaria as duas coisas mentalmente — um processo repetitivo, manual e, pela correria do canteiro, frequentemente negligenciado.

Na minha experiência como engenheiro residente, essa compilação consome cerca de **40 minutos por dia**. Quando ela é pulada, as decisões saem sem dados atualizados: concretagem em dia de chuva, retrabalho, paralisação evitável.

Este pipeline faz esse cruzamento sozinho, todo dia útil às 06:30, e entrega o resultado em texto e áudio antes do início da jornada.

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
| Ganho sobre o processo manual | **≈ 11×** (−91%) | vs. ~40 min de compilação manual |
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
