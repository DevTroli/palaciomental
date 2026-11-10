# Auditoria de desenvolvimento e handoff institucional

Atualização de 6 de novembro de 2026. Recorte: estabilização institucional, branding, onboarding, capa/home e homologação rastreável desta bifurcação. A base revalidada é `02862e5014f8bfd9faaa477524a5dfdbcdb8bc05`, já incluindo os trabalhos paralelos até o PR #123. Não é certificado de segurança, pentest ou homologação exaustiva de produção.

## Resumo executivo

As entregas de tema e capa/home foram integradas pelo responsável nos PRs #117 e #118. A coleção Postman cobre os formulários HTTP reais e vem bloqueada para escrita por padrão. A regressão local sobre a `main` atualizada passou com 215 testes Django, 15 contratos independentes, 8 testes de parser/guardas e 55 asserções no fluxo Newman. Nenhum merge automático, deploy ou e-mail real foi feito nesta etapa de documentação/testes.

O fechamento de desenvolvimento é distinto do aceite operacional. Os gates de e-mail real, mídia após redeploy, runtime RLS atual e matriz visual/papéis em produção continuam explícitos na issue #116.

## Rastreabilidade das entregas

| Entrega | Referência | Resultado no escopo desta bifurcação |
|---|---|---|
| RLS mínima e proteção por host | [PR #104](https://github.com/DevTroli/palaciomental/pull/104) | Política de projetos e fundação dos convites por host |
| Preparação de produção | [PR #105](https://github.com/DevTroli/palaciomental/pull/105) | Gunicorn/WhiteNoise, PostgreSQL e role comum |
| MVP institucional | [PR #106](https://github.com/DevTroli/palaciomental/pull/106) | Portal multi-tenant, hierarquia, convites e RLS |
| Correções de qualidade | [PR #107](https://github.com/DevTroli/palaciomental/pull/107) | Ajustes do CodeFactor associados ao MVP |
| Continuidade de projeto | [PR #108](https://github.com/DevTroli/palaciomental/pull/108) | Criar → contexto → detalhe no host correto, sem o 4xx anterior |
| Entrada por convite | [PR #109](https://github.com/DevTroli/palaciomental/pull/109) | Cadastro/aceite e preparação do Resend via HTTPS |
| Branding persistente | [PR #110](https://github.com/DevTroli/palaciomental/pull/110) | R2, URLs de logo e convite com identidade institucional |
| Onboarding/CSRF | [PR #111](https://github.com/DevTroli/palaciomental/pull/111) | Cadastro mínimo, duas etapas reais, 403 tratada e rodapé contextual |
| Tema flexível | [PR #117](https://github.com/DevTroli/palaciomental/pull/117), issues #112/#113 | Pickr Nano local, cinco tokens, contraste, permissões e propagação |
| Capa/home | [PR #118](https://github.com/DevTroli/palaciomental/pull/118), issue #114 | Upload R2, apresentação, nova home e navbar institucional |
| Testes reproduzíveis | [Issue #115](https://github.com/DevTroli/palaciomental/issues/115) | Coleção, environment vazio, fixtures, docs e testes de contrato |
| Auditoria/fechamento | [Issue #116](https://github.com/DevTroli/palaciomental/issues/116) | Este registro, handoff e gates operacionais pendentes |

Milestone: [#12](https://github.com/DevTroli/palaciomental/milestone/12). Os PRs #119–#123 são trabalhos posteriores/paralelos, não são atribuídos à implementação desta bifurcação. Foram incorporados à base de regressão para não ignorar o boot atual, NoSQL e novos links do Admin.

## Evidências desta rodada

| Camada | Execução | Resultado |
|---|---|---|
| Django/PostgreSQL | `manage.py test` | 215 testes, sem falha |
| Boot | `unittest` de `test_release_contract.py` | 7 testes, sem falha |
| Links Admin | `unittest` de `test_tenant_admin_links.py` | 8 testes, sem falha |
| Parser e guardas | `node --test tools/test_postman_*.mjs` | Registro histórico: 8 testes sem falha; hoje são experimentais e executados sob demanda |
| Newman 6.2.1 | Sessão, branding, multipart, projeto/contexto, comentário, marco, bordas, cadastro/aceite | 31 requests, 55 asserções, sem falha |
| Upload sem branding | `allow_branding=false`, uploads habilitados | 30 requests, 53 asserções; nome/apresentação/cores preservados |
| Modo padrão | Flags de mutação desligados | 1 GET, 2 asserções; nenhum POST |
| Host não aprovado | Teste negativo deliberado | 1 GET; nenhum POST; falha de proteção esperada |
| RLS local | `pm_rls_status --strict` | `pm_app`, superuser=False, bypassrls=False; ENABLE/FORCE e política presentes; comando aprovado |
| Navegador local das entregas #117/#118 | Desktop e 375 px, picker, salvamento/releitura, capa, menu e busca | Sem overflow/erros JS nos percursos verificados |

Os 34 itens da coleção não foram todos enviados: envio real e os dois GETs externos de mídia ficaram desativados. A execução local de convite usou fixture com token novo, sem e-mail real; não demonstra recebimento. A QA visual de mídia local interceptou `/media/` para arquivos do sandbox, pois Gunicorn com DEBUG=False não os serve. Não confundir isso com prova atual de R2.

O inventário individual está em `django-test-inventory.json`. Warnings deliberados dos testes de CSRF, falha de envio e indisponibilidade de cache são cenários negativos esperados, não falhas da suíte.

## Decisões e limites de produto

- **Problema e usuário:** Gestor precisa reconhecer/configurar o ambiente; participante convidado precisa entrar com pouco atrito, sem acesso automático a outro tenant.
- **Decisão implementada:** cinco cores — principal, secundária, destaque, fundo e superfície — com texto/links derivados. Somente Proprietário/Gestor ativo altera identidade pelo servidor.
- **Decisão de mídia:** capa opcional, apresentação curta e logos por tenant, sem CAMP hardcoded. Branding é público; não é storage para arquivos privados.
- **Hipótese:** cadastro mínimo/progressivo e marca contextual devem reduzir fadiga e ambiguidade. Não há experimento de conversão ou evidência de redução de abandono nesta rodada.
- **Métrica futura:** acompanhar conclusão cadastro → aceite, tempo/erros de configuração e reconhecimento do ambiente em teste de uso. Essas métricas não foram instrumentadas nem medidas aqui.
- **Critério técnico:** suíte/contratos aprovados, fluxo sem 4xx indevido e nenhum vazamento nos casos automatizados. Não equivale a acessibilidade integral nem segurança integral comprovada.

## Contradições e riscos que não devem sumir no handoff

- **Ranking:** o PR #120 trouxe alinhamento NoSQL/Redis à `main`, mas `core.views.home` ainda usa votos/atualização e `ranking_provisorio=True`. A home declara isso. Não relatar a vitrine como integrada à projeção oficial Redis; é ponto de alinhamento separado.
- **Boot:** #119 propôs release explícito, mas #121 o reverteu e #122 ajustou a documentação. O código atual mantém migrations no `entrypoint.sh`, usando `DATABASE_MIGRATION_URL` quando disponível. Não reaplicar silenciosamente a configuração revertida.
- **RLS de produção:** a separação runtime/migration foi configurada antes, mas esta rodada só repetiu o strict local. Navegação por host e CI não comprovam a role usada pelo deployment atual.
- **Nomes físicos:** `listaEspera_*` e app label legado permanecem para compatibilidade com migrações/políticas. Não houve renomeação massiva de banco; isso exige plano próprio.
- **Pickr:** versão 1.10.3 local, licença preservada e fallback HEX. O projeto declara funcionalidades congeladas; não presumir evolução ilimitada nem uma auditoria completa de leitor de tela.
- **Mídia substituída:** capas ganham nova chave; remover/desvincular não limpa objetos antigos do R2. Retenção/limpeza requer política e autorização separadas.
- **E-mail:** domínio de envio isolado e branding não garantem aba Principal nem avatar. A mensagem anterior foi confirmada pelo usuário em Promoções.
- **Erros:** o 403 de CSRF tem recuperação; o 404 global genérico observado anteriormente não foi redesenhado neste escopo.

## Gates de operação para encerrar a bifurcação

1. Revisar e integrar manualmente o PR de coleção/auditoria, com CI/CodeFactor aprovados.
2. No deployment atual, executar `python manage.py pm_rls_status --strict` com a conexão runtime; registrar resultado sem URLs de banco/senhas.
3. Em tenant descartável, conferir principal/secundária/destaque/fundo/superfície, upload de logo/capa, recorte mobile e forms login/cadastro. Conferir que outro tenant/global não mudou.
4. Consultar as URLs públicas de imagem e repetir após um redeploy normal autorizado; não forçar indisponibilidade só para teste.
5. Se autorizado um novo convite, usar destinatário controlado; conferir conteúdo/rodapé/logo/capa, criar conta inédita, aceitar e validar papel. Não reutilizar token já consumido.
6. Conferir por papéis o percurso programa → turma → grupo → projeto vinculado; a coleção HTTP não substitui essa homologação de UX.
7. Decidir explicitamente a limpeza das contas/projetos/convites de homologação. Nenhuma exclusão automática é proposta neste PR.

A issue #116 permanece aberta até o aceite desses gates ou decisão explícita do responsável de transferi-los para acompanhamento operacional. A auditoria de desenvolvimento está entregue; não se declara “todo o site global e todos os fluxos testados”.

## Resumo para o chat original

Foram integrados os PRs #117/#118 de tema flexível e capa/home institucional. A branch `test/pm-14-postman-auditoria` contém a coleção Postman segura por padrão, environment sem segredos, fixtures, inventário e auditoria. A regressão foi refeita sobre a main com #123: 215 testes Django + 15 contratos independentes + 8 testes de parser/guardas passaram; Newman executou 31 requests/55 asserções sem falha. O strict de RLS passou localmente com role comum; o atual em produção e mídia após redeploy continuam gates explícitos. Preservar as alterações paralelas #119–#123; em particular o boot atual mantém migrations no entrypoint e a home ainda sinaliza ranking provisório. Não houve merge automático, novo deploy, e-mail real ou exclusão de fixtures nesta etapa.
