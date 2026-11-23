# Testes HTTP do CAMPPG

As três coleções representam jornadas do tenant:

| Coleção | Fluxo |
|---|---|
| CAMPPG · Gestor e aluno | Programa, turma, participação, grupo, projeto e limpeza |
| Palácio Mental · Jornadas do MVP | `10 - FLUXO DE USO PRINCIPAL`: aluno cria projeto vinculado, salva contexto e verifica privacidade |
| CAMPPG - Colaboração | Dois alunos: publicação, comentário, relevância, pedido e aceite |

A jornada principal tem 15 requisições; cinco exigem outro tenant e ficam
puladas com `allow_isolation=false`. A chamada ao host global apenas confirma
404 para o projeto institucional; não cria projetos pessoais no ambiente global.

## Gerar e verificar

```sh
node tools/build_postman_collection.mjs
node tools/build_postman_collaboration.mjs
node tools/build_postman_institutional.mjs
node --test tools/test_postman_guards.mjs
docker compose exec django python manage.py test tools.postman_contract
```

Os geradores mantêm os nomes dos environments do workspace: **CAMP-PG · Gestor e aluno**,
**P.M · Jornadas do MVP** e **CAMP-PG · Colaboração**.

Os geradores sobrescrevem os modelos de environment. Guarde credenciais em uma
cópia privada. O Git mantém os scripts e os JSONs gerados juntos.

## Environment e Runner web

Importe a coleção e seu `.postman_environment.json` deste diretório. Se a coleção
já existir, escolha substituir/atualizar a versão existente. O environment deve
ser editado em **Environments**, não em Variables da coleção. Preencha senhas
somente nos valores locais sensíveis, sem compartilhar.

Configuração comum: `tenant_a_base=https://camppg.palaciomental.com.br`,
`allow_writes=true` e `approved_write_hosts=camppg.palaciomental.com.br`.

- Institucional: contas Gestor e Aluno, `professor_id` numérico e ativo.
- Jornada principal: conta Membro em `membro_username`/`membro_password`,
  `turma_id`, `orientador_id`; `grupo_id` opcional. A conta precisa participar
  da turma. Mantenha `allow_isolation=false` enquanto não houver outro tenant.
  Para ativar os cinco passos opcionais, configure também `tenant_b_base`,
  `membro_b_username`/`membro_b_password` e `sem_afiliacao_username`/
  `sem_afiliacao_password` com uma conta sem vínculo ao tenant B.
- Colaboração: conta Troli como autor e Carvalho como colaborador; veja
  [README-colaboracao.md](README-colaboracao.md).

No Runner, selecione esse environment, uma iteração e atraso de 300 ms. Na web,
use Desktop Agent. Execute a coleção inteira e preserve a ordem. Uma falha pode
impedir a limpeza: confira os IDs criados, nunca remova apenas por prefixo.

## CLI

```sh
newman run docs/testing/postman/palacio-mental.postman_collection.json -e /caminho/privado/jornada.json --delay-request 300
postman collection run docs/testing/postman/palacio-mental.postman_collection.json -e /caminho/privado/jornada.json --delay-request 300 --no-report-events
```

Para as outras jornadas, substitua o arquivo e seu environment correspondente.
O Runner web e os CLIs precisam receber o mesmo conjunto de valores.

## GitHub Actions

O CI valida scripts e rotas sem acessar produção. O workflow **Postman · Jornadas
do MVP** é manual, exclusivo da main e serializa as execuções. Em Actions,
selecione Run workflow e autorize a criação/remoção dos dados de teste.

O workflow sincroniza as coleções do commit e publica os resultados no workspace
PalacioMental. Alterações manuais no Postman devem entrar nos geradores para
serem preservadas na sincronização seguinte.

Secrets: `POSTMAN_API_KEY` para acessar o workspace e `POSTMAN_TEST_ENV`, um JSON
privado com `gestor_username`, `gestor_password`, `aluno_username`,
`aluno_password`, `professor_id`, `turma_id`, `orientador_id`, `colab_username`,
`colab_password` e `colab_display_name`. Aluno é autor na colaboração; o segundo
aluno é colaborador. Gestor participa apenas da jornada de gestão.

Os arquivos temporários de credenciais são removidos e não são publicados como
artifacts. A automação não executa cenários destrutivos a cada push.

## Limites

Itens pulados não contam como aprovados. O teste HTTP não comprova RLS SQL,
acessibilidade visual, envio de e-mail ou remoção de notificações. A coleção
antiga de saúde/homologação não faz parte da suíte atual.
