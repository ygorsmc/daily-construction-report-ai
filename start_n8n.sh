#!/bin/bash

echo "🚀 Iniciando AI Factory II - Relatório Diário de Obra"
echo "------------------------------------------------------"

# 1. Verifica se o Ollama está rodando
if ! pgrep -x "ollama" > /dev/null; then
    echo "⚠️ Ollama não está rodando. Tentando iniciar o Ollama em background..."
    ollama serve &
    sleep 3
else
    echo "✅ Ollama já está em execução."
fi

# 2. Carrega variáveis do .env
echo "⚙️  Carregando configurações do .env..."
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✅ Variáveis carregadas."
else
    echo "⚠️ Arquivo .env não encontrado."
fi

echo "------------------------------------------------------"
echo "⚙️  Configurando permissões do n8n..."
export NODE_FUNCTION_ALLOW_BUILTIN=fs
export GENERIC_TIMEZONE="America/Sao_Paulo"
export N8N_BLOCK_ENV_VARS_BY_DEFAULT=false
export NODES_EXCLUDE="[]"

echo "✅ Iniciando n8n..."
echo "Acesse http://localhost:5678 no seu navegador."
echo "------------------------------------------------------"

n8n start --open
