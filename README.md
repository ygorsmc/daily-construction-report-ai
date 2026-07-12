# Relatório Diário Automatizado de Progresso de Obra

Pipeline de automação inteligente *Serverless* que gera relatórios executivos diários de progresso de obra, integrando dados climáticos geração de texto por LLM, síntese vocal nativa e distribuição **multicanal** (Telegram + E-mail) — com zero intervenção manual.

## Visão Geral

A automação elimina a compilação manual (que habitualmente consome ~40 minutos por dia do engenheiro residente). A orquestração é centralizada exclusivamente no **n8n** e executa nativamente todo dia útil, às 06:30 da manhã:

1. **Geocodifica** a cidade da obra (OpenStreetMap Nominatim).
2. **Coleta de Clima Preditivo** (OpenWeather API).
3. **Pensa e Analisa** cruzando os dados físicos do dia anterior + chuva computada, criando um Plano de Ação para o dia embasado na **Previsão do Tempo** (Ollama Qwen 2.5:14b).
4. **Sintetiza Áudio** nativamente e off-grid em português do Brasil limpando as marcações de Markdown (Kokoro TTS ONNX).
5. **Distribui Multicanal** em paralelo:
 - **Telegram**: Texto + Áudio HD via Bot API.
 - **E-mail (Gmail SMTP)**: Relatório HTML formatado para lista de destinatários CSV.
6. **Logging e Auditoria**: Métricas de execução em JSON + histórico em CSV.
7. **Error Handling Global**: Captura erros de qualquer nó, loga e notifica via Telegram.

> **Tempo de Execução:** ~3,7 minutos (de ponta a ponta, mediana medida; teto de 5 min).

---

## Requisitos de Hardware / Software

| Componente | Especificações / Setup | Notas |
|---|---|---|
| Ollama | 0.21 (`qwen2.5:14b`) | Modelo de homologação (testado). O sistema é **agnóstico**: basta alterar o `.env` para usar outros modelos (Llama 3, Phi-3, etc). |
| Node.js & n8n | 18+ / `npm i -g n8n` | Para host do orchestrator. |
| Python | 3.12 (`.venv` isolation) | Motor de Áudio (Kokoro) + Microsserviço de E-mail. |
| espeak-ng | `sudo apt install espeak-ng` | Backend fônico obrigatório do TTS. |

---

## Guia de Execução

Para validar o projeto em sua máquina, siga este roteiro simplificado:

1. **Configuração de Chaves**: 
   - Renomeie o arquivo `.env.example` para `.env`.
   - Preencha suas credenciais (Telegram Bot Token, Chat ID, OpenWeather API Key e **SMTP do Gmail**) no `.env`. 
   - O projeto agora utiliza o `.env` como **única fonte de configuração** para Localização, Clima, Modelo do Ollama, Telegram e E-mail.

2. **Lista de Destinatários de E-mail**:
   - Edite o arquivo `data/email_recipients.csv` com os nomes e e-mails dos destinatários.
   - Formato: `nome,email` (uma linha por destinatário).

3. **Dependências do Sistema**:
   - Certifique-se de ter o **Ollama** instalado e o modelo `qwen2.5:14b` baixado (`ollama pull qwen2.5:14b`).
   - Instale o `espeak-ng`: `sudo apt install espeak-ng`.
   - Tenha o **n8n** instalado globalmente (`npm install n8n -g`).

4. **Inicialização**:
   - Execute o script principal: `./start_n8n.sh`. Ele irá configurar o ambiente virtual Python, carregar as variáveis do `.env` e abrir o n8n.
   - No n8n, importe o arquivo `n8n/Relatório Diário de Obra.json`.

5. **Teste**:
   - Com o workflow aberto no n8n, clique em **"Test Workflow"**. O sistema irá ler o diário de obras, consultar o clima, gerar o relatório com a IA local, sintetizar o áudio, enviar para o seu Telegram **e** enviar o relatório por e-mail para os destinatários configurados.

6. **Teste de E-mail (dry-run)**:
   ```bash
   python3 scripts/send_email.py --body-file data/output/temp_tts.txt \
     --recipients data/email_recipients.csv \
     --subject "Teste" --dry-run
   ```

---

## Como Subir o Sistema

### 1. Modelos Analíticos e Preditivos (LLM e TTS)
Prepare os motores pesados de Inteligência Artificial usando um ambiente Linux.

**Ollama e Qwen2.5:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b
```

**Pesos do Kokoro TTS:**
```bash
mkdir -p models
cd models
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### 2. Ambiente Virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install kokoro-onnx soundfile numpy requests
sudo apt install espeak-ng
```

### 3. Automação N8N (Produção)
Ative a máquina de orquestração localmente com as credenciais do seu BOT no Telegram:

**No Linux/WSL:**
```bash
chmod +x start_n8n.sh
./start_n8n.sh
```

**No Windows:**
Execute o arquivo `start_n8n.bat`.

1. Acesse `http://localhost:5678`.
2. Importe o painel de fluxos `n8n/Relatório Diário de Obra.json`.
3. Garanta que a chave/toggle visual no canto superior direito esteja marcada como **Active**. O fluxo passará a rodar permanentemente e enviará os status auditivos no canal todos os dias úteis.

---

## Testes de Stress

O projeto inclui um script de testes de stress para identificar gargalos de performance:

```bash
# Todos os testes (requer Ollama rodando)
python3 scripts/stress_test.py --all --rounds 3

# Apenas SMTP
python3 scripts/stress_test.py --email-only --rounds 5

# Apenas Ollama
python3 scripts/stress_test.py --ollama-only --rounds 3

# Modo simulado (sem conexões reais)
python3 scripts/stress_test.py --all --dry-run
```

O relatório é salvo em `data/output/stress_test_report.json`.

---

## Topologia do Projeto


```
ai_factory_ii_project/
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
