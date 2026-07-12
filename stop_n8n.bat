@echo off
echo 🛑 Encerrando n8n e liberando a porta 5678...

:: Encontra o PID do processo na porta 5678 e o encerra
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5678') do (
    echo Encerrando processo PID %%a...
    taskkill /F /PID %%a
)

echo ✅ Porta 5678 liberada.
pause
