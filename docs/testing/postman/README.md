# Homologação institucional no Postman

Coleção importável de formulários Django reais, não uma API REST fictícia. São cinco fluxos ordenados, com sessão, CSRF, IDs extraídos de redirecionamentos e caminhos negativos. A issue #115 acompanha a entrega; a auditoria e os gates finais estão na #116.

## Começar com segurança

Importe `palacio-mental.postman_collection.json` e `palacio-mental.postman_environment.json`. A pasta **00 · Saúde pública** consulta `https://palaciomental.com.br/saude` e `/pronto` em produção usando somente GET, sem login e sem efeitos colaterais. Duplique o environment para uso privado e selecione-o no Runner. Não publique senhas, cookies, tokens de convite ou environments preenchidos.

- **Padrão seguro:** todos os `allow_*` vêm como `"false"`. A execução faz somente o GET público inicial; os fluxos dependentes ficam sem execução, não “aprovados”.
- **Escrita controlada:** em um tenant descartável, preencha `username`, `password`, `allow_writes="true"` e `approved_write_host` com o host exato, incluindo porta se houver. Exemplo: `homolog-a.palaciomental.com.br`. Divergência bloqueia a requisição antes do POST e encerra o fluxo.
- **Conta adequada:** use Gestor ativo para a execução completa. Proprietário pode gerir marca, mas convida somente Gestor; o envio opcional desta coleção convida Membro, permitido a Gestor/Professor. Professor não acessa toda a gestão.
- **Não usar dados reais:** o fluxo cria um projeto privado novo com prefixo `TESTE-POSTMAN`. Arquivos e marca podem ser substituídos somente quando os respectivos flags forem habilitados. Nada é excluído automaticamente.
- **Sem segredos no export:** CSRF e ID de projeto são variáveis locais da execução, não valores gravados no environment entregue. Senhas e convite devem permanecer apenas no ambiente privado de quem testa.

Execute a coleção inteira em ordem. `setNextRequest(null)` interrompe o Runner quando um pré-requisito essencial falha; não controla o botão Send isolado, conforme a [documentação de workflows do Postman](https://learning.postman.com/docs/tests-and-scripts/running-collections/building-workflows).

```sh
# Na raiz do repositório, com environment privado fora do Git:
newman run docs/testing/postman/palacio-mental.postman_collection.json \
  -e /caminho/privado/pm-homologacao.json \
  --working-dir .
```

Não use `--insecure` em produção. A QA local usou certificado de teste e resolução DNS restrita ao processo Newman; isso não faz parte da coleção entregue. Relatórios verbosos podem incluir URLs com token: não publique esses relatórios, cookies ou corpos de autenticação.

## Fluxos e dependências

| Pasta | Pré-requisito | Verifica | Efeito |
|---|---|---|---|
| Saúde pública | Nenhum | `/saude` e `/pronto` no domínio global de produção | Somente GET; não altera dados |
| Sessão e entrada | Login válido no tenant A | Formulário, CSRF, redirect de autenticação, home institucional e projetos | Sessão de teste |
| Gestão e identidade | Gestor ativo e sessão | Cinco cores, releitura, membros/programas; uploads e envio opcionais | Marca/envio somente com flags próprios |
| Projeto e contexto | Sessão e novo CSRF | Básico → ID do Location → contexto sem 4xx → salvar → detalhe → comentário → marco → releitura | Um projeto privado por execução |
| Bordas e isolamento | ID criado no fluxo anterior | Mesmo ID no tenant B/global, rejeição CSRF e recuperação | POST inválido não deve persistir |
| Entrada por convite | Convite novo de Membro e dados inéditos | Sair do gestor → GET anônimo → cadastro mínimo → aceite → afiliação → token consumido → Membro sem gestão | Nova conta/afiliação |

Não configure redirects automáticos: os itens os desabilitam para que um POST inválido que volta ao formulário com HTTP 200 não pareça sucesso. O CSRF é extraído do HTML e renovado após mudanças de sessão. Headers Origin/Referer usam o host configurado.

As dependências são intencionais: se não houve login, itens protegidos são pulados; se a criação não retorna ID/destino válidos, o fluxo é interrompido. Não informe manualmente um ID antigo para contornar um pré-requisito.

## Flags opcionais

| Variável | Habilita | Condições / limites |
|---|---|---|
| `allow_branding` | POST das cinco cores, nome e apresentação | Sobrescreve esses valores em tenant descartável |
| `allow_uploads` | Multipart de logo e capa | Substitui apenas imagens; preserva os demais valores lidos no GET anterior |
| `allow_media_fetch` | GET das imagens públicas extraídas do upload | Exige upload anterior na mesma execução; desativar se Gunicorn local não serve `/media/` |
| `allow_email` | Convite de Membro para `invite_email` | Destinatário controlado e emissor Gestor; 302 não prova entrega |
| `allow_invite_accept` | Consome `invite_path` e cria conta nova | Convite de Membro, `new_username` inédito e `new_password` forte |

Todos os POSTs ainda exigem `allow_writes` e host aprovado, mesmo quando outro flag está ligado. O caminho do convite deve ser `/convites/organizacao/TOKEN/aceitar/`, sem domínio; mantenha-o privado.

O upload reenvia nome, apresentação e três cores legadas exatamente como foram lidos no formulário, sem usar `branding_name`. Não envia os novos campos de tema, preservando o JSON existente. Uma asserção posterior compara todos os campos não relacionados às imagens com o snapshot anterior. Isso também é testado com `allow_branding=false` e caracteres escapados no HTML.

O envio e o aceite têm uma fronteira manual: o token chega ao destinatário, não é exposto pelo painel administrativo. Para testar entrega real, habilite somente o envio, verifique caixa/eventos do provedor e use um convite novo na execução de aceite. Como esta última sai do gestor, não a rode com uma sessão de trabalho importante.

Os itens de mídia validam HTTP 200 e Content-Type de imagem. Isso não comprova persistência depois de redeploy nem política de acesso a documentos: o bucket deste fluxo contém apenas identidade visual pública.

## O que esta coleção não comprova

- **RLS no PostgreSQL:** host B negado não é evidência suficiente de política SQL. Pode ser sessão ausente, afiliação ausente ou bloqueio do middleware. Execute `python manage.py pm_rls_status --strict` com a conexão runtime de produção e mantenha os testes de política do Django.
- **Permissões completas:** o POST de Membro é um caso adicional. Proprietário, Gestor, Professor, afiliação inativa e isolamento A/B têm testes Django próprios.
- **Projeto vinculado:** projetos com programa/turma/grupo e suas regras de elegibilidade estão na suíte Django. O projeto criado pelo Postman é autônomo.
- **Experiência visual:** layout, logo nos forms, contraste, teclado, recorte da capa, estados de erro e 375 px exigem navegador.
- **Entrega de e-mail:** resposta HTTP e evento de envio não garantem Inbox/Principal nem avatar de remetente. Conferir destinatário e conteúdo reais.
- **Infraestrutura:** wildcard/DNS/TLS, separação runtime/migration, R2 e redeploy devem ser revalidados na operação.

## Inventário e reprodução

`../django-test-inventory.json` lista individualmente os testes descobertos na base deste PR. A coleção não afirma converter todos eles em HTTP. Grupos relevantes:

- `plataforma.tests.institucional`: acesso, convites, CSRF, formulários, marca, capa, hierarquia e projetos.
- Testes de RLS/isolamento: executar no PostgreSQL com role comum, conforme o CI.
- `core` e testes de comentários: cache/rankings e integrações NoSQL/fallbacks da `main` atualizada.
- `plataforma.tests.administracao`: links seguros do Admin para abrir tenant.
- `plataforma.tests.test_postman_contract`: rotas existentes, IDs únicos, redirects e export seguro.
- `scripts/tests`: contratos de boot e links do Admin, executados separadamente do runner Django.

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py pm_rls_status --strict
python manage.py test
node --test tools/test_postman_*.mjs
python -m unittest discover -s scripts/tests -p 'test_release_contract.py' -v
python -m unittest discover -s scripts/tests -p 'test_tenant_admin_links.py' -v
```

Regeneração, sem tokens nem banco de produção:

```sh
node tools/build_postman_collection.mjs
python tools/build_branding_fixtures.py
python manage.py shell --no-imports \
  -c 'exec(open("tools/export_test_inventory.py").read())' \
  > docs/testing/django-test-inventory.json
```

## Evidência local desta entrega

Com Newman 6.2.1 e fixtures descartáveis: fluxo funcional executou 31 requests e 55 asserções sem falhas; envio real e GET externo de mídia ficaram desativados. O cenário com uploads e `allow_branding=false` passou com 30 requests/53 asserções, preservando nome, apresentação e cores. Modo padrão fez somente um GET e duas asserções. Host não aprovado produziu a falha esperada de proteção e nenhum POST: apenas o GET inicial foi enviado.

Esses resultados são de homologação local, não de produção. Não reutilize o convite consumido nem interprete itens pulados como cobertura executada. O inventário e os resultados completos de regressão estão resumidos em `../auditoria-bifurcacao.md`.
