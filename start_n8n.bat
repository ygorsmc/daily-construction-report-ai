@echo off
setlocal enabledelayedexpansion

echo 🚀 Iniciando AI Factory II - Relatorio Diario de Obra (Windows)
echo ------------------------------------------------------

:: 1. Verifica se o Ollama está rodando
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ✅ Ollama ja esta em execucao.
) else (
    echo ⚠️ Ollama nao esta rodando. Certifique-se de iniciar o Ollama antes.
)

:: 2. Carrega variáveis do .env
echo ⚙️  Carregando configuracoes do .env...
if exist .env (
    for /f "usebackq tokens=*" %%a in (".env") do (
        set "line=%%a"
        :: Ignora comentários e linhas vazias
        if not "!line:~0,1!"=="#" if not "!line!"=="" (
            :: Remove aspas se existirem e define a variável
            set "%%a"
        )
    )
    echo ✅ Variaveis carregadas.
) else (
    echo ⚠️ Arquivo .env nao encontrado.
)

echo ------------------------------------------------------
echo ⚙️  Configurando permissoes do n8n...
set NODE_FUNCTION_ALLOW_BUILTIN=fs
set GENERIC_TIMEZONE=America/Sao_Paulo
set N8N_BLOCK_ENV_VARS_BY_DEFAULT=false
set NODES_EXCLUDE=[]

echo ✅ Iniciando n8n...
echo Acesse http://localhost:5678 no seu navegador.
echo ------------------------------------------------------

n8n start --open
