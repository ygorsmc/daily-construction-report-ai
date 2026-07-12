#!/usr/bin/env python3
"""
Script de testes de stress para o pipeline multicanal.
Mede performance de cada componente e identifica gargalos.
"""
import sys
import os
import json
import time
import uuid
import argparse
import smtplib
import logging
import statistics
import threading
import psutil
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

class ResourceProfiler:
    def __init__(self):
        self.running = False
        self.max_cpu = 0.0
        self.max_ram = 0.0
        self._thread = None

    def _monitor(self):
        while self.running:
            try:
                cpu = psutil.cpu_percent(interval=0.5)
                ram = psutil.virtual_memory().used / (1024 * 1024)
                if cpu > self.max_cpu: self.max_cpu = cpu
                if ram > self.max_ram: self.max_ram = ram
            except Exception:
                pass

    def start(self):
        self.max_cpu = 0.0
        self.max_ram = 0.0
        self.running = True
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        return {"max_cpu": round(self.max_cpu, 1), "max_ram": round(self.max_ram, 1)}

profiler = ResourceProfiler()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("stress_test")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict:
    env_path = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, val = line.partition("=")
                env_vars[key.strip()] = val.strip().strip("\"'")
    return env_vars


def measure(func, *args, **kwargs):
    start = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        return {"elapsed_s": round(elapsed, 3), "status": "ok", "result": result}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"elapsed_s": round(elapsed, 3), "status": "error", "error": str(e)}


# ── Ollama Tests ─────────────────────────────────────────────────────────────

def test_ollama_response(url: str, model: str, prompt: str) -> dict:
    import urllib.request

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 512},
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
        response_len = len(data.get("response", ""))
        return {"response_chars": response_len, "model": model}


def run_ollama_tests(env: dict, rounds: int, concurrent_workers: int = 1, extreme: bool = False) -> dict:
    url = env.get("OLLAMA_URL", "http://localhost:11434/api/generate")
    model = env.get("OLLAMA_MODEL", "qwen2.5:14b")

    payloads = {
        "curto": "Resuma em uma frase: o clima está bom para concretagem.",
        "medio": "Analise este cenário de obra: " + ("Atividade de concretagem em andamento. " * 20),
        "longo": "Gere um relatório detalhado sobre: " + ("Fundação com estacas hélice contínua, 12 operários, 8h trabalhadas, etapa de infraestrutura 45% concluída. " * 10),
    }
    if extreme:
        payloads["extremo_50k"] = "A chuva paralisou a laje hoje. O guindaste quebrou e tivemos que esperar. " * 600

    results = {}
    for size, prompt in payloads.items():
        log.info("Ollama — payload %s (%d chars), %d rodadas (Concorrência: %d)", size, len(prompt), rounds, concurrent_workers)
        timings = []
        profiler.start()
        
        if concurrent_workers > 1:
            with ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
                futures = [executor.submit(measure, test_ollama_response, url, model, prompt) for _ in range(rounds)]
                for future in as_completed(futures):
                    m = future.result()
                    timings.append(m["elapsed_s"])
                    log.info("  Rodada Concorrente concluída: %.2fs [%s]", m["elapsed_s"], m["status"])
        else:
            for i in range(rounds):
                m = measure(test_ollama_response, url, model, prompt)
                timings.append(m["elapsed_s"])
                log.info("  Rodada %d/%d: %.2fs [%s]", i + 1, rounds, m["elapsed_s"], m["status"])

        prof_stats = profiler.stop()
        results[size] = {
            "prompt_chars": len(prompt),
            "rounds": rounds,
            "min_s": round(min(timings), 3),
            "max_s": round(max(timings), 3),
            "avg_s": round(statistics.mean(timings), 3),
            "median_s": round(statistics.median(timings), 3),
            "max_cpu": prof_stats["max_cpu"],
            "max_ram": prof_stats["max_ram"],
        }
    return results


# ── TTS Tests ────────────────────────────────────────────────────────────────

def test_tts_generation(text: str, output_path: str) -> dict:
    import subprocess

    script_path = PROJECT_ROOT / "scripts" / "generate_audio.py"
    unique_id = uuid.uuid4().hex[:8]
    temp_file = PROJECT_ROOT / "data" / "output" / f"stress_tts_input_{unique_id}.txt"
    temp_file.write_text(text, encoding="utf-8")

    result = subprocess.run(
        [str(PROJECT_ROOT / ".venv" / "bin" / "python3"), str(script_path),
         "--text-file", str(temp_file), "--output", output_path],
        capture_output=True, text=True, timeout=1000,
    )

    file_size_mb = 0
    if os.path.exists(output_path):
        file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
        
    try:
        temp_file.unlink()
    except Exception:
        pass

    return {"exit_code": result.returncode, "file_size_mb": file_size_mb}


def run_tts_tests(rounds: int, concurrent_workers: int = 1, extreme: bool = False) -> dict:
    payloads = {
        "curto": "Este é um teste curto de síntese de voz para validação de performance." * 2,
        "medio": "Relatório semanal de obra. A etapa de fundação avançou significativamente nesta semana, com a conclusão de oitenta por cento das estacas previstas. " * 8,
        "longo": "Relatório detalhado de progresso. A concretagem das vigas de baldrame foi concluída com sucesso, utilizando concreto com resistência de trinta megapascals. A equipe de armação já iniciou a montagem das formas para os pilares do pavimento térreo, com previsão de conclusão em três dias úteis. " * 12,
    }
    if extreme:
        payloads["extremo_50k"] = "A chuva forte paralisou a obra hoje. O guindaste quebrou e tivemos que esperar. " * 600

    results = {}
    for size, text in payloads.items():
        output_path = str(PROJECT_ROOT / "data" / "output" / f"stress_tts_{size}.wav")
        log.info("TTS — payload %s (%d chars), %d rodadas (Concorrência: %d)", size, len(text), rounds, concurrent_workers)
        timings = []
        file_sizes = []
        profiler.start()
        
        if concurrent_workers > 1:
            with ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
                futures = [executor.submit(measure, test_tts_generation, text, output_path.replace(".wav", f"_{i}.wav")) for i in range(rounds)]
                for future in as_completed(futures):
                    m = future.result()
                    timings.append(m["elapsed_s"])
                    if m["status"] == "ok":
                        file_sizes.append(m["result"]["file_size_mb"])
                    log.info("  Rodada Concorrente concluída: %.2fs, %.2fMB [%s]", m["elapsed_s"],
                             m["result"]["file_size_mb"] if m["status"] == "ok" else 0, m["status"])
        else:
            for i in range(rounds):
                m = measure(test_tts_generation, text, output_path)
                timings.append(m["elapsed_s"])
                if m["status"] == "ok":
                    file_sizes.append(m["result"]["file_size_mb"])
                log.info("  Rodada %d/%d: %.2fs, %.2fMB [%s]", i + 1, rounds, m["elapsed_s"],
                         m["result"]["file_size_mb"] if m["status"] == "ok" else 0, m["status"])

        prof_stats = profiler.stop()
        results[size] = {
            "text_chars": len(text),
            "rounds": rounds,
            "min_s": round(min(timings), 3),
            "max_s": round(max(timings), 3),
            "avg_s": round(statistics.mean(timings), 3),
            "avg_file_mb": round(statistics.mean(file_sizes), 2) if file_sizes else 0,
            "max_cpu": prof_stats["max_cpu"],
            "max_ram": prof_stats["max_ram"],
        }
    return results


# ── SMTP Tests ───────────────────────────────────────────────────────────────

def test_smtp_connection(host: str, port: int, user: str, password: str) -> dict:
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
    return {"connected": True}


def test_smtp_send(host: str, port: int, user: str, password: str, body_size: int) -> dict:
    from email.mime.text import MIMEText

    body = "Teste de stress do pipeline multicanal. " * (body_size // 40)
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = user
    msg["To"] = user
    msg["Subject"] = f"[STRESS TEST] Payload {body_size} chars — {datetime.now().isoformat()}"

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)

    return {"sent": True, "body_chars": len(body)}


def run_smtp_tests(env: dict, rounds: int, dry_run: bool = False) -> dict:
    host = env.get("SMTP_HOST", "smtp.gmail.com")
    port = int(env.get("SMTP_PORT", "587"))
    user = env.get("SMTP_USER", "")
    password = env.get("SMTP_PASSWORD", "")

    if not user or not password:
        log.warning("SMTP_USER/SMTP_PASSWORD não configurados — pulando testes SMTP")
        return {"skipped": True, "reason": "credentials_missing"}

    if dry_run:
        log.info("[DRY-RUN] Testes SMTP simulados — sem conexão real")
        return {"skipped": True, "reason": "dry_run"}

    results = {}

    # Connection test
    log.info("SMTP — teste de conexão, %d rodadas", rounds)
    conn_timings = []
    for i in range(rounds):
        m = measure(test_smtp_connection, host, port, user, password)
        conn_timings.append(m["elapsed_s"])
        log.info("  Conexão %d/%d: %.2fs [%s]", i + 1, rounds, m["elapsed_s"], m["status"])

    results["connection"] = {
        "rounds": rounds,
        "min_s": round(min(conn_timings), 3),
        "max_s": round(max(conn_timings), 3),
        "avg_s": round(statistics.mean(conn_timings), 3),
    }

    # Payload size tests
    payload_sizes = {"small_500": 500, "medium_2000": 2000, "large_8000": 8000}
    for label, size in payload_sizes.items():
        log.info("SMTP — payload %s (%d chars), %d rodadas", label, size, rounds)
        timings = []
        for i in range(rounds):
            m = measure(test_smtp_send, host, port, user, password, size)
            timings.append(m["elapsed_s"])
            log.info("  Envio %d/%d: %.2fs [%s]", i + 1, rounds, m["elapsed_s"], m["status"])

        results[label] = {
            "body_chars": size,
            "rounds": rounds,
            "min_s": round(min(timings), 3),
            "max_s": round(max(timings), 3),
            "avg_s": round(statistics.mean(timings), 3),
        }

    # Burst test — multiple emails in rapid succession
    burst_count = min(rounds * 2, 10)
    log.info("SMTP — teste de rajada: %d e-mails consecutivos", burst_count)
    burst_timings = []
    failures = 0
    for i in range(burst_count):
        m = measure(test_smtp_send, host, port, user, password, 500)
        burst_timings.append(m["elapsed_s"])
        if m["status"] == "error":
            failures += 1
        log.info("  Rajada %d/%d: %.2fs [%s]", i + 1, burst_count, m["elapsed_s"], m["status"])

    results["burst"] = {
        "total_emails": burst_count,
        "failures": failures,
        "total_time_s": round(sum(burst_timings), 3),
        "avg_per_email_s": round(statistics.mean(burst_timings), 3),
        "degradation": round(burst_timings[-1] - burst_timings[0], 3) if len(burst_timings) > 1 else 0,
    }

    return results


# ── Telegram Tests ───────────────────────────────────────────────────────────

def validate_telegram_response(response: dict) -> dict:
    """Validates Telegram API response and raises on failure."""
    if not response.get("ok"):
        error_code = response.get("error_code", "unknown")
        description = response.get("description", "Unknown error")
        raise RuntimeError(f"Telegram API error {error_code}: {description}")
    return response


def test_telegram_text(token: str, chat_id: str, text: str) -> dict:
    import urllib.request
    import urllib.parse

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        response = json.loads(resp.read())
    return validate_telegram_response(response)


def test_telegram_audio(token: str, chat_id: str, audio_path: str) -> dict:
    import subprocess

    cmd = [
        "curl", "-s", "-X", "POST",
        f"https://api.telegram.org/bot{token}/sendAudio",
        "-F", f"chat_id={chat_id}",
        "-F", f"audio=@{audio_path}",
        "-F", "caption=[STRESS TEST] Upload de áudio finalizado"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    try:
        response = json.loads(result.stdout)
    except Exception:
        raise RuntimeError(f"Telegram curl failed: {result.stdout[:200]}")
    return validate_telegram_response(response)



def run_telegram_tests(env: dict, rounds: int, dry_run: bool = False) -> dict:
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN/CHAT_ID não configurados — pulando")
        return {"skipped": True, "reason": "credentials_missing"}

    if dry_run:
        log.info("[DRY-RUN] Testes Telegram simulados")
        return {"skipped": True, "reason": "dry_run"}

    payloads = {
        "curto": "[STRESS TEST] Mensagem curta de teste.",
        "medio": "[STRESS TEST] " + ("Teste de performance do pipeline. " * 20),
        "longo": "[STRESS TEST] " + ("Relatório de stress test do pipeline multicanal. " * 60),
    }

    results = {}
    for size, text in payloads.items():
        text_truncated = text[:4096]
        log.info("Telegram — payload %s (%d chars), %d rodadas", size, len(text_truncated), rounds)
        timings = []
        for i in range(rounds):
            m = measure(test_telegram_text, token, chat_id, text_truncated)
            timings.append(m["elapsed_s"])
            log.info("  Rodada %d/%d: %.2fs [%s]", i + 1, rounds, m["elapsed_s"], m["status"])
            time.sleep(0.5)

        results[size] = {
            "text_chars": len(text_truncated),
            "rounds": rounds,
            "min_s": round(min(timings), 3),
            "max_s": round(max(timings), 3),
            "avg_s": round(statistics.mean(timings), 3),
        }
        
    # Audio upload test
    audio_candidates = list(PROJECT_ROOT.glob("data/output/stress_tts_*.wav"))
    if audio_candidates:
        # Pega o áudio mais pesado (longo) para testar o pior cenário
        audio_candidates.sort(key=lambda x: x.stat().st_size, reverse=True)
        audio_path = str(audio_candidates[0])
        file_size_mb = round(os.path.getsize(audio_path) / (1024 * 1024), 2)
        
        log.info("Telegram — upload de áudio (%s, %.2fMB), %d rodadas", Path(audio_path).name, file_size_mb, rounds)
        timings = []
        for i in range(rounds):
            m = measure(test_telegram_audio, token, chat_id, audio_path)
            timings.append(m["elapsed_s"])
            log.info("  Upload %d/%d: %.2fs [%s]", i + 1, rounds, m["elapsed_s"], m["status"])
            time.sleep(1.0)
            
        results["audio_upload"] = {
            "file": Path(audio_path).name,
            "file_size_mb": file_size_mb,
            "rounds": rounds,
            "min_s": round(min(timings), 3),
            "max_s": round(max(timings), 3),
            "avg_s": round(statistics.mean(timings), 3),
        }
    else:
        log.info("Telegram — pulando upload de áudio (nenhum WAV de teste encontrado)")

    return results


# ── Report ───────────────────────────────────────────────────────────────────

def generate_report(results: dict, output_path: str):
    report = {
        "timestamp": datetime.now().isoformat(),
        "components": results,
        "bottleneck_analysis": analyze_bottlenecks(results),
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log.info("Relatório salvo em: %s", output_path)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def analyze_bottlenecks(results: dict) -> dict:
    component_avgs = {}

    for component, data in results.items():
        if isinstance(data, dict) and not data.get("skipped"):
            avg_times = []
            for key, val in data.items():
                if isinstance(val, dict) and "avg_s" in val:
                    avg_times.append(val["avg_s"])
            if avg_times:
                component_avgs[component] = round(statistics.mean(avg_times), 3)

    if not component_avgs:
        return {"message": "Sem dados suficientes para análise"}

    slowest = max(component_avgs, key=component_avgs.get)
    fastest = min(component_avgs, key=component_avgs.get)

    return {
        "slowest_component": slowest,
        "slowest_avg_s": component_avgs[slowest],
        "fastest_component": fastest,
        "fastest_avg_s": component_avgs[fastest],
        "all_averages": component_avgs,
        "recommendation": f"Gargalo principal: {slowest} (média {component_avgs[slowest]}s). Considere otimizar este componente primeiro.",
    }


# ── Visualization ────────────────────────────────────────────────────────────

def format_md_table(headers: list, data_rows: list) -> list:
    """Formats rows as a Markdown table with perfectly aligned vertical pipes (|)."""
    cols = len(headers)
    all_rows = [[str(cell) for cell in headers]] + [[str(cell) for cell in row] for row in data_rows]
    
    # Calculate max width for each column
    col_widths = []
    for col_idx in range(cols):
        max_w = max(len(row[col_idx]) for row in all_rows)
        col_widths.append(max_w)
        
    lines = []
    # Header
    header_line = "| " + " | ".join(f"{headers[i]:<{col_widths[i]}}" for i in range(cols)) + " |"
    lines.append(header_line)
    # Separator
    sep_line = "|-" + "-|-".join("-" * col_widths[i] for i in range(cols)) + "-|"
    lines.append(sep_line)
    # Data rows
    for row in data_rows:
        data_line = "| " + " | ".join(f"{str(row[i]):<{col_widths[i]}}" for i in range(cols)) + " |"
        lines.append(data_line)
    return lines


def generate_markdown_report(results: dict, output_path: str):
    """Generates a Markdown visualization of the stress test results with perfectly aligned columns."""
    # Attempt to load existing critical reflection to preserve it
    existing_reflection = ""
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "## Reflexão Crítica sobre os Resultados" in content:
                parts = content.split("## Reflexão Crítica sobre os Resultados", 1)
                existing_reflection = parts[1].strip()
        except Exception as e:
            log.warning("Não foi possível carregar a reflexão crítica anterior: %s", e)

    lines = []
    lines.append("# 📊 Relatório de Testes de Stress — Pipeline Multicanal")
    lines.append(f"\n> Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
    lines.append("")

    # Summary table
    lines.append("## Resumo por Componente")
    lines.append("")
    
    headers = ["Componente", "Payload", "Rodadas", "Mín (s)", "Méd (s)", "Máx (s)", "CPU %", "RAM MB", "Status"]
    data_rows = []
    component_avgs = {}
    
    for component, data in results.items():
        if isinstance(data, dict) and not data.get("skipped"):
            comp_times = []
            for key, val in data.items():
                if isinstance(val, dict) and "avg_s" in val:
                    status = "✅" if val.get("min_s", 999) < 30 else "⚠️"
                    chars = val.get("prompt_chars") or val.get("text_chars") or val.get("body_chars") or val.get("file_size_mb", "—")
                    payload_desc = f"{key} ({chars})"
                    data_rows.append([
                        f"**{component}**",
                        payload_desc,
                        str(val.get('rounds', '—')),
                        f"{val['min_s']:.3f}" if isinstance(val.get('min_s'), float) else str(val.get('min_s', '—')),
                        f"{val['avg_s']:.3f}" if isinstance(val.get('avg_s'), float) else str(val.get('avg_s', '—')),
                        f"{val['max_s']:.3f}" if isinstance(val.get('max_s'), float) else str(val.get('max_s', '—')),
                        str(val.get('max_cpu', '—')),
                        str(val.get('max_ram', '—')),
                        status
                    ])
                    comp_times.append(val["avg_s"])
            if comp_times:
                component_avgs[component] = round(statistics.mean(comp_times), 3)

    lines.extend(format_md_table(headers, data_rows))

    # Bottleneck analysis
    if component_avgs:
        lines.append("")
        lines.append("## Análise de Gargalos")
        lines.append("")
        
        sorted_components = sorted(component_avgs.items(), key=lambda x: x[1], reverse=True)
        slowest_name, slowest_val = sorted_components[0]
        fastest_name, fastest_val = sorted_components[-1]

        bottleneck_headers = ["Métrica", "Componente", "Tempo Médio"]
        bottleneck_rows = [
            ["🐢 **Mais lento**", slowest_name, f"{slowest_val:.3f}s"],
            ["🚀 **Mais rápido**", fastest_name, f"{fastest_val:.3f}s"]
        ]
        lines.extend(format_md_table(bottleneck_headers, bottleneck_rows))

        lines.append("")
        lines.append("### Ranking de Latência (maior → menor)")
        lines.append("")
        
        ranking_headers = ["Componente", "Progresso Visual", "Tempo Médio"]
        ranking_rows = []
        max_val = sorted_components[0][1] if sorted_components else 1
        for name, avg in sorted_components:
            bar_len = int((avg / max_val) * 30) if max_val > 0 else 0
            bar = "█" * bar_len + "░" * (30 - bar_len)
            ranking_rows.append([name, f"`{bar}`", f"{avg:.3f}s"])
            
        lines.extend(format_md_table(ranking_headers, ranking_rows))

    # Burst test details
    for component, data in results.items():
        if isinstance(data, dict) and "burst" in data:
            burst = data["burst"]
            lines.append("")
            lines.append("## Teste de Rajada (Burst) — SMTP")
            lines.append("")
            
            burst_headers = ["Métrica", "Valor"]
            burst_rows = [
                ["E-mails enviados", str(burst.get('total_emails', '—'))],
                ["Falhas", str(burst.get('failures', 0))],
                ["Tempo total", f"{burst.get('total_time_s', 0):.3f}s"],
                ["Média por e-mail", f"{burst.get('avg_per_email_s', 0):.3f}s"],
                ["Degradação (último - primeiro)", f"{burst.get('degradation', 0):.3f}s"]
            ]
            lines.extend(format_md_table(burst_headers, burst_rows))

    # Critical reflection
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Reflexão Crítica sobre os Resultados")
    lines.append("")
    
    if existing_reflection and not existing_reflection.startswith("> **[PREENCHER"):
        lines.append(existing_reflection)
    else:
        lines.append("> **[PREENCHER APÓS ANÁLISE DOS RESULTADOS]**")
        lines.append(">")
        lines.append("> Analise os dados acima e responda:")
        lines.append(">")
        lines.append("> 1. **Qual é o gargalo real do pipeline?** — Qual componente domina o tempo total de execução? O que pode ser feito para otimizá-lo?")
        lines.append("> 2. **Existe correlação entre tamanho do payload e latência?** — Os tempos escalam linearmente ou exponencialmente com o tamanho da entrada?")
        lines.append("> 3. **O teste de rajada SMTP revelou degradação?** — O servidor de e-mail throttleou após múltiplos envios? Há risco de bloqueio em produção?")
        lines.append("> 4. **Quais otimizações seriam prioritárias para escalar?** — Cache de geocodificação, modelo LLM menor, compressão de áudio, pool de conexões SMTP?")
        lines.append("> 5. **O sistema está pronto para produção?** — Baseado nas métricas, qual é a capacidade máxima estimada (relatórios/hora)?")
    lines.append("")

    md_content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    log.info("Relatório Markdown salvo em: %s", output_path)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stress test do pipeline multicanal")
    parser.add_argument("--all", action="store_true", help="Executa todos os testes")
    parser.add_argument("--ollama-only", action="store_true", help="Testa apenas Ollama LLM")
    parser.add_argument("--tts-only", action="store_true", help="Testa apenas Kokoro TTS")
    parser.add_argument("--email-only", action="store_true", help="Testa apenas SMTP")
    parser.add_argument("--telegram-only", action="store_true", help="Testa apenas Telegram")
    parser.add_argument("--rounds", type=int, default=3, help="Número de repetições por teste (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem conexões reais (SMTP/Telegram)")
    parser.add_argument("--visualize-only", action="store_true", help="Apenas regenera o relatório markdown a partir do JSON de resultados")
    parser.add_argument("--concurrent", type=int, default=1, help="Número de workers concorrentes (default: 1)")
    parser.add_argument("--extreme", action="store_true", help="Adiciona testes com payload gigante de 50.000 caracteres")
    args = parser.parse_args()

    output_path = str(PROJECT_ROOT / "data" / "output" / "stress_test_report.json")
    md_path = str(PROJECT_ROOT / "docs_src" / "05_stress_test_results.md")

    if args.visualize_only:
        if not os.path.exists(output_path):
            log.error("Arquivo de resultados não encontrado para visualização: %s", output_path)
            sys.exit(1)
        with open(output_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        log.info("Regenerando apenas relatório visual a partir de %s...", output_path)
        # Check if timestamp or components exists to extract correctly
        results_data = results.get("components", results)
        generate_markdown_report(results_data, md_path)
        log.info("Pronto!")
        sys.exit(0)

    if not any([args.all, args.ollama_only, args.tts_only, args.email_only, args.telegram_only]):
        args.all = True

    env = load_env()
    results = {}

    if args.all or args.ollama_only:
        log.info("═══ TESTE: Ollama LLM ═══")
        results["ollama"] = run_ollama_tests(env, args.rounds, args.concurrent, args.extreme)

    if args.all or args.tts_only:
        log.info("═══ TESTE: Kokoro TTS ═══")
        results["tts"] = run_tts_tests(args.rounds, args.concurrent, args.extreme)

    if args.all or args.email_only:
        log.info("═══ TESTE: SMTP (Gmail) ═══")
        results["smtp"] = run_smtp_tests(env, args.rounds, dry_run=args.dry_run)

    if args.all or args.telegram_only:
        log.info("═══ TESTE: Telegram ═══")
        results["telegram"] = run_telegram_tests(env, args.rounds, dry_run=args.dry_run)

    generate_report(results, output_path)
    generate_markdown_report(results, md_path)


if __name__ == "__main__":
    main()

