# Rodada institucional — 2026-11-21

## Origem das evidências

Execuções locais realizadas pelo responsável pelo projeto em Arch Linux e reportadas na sessão de trabalho. Não executadas diretamente pelo assistente. Commit local informado: `0f80240`, branch `feat/postman`. Logs integrais e relatórios de máquina não foram anexados a este registro.

Ferramentas informadas: Node v22.23.2; npm 12.0.2; Newman 6.2.3; Postman CLI 1.87.0; Python 3.14.7; Docker 29.8.1.

## Resultados reportados

| Verificação | Resultado |
|---|---|
| `node --test tools/test_postman_guards.mjs tools/test_postman_identity.mjs` | 9 passaram, 0 falhas, 0 pulados |
| Leitura JSON dos três pares collection/environment | 6 arquivos interpretados sem erro |
| Principal, pasta `20 · Organização e privacidade`, Newman | 10 requisições, 19 asserções, 0 falhas |
| Principal, mesma pasta, Postman CLI | 10 requisições, 19 asserções, 0 falhas; saída 0 informada |
| Institucional completa, Newman | 29 requisições, 50 asserções, 0 falhas |
| Institucional completa, Postman CLI | 29 requisições, 50 asserções, 0 falhas |

Na principal, foi apresentado o POST de exclusão do projeto 31, com HTTP 302 e asserção de redirecionamento aprovada. Isso comprova execução do passo, não uma consulta posterior de ausência do registro. A institucional inclui limpeza e confirmação de exclusão do programa; o resultado agregado não equivale a auditoria de resíduos no banco.

## Decisões de escopo aprovadas

- Manter as jornadas institucionais no host `camppg.palaciomental.com.br`.
- Reservar `palaciomental.com.br` à etapa pública/pessoal, incluindo a colaboração pública; não redirecionar essa lógica para o CAMPPG.
- Adiar a execução de público/pessoal e colaboração.
- Manter isolamento entre tenants desativado (`allow_isolation=false`); não habilitar tenant B nesta rodada.
- Itens desativados não contam como testes aprovados.

## Alterações e pendências

Não foram feitas correções de código ou alterações nas collections/environments nesta sessão. Não houve falha reproduzida nos escopos executados que justificasse correção. Este commit adiciona somente documentação.

Pendências identificadas por inspeção: README institucional divergente do gerador/JSON atual quanto à contagem e limpeza; `tools/postman_contract.py` não inclui a collection institucional no mapeamento inspecionado. Correções dessas pendências exigem proposta e aprovação separadas. CI inspecionado não executa Newman/Postman CLI; automação permanece pendente.

Não declarar cobertura de isolamento entre tenants, RLS SQL, acessibilidade, entrega de e-mail ou ausência completa de resíduos com base nesta rodada. Credenciais e environments privados não devem ser versionados.

## Postman Web — preparação e execução manual

1. No workspace da equipe, usar Import e selecionar os arquivos versionados `palacio-mental.postman_collection.json`, `palacio-mental.postman_environment.json`, `palacio-mental-institucional.postman_collection.json` e `palacio-mental-institucional.postman_environment.json` deste diretório. Não importar environments privados preenchidos. Os scripts de teste já estão nas collections.
2. Em Environments, preencher as credenciais somente em valores locais, marcar os campos sensíveis como seguros e não compartilhar os valores. Manter os modelos versionados sem segredos.
3. Para a principal, configurar host CAMPPG, conta Membro, turma, orientador e grupo elegíveis; `allow_writes=true`, `approved_write_hosts=camppg.palaciomental.com.br`, `allow_personal=false`, `allow_isolation=false`.
4. Para a institucional, configurar host CAMPPG, contas Gestor e Aluno de teste, professor elegível, `allow_writes=true` e somente o host CAMPPG aprovado. Confirmar elegibilidade dos dados a cada rodada.
5. No seletor de agente do Postman Web, usar Desktop Agent para a execução local. Selecionar a collection ou pasta, Run, Functional/Local quando essas opções estiverem disponíveis, environment correspondente, uma iteração e atraso de 300 ms. Preservar a ordem e começar com cookies dos hosts envolvidos limpos, sem sessão de trabalho importante.
6. Na principal, executar somente a pasta `20 · Organização e privacidade`. Na institucional, executar a collection inteira. Não executar público/pessoal ou colaboração nesta etapa.
7. Conferir requisições efetivamente enviadas, asserções, itens pulados e limpeza. Uma nova execução cria novos dados; falhas podem deixar resíduos. Não excluir registros apenas pelo prefixo do título.

Importar as collections não importa os resultados históricos dos CLIs: novas execuções no Runner produzem seus próprios resultados. Não configurar agendamentos ou execução em nuvem nesta etapa.

Documentação de apoio: https://learning.postman.com/docs/getting-started/importing-and-exporting/importing-data/ ; https://learning.postman.com/docs/use/send-requests/variables/managing-environments ; https://learning.postman.com/docs/tests-and-scripts/running-collections/intro-to-collection-runs/
