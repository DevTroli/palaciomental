# Postman contra o site real

O percurso padrão é `20 · Organização e privacidade`, no tenant camppg. A pasta `10 · Público e pessoal` só roda com `allow_personal=true`. Não use contas ou projetos reais para testes destrutivos.

## Preparar os arquivos

```sh
git fetch origin
git switch feat/postman
git pull --ff-only origin feat/postman
node tools/build_postman_collection.mjs
node tools/build_postman_collaboration.mjs
node --test tools/test_postman_guards.mjs
docker compose exec django python manage.py test tools.postman_contract
```

A geração sobrescreve os modelos de environment: mantenha credenciais numa cópia privada fora do Git. As JSONs precisam ser regeneradas e commitadas após alterações nas fontes.

## Environment privado

Preencha `tenant_a_base=https://camppg.palaciomental.com.br`, `membro_username`, `membro_password`, `turma_id`, `orientador_id`, `allow_writes=true` e `approved_write_hosts=camppg.palaciomental.com.br`.

A conta deve ser Membro ativo, participante da turma; o orientador deve ser o professor responsável. `grupo_id` é opcional. Sem turma e orientador, o POST de projeto é bloqueado com mensagem de preparação. Não tente contornar usando um Gestor.

Deixe `allow_isolation=false` enquanto B não existir. Para isolamento, configure tenant B, membro B e conta pessoal sem afiliação, ative `allow_isolation` e aprove os hosts em que haverá POST. Não aprove um host só para silenciar uma falha.

## Newman

```sh
newman run docs/testing/postman/palacio-mental.postman_collection.json \
  -e /caminho/privado/pm.json \
  --folder "20 · Organização e privacidade" --delay-request 300
```

## Interface web

Importe coleção e environment gerados, selecione uma cópia privada do environment e abra Run. Execute a pasta 20 em ordem, uma iteração. Comece com o cookie jar limpo, sem reutilizar sua sessão de trabalho. Não use Send isoladamente para validar a jornada.

## Resultados e efeitos

A jornada cria um projeto privado vinculado, salva categoria e tags, relê os valores no formulário e tenta excluir o ID criado nesta execução. O teste de persistência não depende mais do texto de um marco no detalhe. Uma resposta 200 após POST de criação significa que é necessário examinar erros do formulário; não equivale a sucesso.

A exclusão e recuperação não são garantidas se houver falha de rede, sessão, interrupção ou erro de script. Registre IDs de execução e confira resíduos com a conta autora; nunca exclua dados só por conterem QA no título. Redirecionar após excluir não comprova sozinho a ausência do registro.

HTTP 404 entre hosts, 403 de gestão e 403 sem afiliação têm significados diferentes. Itens pulados não contam como aprovados. A execução HTTP não comprova RLS em SQL nem acessibilidade visual.

A coleção separada de colaboração publica conteúdo sintético e deixa notificações; execute apenas com aprovação e duas contas controladas. O contador de relevância e associação exata do colaborador ainda precisam de prova mais forte.
