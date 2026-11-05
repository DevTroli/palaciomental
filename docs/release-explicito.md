# Inicializacao restaurada: migrations no boot

## Decisao da equipe

Em 2026-11-04, a equipe decidiu reverter o fluxo de release explicito introduzido no PR #119. Esta reversao parte da main com o merge Redis #120 preservado; nao retorna o repositorio a um snapshot anterior. Este documento substitui as instrucoes anteriores de release explicito.

## Contrato

O entrypoint executa migrate --noinput usando DATABASE_MIGRATION_URL, com fallback para DATABASE_URL. Depois verifica RLS com DATABASE_URL, coleta estaticos e executa o servidor. PM_RLS_STRICT=true interrompe o boot se a verificacao RLS falhar. Nao desabilitar RLS nem usar superusuario como runtime para contornar falhas.

O Docker invoca o entrypoint com sh, inclusive quando o codigo local esta montado sobre /app sem permissao de execucao no arquivo. Compose usa runserver; a imagem usa Gunicorn.

PM_RELEASE_ID, PM_BACKUP_FOR_RELEASE, PM_BACKUP_REFERENCE e PM_BACKUP_RESTORE_VERIFIED nao sao exigidos pelo boot restaurado. Nao preencher comprovantes ficticios. Backup real continua sendo responsabilidade operacional antes de migrations sobre dados importantes.

## Desenvolvimento local

Usar somente credenciais locais no .env, com DATABASE_URL apontando para database:5432 no Compose. Preservar a role comum de runtime e configurar DATABASE_MIGRATION_URL quando necessario para migrations.

```sh
docker compose -f compose.yaml up --build -d
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs --tail=100 django
```

O comando de inicializacao aplica migrations e pode alterar o schema do banco configurado. Conferir o destino antes de executar. Nao usar down -v nem apagar volumes como procedimento de atualizacao.

## Testes

```sh
python -m unittest discover -s scripts/tests -p 'test_release_contract.py' -v
```

O nome do arquivo foi mantido para compatibilidade com o comando atual do CI; os testes agora verificam o boot restaurado. Usam comandos simulados: nao comprovam Docker, PostgreSQL, backup, Redis ou Railway reais.

## Riscos e pendencias antes de promover

- Migrations voltam a executar em cada boot, inclusive reinicios e comandos administrativos via entrypoint.
- O fluxo nao implementa lock distribuido para migrations concorrentes; coordenar deploys e replicas.
- Falha de migration, RLS estrita ou collectstatic bloqueia o servidor.
- Rollback de codigo nao desfaz migrations; nao reverter schema ou restaurar dados sem plano e autorizacao.
- Conferir no Railway eventual pre-deploy scripts/release.sh e overrides de start antes de promover. Nao presumir que estejam configurados ou removidos. Alteracoes de producao exigem autorizacao separada.
- Remover scripts/release.sh e scripts/start.sh e conferir referencias restantes antes de concluir a limpeza.
- Validar CI, build Docker, boot em banco descartavel e restart. Nao considerar esta lista executada pela existencia do documento.
- Preservar Redis, tenants, roles, volumes e historico de migrations.
