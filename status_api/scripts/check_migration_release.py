"""Confere o entrypoint de migração do JAR usando somente um banco de testes."""
import os
from pathlib import Path
import subprocess


def run_jar(environment, expected_success, *arguments):
    jar = next(Path("target").glob("*.jar"))
    result = subprocess.run(["java", "-jar", str(jar), "--migrate-only", *arguments],
                            env=environment, capture_output=True, text=True, timeout=90)
    output = result.stdout + result.stderr
    assert (result.returncode == 0) == expected_success, "Resultado inesperado do executor de migração"
    assert "Tomcat" not in output and "Starting StatusApiApplication" not in output, "Migração iniciou o servidor"
    for name in ("GUARDIAO_MIGRATION_JDBC_URL", "GUARDIAO_MIGRATION_PASSWORD"):
        secret = environment.get(name)
        assert not secret or secret not in output, "Saída da migração expôs configuração sensível"
    return output


def main():
    environment = dict(os.environ)
    assert "127.0.0.1" in environment["GUARDIAO_MIGRATION_JDBC_URL"], "Use somente banco local descartável"
    first = run_jar(environment, True)
    assert "histórico validado" in first
    repeated = run_jar(environment, True)
    assert "0 migration(s)" in repeated, "Reexecução reaplicou migrations"
    missing = dict(environment)
    missing.pop("GUARDIAO_MIGRATION_PASSWORD", None)
    run_jar(missing, False)
    wrong_destination = dict(environment, POSTGRES_DB="different_database")
    run_jar(wrong_destination, False)
    wrong_credentials = dict(environment, GUARDIAO_MIGRATION_PASSWORD="invalid-test-password")
    run_jar(wrong_credentials, False)
    run_jar(environment, False, "--server.port=0")
    print("JAR validado: migração, repetição, falhas de configuração e ausência de servidor.")


if __name__ == "__main__":
    main()
