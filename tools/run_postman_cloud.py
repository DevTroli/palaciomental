"""Sincroniza e executa as três jornadas autorizadas no workspace da equipe."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = {
    "palacio-mental-institucional": "30871897-8c01abc6-db4d-4d37-89f3-8930455c98cd",
    "palacio-mental": "30871897-c72d6a1a-9339-4824-a1be-e0da7dcc132b",
    "palacio-mental-colaboracao": "30871897-22c47f1c-5838-478f-a637-e5be16e79182",
}
REQUIRED = (
    "gestor_username", "gestor_password", "aluno_username", "aluno_password",
    "professor_id", "turma_id", "orientador_id", "colab_display_name", "colab_username", "colab_password",
)


def environment(name, credentials):
    path = ROOT / "docs/testing/postman" / f"{name}.postman_environment.json"
    doc = json.loads(path.read_text())
    values = dict(credentials)
    for prefix in ("membro",):
        for field in ("username", "password"):
            values[f"{prefix}_{field}"] = credentials[f"aluno_{field}"]
    for field in ("username", "password"):
        values[f"autor_{field}"] = credentials[f"aluno_{field}"]
    values.update(
        global_base="https://palaciomental.com.br",
        tenant_a_base="https://camppg.palaciomental.com.br",
        allow_writes="true", allow_isolation="false",
        approved_write_hosts="camppg.palaciomental.com.br",
    )
    for entry in doc["values"]:
        if entry["key"] in values:
            entry["value"] = str(values[entry["key"]])
    return doc


def main():
    key = os.environ.get("POSTMAN_API_KEY")
    credentials = json.loads(os.environ.get("POSTMAN_TEST_ENV", "{}"))
    missing = [name for name in REQUIRED if not credentials.get(name)]
    if not key or missing:
        raise SystemExit("Configure POSTMAN_API_KEY e POSTMAN_TEST_ENV; campos ausentes: " + ", ".join(missing))
    failed = []
    with tempfile.TemporaryDirectory(prefix="pm-postman-") as directory:
        for name, uid in COLLECTIONS.items():
            collection = json.loads((ROOT / "docs/testing/postman" / f"{name}.postman_collection.json").read_text())
            collection["info"]["_postman_id"] = uid.split("-", 1)[1]
            request = Request(
                f"https://api.getpostman.com/collections/{uid}", method="PUT",
                data=json.dumps({"collection": collection}).encode(),
                headers={"X-Api-Key": key, "Content-Type": "application/json"},
            )
            # Se a atualização falhar, não executar a versão antiga da nuvem.
            with urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise SystemExit(f"Falha ao sincronizar {name}")
            path = Path(directory) / f"{name}.json"
            path.touch(mode=0o600)
            path.write_text(json.dumps(environment(name, credentials)))
            result = subprocess.run([
                "postman", "collection", "run", uid, "-e", str(path),
                "--delay-request", "300", "--timeout-request", "30000",
            ], check=False)
            if result.returncode:
                failed.append(name)
    if failed:
        raise SystemExit("Jornadas com falhas: " + ", ".join(failed))


if __name__ == "__main__":
    main()
