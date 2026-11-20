#!/usr/bin/env python3
"""Gera segredos locais no .env sem substituir credenciais já definidas."""

from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import urlsplit

ENV_FILE = Path(".env")


def credentials_locais() -> dict[str, str]:
    return {
        "DJANGO_SECRET_KEY": "django-" + secrets.token_urlsafe(48),
        "GUARDIAO_SERVICE_TOKEN": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "PM_APP_DB_PASSWORD": secrets.token_urlsafe(24),
    }


def main() -> None:
    if not ENV_FILE.exists():
        raise SystemExit("Copie .env.example para .env antes de gerar os segredos.")

    lines = ENV_FILE.read_text().splitlines()
    generated_values = credentials_locais()
    changed = []
    database_line = next((line for line in lines if line.startswith("DATABASE_URL=")), "")
    database_value = database_line.split("=", 1)[1] if database_line else ""
    database = urlsplit(database_value)

    for name, generated in generated_values.items():
        found = False
        for index, line in enumerate(lines):
            if not line.startswith(f"{name}="):
                continue
            found = True
            current = line.split("=", 1)[1].strip()
            if not current or current in {"your-secret-key-here", "troque-esta-senha"}:
                lines[index] = f"{name}={generated}"
                changed.append(name)
            break
        if not found:
            lines.append(f"{name}={generated}")
            changed.append(name)

    app_password = next((line.split("=", 1)[1] for line in lines if line.startswith("PM_APP_DB_PASSWORD=")), "")
    if database.username == "pm_app" and not database.password and app_password:
        for index, line in enumerate(lines):
            if line.startswith("DATABASE_URL="):
                lines[index] = line.replace("postgresql://pm_app:@", f"postgresql://pm_app:{app_password}@", 1)
                if lines[index] != line:
                    changed.append("DATABASE_URL")
                break

    ENV_FILE.write_text("\n".join(lines) + "\n")
    if changed:
        print("Configuração local preenchida: " + ", ".join(dict.fromkeys(changed)))
    else:
        print("As credenciais locais já estavam preenchidas. Nenhum valor foi alterado.")
    if database.username and database.username != "pm_app":
        print("DATABASE_URL preservada: usa uma role diferente de pm_app; nenhuma role ou senha do PostgreSQL foi alterada.")


if __name__ == "__main__":
    main()
