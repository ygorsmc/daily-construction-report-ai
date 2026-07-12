# 10. Impacto Ético, LGPD e IA Responsável

> Esta seção analisa em profundidade os impactos **éticos, legais e sociais** do Assistente de Obra IA. Aplica a **LGPD (Lei nº 13.709/2018)** ao fluxo concreto de dados do pipeline, mapeia o sistema contra **princípios de IA Responsável**, identifica riscos e propõe **ações de mitigação** acionáveis. A análise parte de um princípio: tecnologia em construção civil lida com pessoas (operários, engenheiros, gestores) e com decisões que afetam segurança e dinheiro — logo, responsabilidade não é acessório, é requisito.

---

## 10.1. Mapeamento de Dados Pessoais no Pipeline (Data Mapping)

O primeiro passo de qualquer análise de conformidade é saber **quais dados pessoais o sistema realmente trata**. Mapeamento do fluxo atual:

| Dado | Onde está | É dado pessoal? | Categoria LGPD |
|---|---|---|---|
| Nome e e-mail dos destinatários | `data/email_recipients.csv` | **Sim** | Dado pessoal (art. 5º, I) |
| Chat ID do Telegram | `.env` | **Sim** (identifica um dispositivo/pessoa) | Dado pessoal |
| Nome do engenheiro responsável | `registros_exemplo.json` | **Sim** | Dado pessoal |
| Nº de operários, horas, etapa, ocorrências | `registros_exemplo.json` | Não (dados operacionais agregados) | Dado não-pessoal |
| Cidade da obra / coordenadas | `.env` | Não (dado de local, não de pessoa) | Dado não-pessoal |
| Credenciais (tokens, senha SMTP) | `.env` | Sensível do ponto de vista de **segurança** | Segredo (não é dado pessoal, mas exige proteção) |

### ⚠️ Risco latente em produção (dado sensível)
Hoje o diário de obras **não** contém nomes de operários nem detalhes de saúde. Porém, em uso real, ocorrências do tipo *"acidente de trabalho com o operário Fulano"* introduziriam **dados pessoais sensíveis** (saúde — art. 5º, II da LGPD), elevando o nível de exigência legal. **Recomendação:** o diário deve registrar ocorrências de forma **anonimizada/agregada** (ex.: "1 afastamento por acidente leve") salvo quando houver base legal e finalidade específica para identificar a pessoa.

---

## 10.2. Aplicação da LGPD ao Projeto

### 10.2.1. Papéis e bases legais

| Conceito LGPD | Aplicação no projeto |
|---|---|
| **Controlador** (art. 5º, VI) | A **construtora** que opera o sistema e decide as finalidades (a quem enviar, quais dados usar). |
| **Operador** (art. 5º, VII) | Quem roda a infraestrutura (no protótipo, o próprio desenvolvedor/engenheiro). Em modelo SaaS, o fornecedor seria operador. |
| **Titulares** (art. 5º, V) | Engenheiro, gestores e demais destinatários dos relatórios; eventualmente operários citados no diário. |
| **Base legal** (art. 7º) | **Execução de contrato / legítimo interesse** (art. 7º, V e IX) para o envio de relatórios a profissionais da própria obra. Para terceiros externos, recomenda-se **consentimento** (art. 7º, I). |

### 10.2.2. Princípios do art. 6º — autoavaliação

| Princípio (art. 6º) | Como o projeto atende | Lacuna / ação |
|---|---|---|
| **Finalidade** | Dados usados só para gerar/entregar o relatório diário | ✅ Documentar finalidade por escrito (aviso de privacidade) |
| **Adequação & Necessidade (minimização)** | Coleta apenas nome+e-mail/chat e dados operacionais | ✅ Não coletar dados além do necessário; evitar nomes no diário |
| **Livre acesso** | Lista de destinatários é editável no CSV | ⚠️ Criar processo simples de consulta pelo titular |
| **Transparência** | — | ❌ **Adicionar disclaimer** de que o conteúdo é gerado por IA e como pedir descadastro |
| **Segurança** (art. 46) | `.env` fora do Git; inferência local | ⚠️ Reforçar (ver §10.2.4) |
| **Prevenção** | *Error handler*, validação humana no 1º mês | ✅ |
| **Não discriminação** | Sistema não decide sobre pessoas | ✅ (baixo risco — ver §10.3) |
| **Responsabilização (accountability)** | Logs em JSON/CSV registram cada execução | ✅ Trilha de auditoria existente (doc 06) |

### 10.2.3. Direitos dos titulares (art. 18) — como atender

| Direito | Implementação proposta |
|---|---|
| Confirmação e acesso | Responder a pedidos sobre quais dados constam no `email_recipients.csv` |
| Correção | Editar nome/e-mail no CSV |
| Eliminação / oposição | **Descadastro:** remover a linha do CSV; incluir instrução "responda SAIR para deixar de receber" no rodapé do e-mail/Telegram |
| Portabilidade | Exportar os dados do titular (CSV é nativamente portável) |
| Informação sobre compartilhamento | Informar que a entrega usa Telegram e Gmail (ver transferência internacional) |

### 10.2.4. Segurança da informação (art. 46) — estado atual e melhorias

| Medida | Estado | Melhoria recomendada |
|---|---|---|
| Segredos fora do versionamento | ✅ `.gitignore` cobre `.env` | — |
| Senha SMTP | ⚠️ Texto plano no `.env` | Usar **senha de app** dedicada (já é o padrão Gmail) e cofre de segredos em produção |
| Dados em repouso | ⚠️ CSV/logs/áudios sem criptografia | Criptografar disco / restringir permissões de arquivo |
| Dados em trânsito | ✅ HTTPS (APIs) + TLS (SMTP/Telegram) | — |
| Retenção / descarte | ❌ Áudios e logs acumulam indefinidamente | **Política de retenção:** expurgar áudios/logs após N meses |
| Controle de acesso | ⚠️ Máquina local | Restringir acesso físico/lógico ao host |

### 10.2.5. Transferência internacional de dados (art. 33)

Ponto **central** e diferencial do projeto:

- ✅ **A IA (LLM Ollama + TTS Kokoro) roda 100% localmente.** Nenhum dado do diário de obras é enviado a APIs de IA de terceiros (OpenAI, Google, etc.). Isso **elimina a maior fonte de exposição** de dados em projetos de IA e é uma vantagem decisiva de privacidade (RNF02).
- ⚠️ **Canais de entrega usam servidores no exterior:** Telegram e Gmail (Google) processam o conteúdo do relatório e os dados de contato em infraestrutura internacional. Isso configura **transferência internacional** e deve ser informado aos titulares; ambos os provedores possuem salvaguardas contratuais, mas a construtora deve declarar esse fluxo em seu aviso de privacidade.
- ✅ **APIs OpenWeather/Nominatim** recebem apenas **a cidade/coordenadas da obra** — dado não-pessoal.

> **Síntese LGPD:** o ponto mais sensível de um projeto de IA — enviar dados a um modelo na nuvem — **não existe aqui**, pois a IA é local. As lacunas remanescentes (disclaimer, retenção, descadastro, criptografia em repouso) são de **baixa complexidade** e estão endereçadas no plano de ação (§10.5).

---

## 10.3. Análise de IA Responsável

O sistema é classificado, em termos de risco, como um **sistema de IA de risco limitado/mínimo**: ele **apoia** decisões (gera sugestões para um engenheiro avaliar), **não decide** automaticamente sobre pessoas, crédito, contratação ou segurança. Mesmo assim, aplicam-se princípios consagrados (OCDE, UNESCO, e o PL 2.338/2023 — Marco Legal da IA brasileiro em tramitação).

| Princípio de IA Responsável | Situação no projeto | Mitigação implementada / proposta |
|---|---|---|
| **Supervisão humana** (*human-in-the-loop*) | A sugestão é consultiva; o engenheiro decide | ✅ Validação humana recomendada no 1º mês (doc 03); a IA **nunca** aciona obra sozinha |
| **Transparência / explicabilidade** | Destinatário pode não saber que é texto de IA | ❌→ **Adicionar disclaimer** "relatório gerado por IA com base no diário e na previsão; confira antes de decidir" |
| **Robustez e segurança** | Risco de alucinação (correlação espúria clima×obra) | ✅ Prompt restritivo, temperatura 0.7, limite de tokens, "use só os dados fornecidos" (doc 03) |
| **Justiça / não-discriminação** | Não há decisão sobre indivíduos | ✅ Baixo risco; o output é sobre cronograma físico, não sobre pessoas |
| **Responsabilização** | Necessário saber quem responde por erro | ✅ Logs/auditoria; ⚠️ definir responsável formal (o engenheiro valida e assume a decisão final) |
| **Privacidade desde a concepção** (*privacy by design*) | IA local por decisão de arquitetura | ✅ Inferência 100% local — privacidade é uma escolha estrutural, não um remendo |
| **Confiabilidade** | Output pode variar | ✅ Datas dinâmicas, parsing validado; ⚠️ monitorar qualidade ao longo do tempo |

### O risco mais importante: alucinação com consequência física
Uma sugestão errada ("pode concretar quinta") tomada como verdade absoluta pode gerar **prejuízo material e até risco de segurança**. Por isso, o princípio mais crítico aqui é a **supervisão humana**: o sistema é explicitamente posicionado como **assistente de planejamento**, e a decisão final é — e deve continuar sendo — do engenheiro responsável, que possui o registro profissional (CREA) e a responsabilidade técnica pela obra.

---

## 10.4. Impacto Social

### Impactos positivos
- **Democratização tecnológica:** por ser open-source e de custo zero, leva IA aplicada a **construtoras de pequeno e médio porte**, que normalmente ficam de fora da transformação digital do setor.
- **Acessibilidade da informação:** o formato em **áudio** (TTS) torna o relatório consumível por quem está em campo, em deslocamento, ou tem menor familiaridade com leitura de relatórios técnicos longos — aproximando o canteiro do escritório.
- **Redução de desperdício:** menos retrabalho (concretagem/pintura mal planejadas) significa **menos consumo de material e energia** — um ganho ambiental indireto.
- **Valorização do trabalho humano:** ao automatizar a tarefa repetitiva de compilação, devolve ao engenheiro **tempo para o trabalho de maior valor** (análise, decisão, gestão de equipe).

### Riscos sociais e mitigação
| Risco social | Análise | Mitigação |
|---|---|---|
| **Excesso de confiança na IA** (*automation bias*) | Usuário pode aceitar sugestões sem checar | Disclaimer + cultura de validação + posicionar como "assistente" |
| **Deslocamento de função** | Receio de substituir o engenheiro | O sistema **aumenta**, não substitui: não há decisão técnica autônoma; o profissional segue indispensável |
| **Exclusão digital** | Requer máquina, internet e algum letramento técnico | Setup simples via `.env`; formato em áudio reduz barreira; roadmap de onboarding assistido |
| **Vieses do modelo** | LLMs podem carregar vieses de treino | Baixa exposição (domínio técnico restrito); supervisão humana como salvaguarda |

---

## 10.5. Plano de Ação de Conformidade (Checklist Acionável)

Consolidação das lacunas identificadas, com prioridade. Itens de **alta prioridade** são de baixo esforço e alto retorno de conformidade.

| # | Ação | Prioridade | Esforço |
|---|---|---|---|
| 1 | Adicionar **disclaimer de IA** no rodapé do relatório (texto e e-mail): conteúdo gerado por IA, confira antes de decidir | 🔴 Alta | Baixo |
| 2 | Incluir **instrução de descadastro** ("responda SAIR / clique aqui") nas mensagens | 🔴 Alta | Baixo |
| 3 | Redigir **aviso de privacidade** declarando finalidade, base legal, uso de Telegram/Gmail e direitos do titular | 🔴 Alta | Médio |
| 4 | Definir e implementar **política de retenção** (expurgo de áudios/logs após N meses) | 🟠 Média | Baixo |
| 5 | Orientar registro **anonimizado** de ocorrências com pessoas no diário | 🟠 Média | Baixo |
| 6 | **Criptografia em repouso** e restrição de permissões dos arquivos de dados | 🟡 Baixa | Médio |
| 7 | Em modelo SaaS: formalizar **contrato controlador-operador** (art. 39) com cláusulas LGPD | 🟡 Futuro | Médio |

---

> **Conclusão da seção:** O Assistente de Obra IA nasce com uma vantagem ética e legal estrutural — **a IA é local, então os dados da obra nunca saem para um modelo de terceiros**. Isso resolve, por design, o problema mais grave de privacidade em projetos de IA. As lacunas restantes (transparência, descadastro, retenção, segurança em repouso) são pontuais e de baixo custo, e estão organizadas em um plano de ação priorizado. Eticamente, o sistema se mantém no lugar correto: **um assistente que potencializa o engenheiro, sem jamais substituir o julgamento humano sobre uma decisão que envolve segurança, dinheiro e pessoas.**
