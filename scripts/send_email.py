#!/usr/bin/env python3
"""
Microsserviço de envio de e-mail via SMTP (Gmail).
Envia relatório em HTML para lista de destinatários CSV.
"""
import sys
import os
import csv
import json
import argparse
import smtplib
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("send_email")

def load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, val = line.partition("=")
                key = key.strip()
                if key not in os.environ:
                    os.environ[key] = val.strip().strip("\"'")


TEMPLATE_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Roboto,Arial,sans-serif;background:#f4f4f4;margin:0;padding:0;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:20px auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <tr>
      <td style="background:linear-gradient(135deg,#0078D4,#005A9E);padding:28px 32px;">
        <h1 style="margin:0;color:#ffffff;font-size:22px;">🏗️ Relatório Diário de Obra</h1>
        <p style="margin:6px 0 0;color:#d0e8ff;font-size:14px;">{subtitle}</p>
      </td>
    </tr>
    <tr>
      <td style="padding:28px 32px;">
        <p style="margin:0 0 8px;color:#666;font-size:13px;">Olá, {recipient_name}.</p>
        <p style="margin:0 0 20px;color:#666;font-size:13px;">Segue o relatório diário gerado automaticamente:</p>
        <div style="background:#f8f9fa;border-left:4px solid #0078D4;padding:20px;border-radius:4px;line-height:1.7;color:#333;font-size:14px;white-space:pre-wrap;">{body}</div>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 32px;background:#f8f9fa;border-top:1px solid #eee;">
        <p style="margin:0;color:#999;font-size:11px;">Gerado automaticamente por Assistente de Obra IA · {timestamp}</p>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def load_recipients(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        log.error("Arquivo de destinatários não encontrado: %s", csv_path)
        sys.exit(1)

    recipients = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("nome", "").strip()
            email = row.get("email", "").strip()
            if email:
                recipients.append({"nome": name or email.split("@")[0], "email": email})

    if not recipients:
        log.error("Nenhum destinatário válido encontrado em %s", csv_path)
        sys.exit(1)

    return recipients


def build_html(body_text: str, recipient_name: str, subtitle: str) -> str:
    return TEMPLATE_HTML.format(
        subtitle=subtitle,
        recipient_name=recipient_name,
        body=body_text.replace("<", "&lt;").replace(">", "&gt;"),
        timestamp=datetime.now().strftime("%d/%m/%Y às %H:%M"),
    )


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_name: str,
    recipient: dict,
    subject: str,
    html_body: str,
    dry_run: bool = False,
) -> dict:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = f"{recipient['nome']} <{recipient['email']}>"
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if dry_run:
        log.info("[DRY-RUN] E-mail construído para %s — não enviado", recipient["email"])
        return {"email": recipient["email"], "status": "dry-run", "error": None}

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            log.info("E-mail enviado com sucesso para %s (tentativa %d/%d)", recipient["email"], attempt, MAX_RETRIES)
            return {"email": recipient["email"], "status": "sent", "error": None, "attempts": attempt}
        except smtplib.SMTPAuthenticationError as e:
            log.error("Falha de autenticação SMTP (sem retry — credencial inválida): %s", e)
            return {"email": recipient["email"], "status": "failed", "error": f"auth_error: {e}", "attempts": attempt}
        except (smtplib.SMTPException, OSError) as e:
            wait = 2 ** attempt
            if attempt < MAX_RETRIES:
                log.warning("Erro SMTP para %s (tentativa %d/%d, retry em %ds): %s", recipient["email"], attempt, MAX_RETRIES, wait, e)
                import time; time.sleep(wait)
            else:
                log.error("Erro SMTP definitivo para %s após %d tentativas: %s", recipient["email"], MAX_RETRIES, e)
                return {"email": recipient["email"], "status": "failed", "error": str(e), "attempts": attempt}
        except Exception as e:
            log.error("Erro inesperado ao enviar para %s: %s", recipient["email"], e)
            return {"email": recipient["email"], "status": "failed", "error": str(e), "attempts": attempt}


def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Enviar relatório de obra por e-mail (Gmail SMTP)")
    parser.add_argument("--body-file", required=True, help="Arquivo .txt com o corpo do relatório")
    parser.add_argument("--recipients", required=True, help="Arquivo CSV com colunas nome,email")
    parser.add_argument("--subject", required=True, help="Assunto do e-mail")
    parser.add_argument("--dry-run", action="store_true", help="Simula envio sem conectar ao SMTP")
    args = parser.parse_args()

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_name = os.environ.get("SMTP_FROM_NAME", "Assistente de Obra IA")

    if not args.dry_run and (not smtp_user or not smtp_password):
        log.error("SMTP_USER e SMTP_PASSWORD devem estar definidos no .env")
        sys.exit(1)

    if not os.path.exists(args.body_file):
        log.error("Arquivo de corpo não encontrado: %s", args.body_file)
        sys.exit(1)

    with open(args.body_file, "r", encoding="utf-8") as f:
        body_text = f.read().strip()

    if not body_text:
        log.error("Corpo do relatório está vazio")
        sys.exit(1)

    recipients = load_recipients(args.recipients)
    log.info("Destinatários carregados: %d", len(recipients))

    results = []
    for recipient in recipients:
        html = build_html(body_text, recipient["nome"], args.subject)
        result = send_email(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            from_name=from_name,
            recipient=recipient,
            subject=args.subject,
            html_body=html,
            dry_run=args.dry_run,
        )
        results.append(result)

    sent = sum(1 for r in results if r["status"] == "sent")
    failed = sum(1 for r in results if r["status"] == "failed")
    summary = {
        "total": len(results),
        "sent": sent,
        "failed": failed,
        "dry_run": args.dry_run,
        "results": results,
    }

    print(json.dumps(summary, ensure_ascii=False))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
