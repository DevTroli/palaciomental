# Postman contra o site real

O percurso padrão é `20 · Organização e privacidade`, no tenant camppg. A pasta `10 · Público e pessoal` só roda com `allow_personal=true`. Não use contas ou projetos reais para testes destrutivos.

## Preparar os arquivos

```sh
git fetch origin
git switch main
git pull --ff-only origin main
node tools/build_postman_collection.mjs
node tools/build_postman_collaboration.mjs
node tools/build_postman_institutional.mjs
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

## Postman CLI

```sh
postman collection run docs/testing/postman/palacio-mental.postman_collection.json \
  -e /caminho/privado/pm.json \
  -i "20 · Organização e privacidade" --delay-request 300 --no-report-events
```

No Postman CLI, a seleção de pasta usa `-i`; no Newman, usa `--folder`.
HTTP 200 no POST de login indica formulário com erro, não autenticação concluída.
Consulte os IDs da turma e do professor responsável no ambiente testado. Os nomes
de usuário diferenciam maiúsculas de minúsculas. Não use a conta Gestor no cenário
que exige a negativa de acesso de Membro.

## Interface web

Importe coleção e environment gerados, selecione uma cópia privada do environment e abra Run. Execute a pasta 20 em ordem, uma iteração. Comece com o cookie jar limpo, sem reutilizar sua sessão de trabalho. Não use Send isoladamente para validar a jornada.

## Resultados e efeitos

A jornada cria um projeto privado vinculado, salva categoria e tags, relê os valores no formulário e tenta excluir o ID criado nesta execução. O teste de persistência não depende mais do texto de um marco no detalhe. Uma resposta 200 após POST de criação significa que é necessário examinar erros do formulário; não equivale a sucesso.

A exclusão e recuperação não são garantidas se houver falha de rede, sessão, interrupção ou erro de script. Registre IDs de execução e confira resíduos com a conta autora; nunca exclua dados só por conterem QA no título. Redirecionar após excluir não comprova sozinho a ausência do registro.

HTTP 404 entre hosts, 403 de gestão e 403 sem afiliação têm significados diferentes. Itens pulados não contam como aprovados. A execução HTTP não comprova RLS em SQL nem acessibilidade visual.

A coleção separada de colaboração publica conteúdo sintético e deixa notificações; execute apenas com aprovação e duas contas controladas. A releitura confirma o comentário, o incremento do voto e a associação do colaborador na equipe.


## Resultados no Postman web — 22/11/2026

| Jornada | Requisições enviadas | Asserções | Relatório do CLI na web |
|---|---:|---:|---|
| Gestor e aluno | 29 | 50 | [Abrir execução](https://go.postman.co/workspace/93cde965-fda5-4c07-b79b-7966778b859e/run/30871897-1576b7d6-59b7-4e74-8bf1-78792f0e9b1c) |
| Pessoal e privacidade | 17 | 31 | [Abrir execução](https://go.postman.co/workspace/93cde965-fda5-4c07-b79b-7966778b859e/run/30871897-84a8bd3d-665c-4187-9d6f-d92c80da5c93) |
| Colaboração pública | 21 | 37 | [Abrir execução](https://go.postman.co/workspace/93cde965-fda5-4c07-b79b-7966778b859e/run/30871897-a4abd94a-bae5-4b1f-a3be-9ba51c5c7d52) |

As três jornadas passaram também no Newman, com as mesmas contagens. Cinco
requisições de isolamento com tenant B ficaram desativadas; dois passos de
reautenticação da colaboração foram dispensados porque a sessão do autor já
estava ativa. Envio/aceite de convite e atuação do professor não foram executados.
Consultas posteriores autenticadas como autores retornaram 404 para os nove
projetos criados nas rodadas, inclusive na tentativa que falhou. Isso não é uma
auditoria de registros auxiliares ou notificações no banco.

A coleção antiga “Saúde pública e homologação” não integra esta suíte; foi
preservada no workspace, sem executar seus cenários antigos.

Na colaboração, a primeira rodada na nuvem falhou por divergência no script
inicial. O script foi sincronizado e a execução final acima passou. O histórico
da falha foi preservado. Nenhuma correção na aplicação foi necessária.

Para apresentar, abra um relatório acima e mostre os grupos de requisições e os
resultados das asserções. São execuções reais do CLI publicadas no Postman; não
são execuções pelo Runner do navegador.

Para repetir pela interface: selecione a coleção e o environment correspondente,
preencha os valores locais sem compartilhá-los e escolha **Run → Functional →
Local**. Use uma iteração, atraso de 300 ms e mantenha a ordem das pastas.
Na web, use Desktop Agent. A institucional é a melhor demonstração do percurso
completo; professor_id precisa apontar para um professor ativo. Na colaboração,
preencha também colab_display_name com o nome exibido na equipe. A principal
precisa de turma existente, orientador e allow_personal=true para os 17 passos.
Não use a aba Performance: estes cenários criam e removem registros.

## GitHub Actions

O CI comum valida scripts e contratos sem acessar produção. O workflow separado
**Postman · Jornadas do MVP** é manual, restrito à main e serializa as execuções.
Em Actions, selecione **Run workflow**, marque a autorização de dados de teste e
execute. Ele atualiza as três coleções pelos arquivos do commit e publica os
resultados no workspace PalacioMental. O workflow só aparece após chegar à main.

Secrets necessários:

- POSTMAN_API_KEY: chave com acesso às coleções da equipe.
- POSTMAN_TEST_ENV: objeto JSON privado com gestor_username, gestor_password,
  aluno_username, aluno_password, professor_id, turma_id, orientador_id e
  colab_display_name. A conta Aluno também executa o percurso pessoal e atua
  como colaborador; a conta Gestor é autora no percurso público.

A turma existente deve aceitar a conta Aluno e ter o orientador informado. Os
hosts são limitados ao CAMPPG e ao Palácio Mental global. O isolamento com outro
tenant permanece desligado. Os arquivos temporários de credenciais são removidos
ao terminar; não são publicados como artifacts. A chave Postman autentica o CLI
no Postman, enquanto as contas de teste autenticam no Palácio Mental.

O workflow foi preparado e os secrets cadastrados, mas ainda não foi executado
no GitHub nesta revisão. Não há agendamento nem teste destrutivo a cada push.
