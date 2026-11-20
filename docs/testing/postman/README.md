# Jornadas do MVP no Postman

Documentação executável do que o MVP faz, contra formulários reais do Django. Cada pasta responde a uma pergunta; cada negativa declara quem pede, onde e qual resposta a regra produz. Não substitui a suíte Django nem comprova RLS em SQL.

| Pasta | Pergunta | Identidade |
|---|---|---|
| 00 · Pré-condições | O ambiente responde e o tenant A é o esperado? | Nenhuma |
| 10 · Público e pessoal | Autor cria projeto privado, salva contexto e a releitura confirma? | Conta pessoal, host global |
| 20 · Organização | Membro cria projeto vinculado a turma e orientador, e não acessa a gestão? | Membro do tenant A |
| 30 · Privacidade | Tenant inexistente, host errado, conta sem afiliação e outro tenant recebem a negativa prevista? | Conta pessoal e membro do tenant B |

Persistência é comprovada pelo título do projeto e pelo marco automático "Contexto atualizado" na releitura, não apenas por status HTTP.

## Resultados esperados nas negativas

| Pedido | Resposta |
|---|---|
| Subdomínio sem organização | 404 |
| Projeto institucional pelo host global | 404 |
| Conta autenticada sem afiliação no tenant A (login e projeto) | 403 |
| Membro do tenant B pedindo projeto do tenant A | 404 |
| Membro pedindo `/gestao/identidade/` | 403 |

## Preparação (uma vez, fora da coleção)

Use somente tenants e contas de teste. As contas não têm acesso ao Admin interno.

1. Tenants A e B de teste. Domínios ativos e cadastrados.
2. Em A: Gestor cria programa publicado e turma ativa com professor responsável (afiliação ativa de Professor).
3. Em A: Membro de teste entra na turma (política aberta, ou solicitação aprovada). O grupo, se usado, é criado por esse Membro, porque só Membro ativo da turma cria grupo.
4. Em B: Membro de teste com afiliação ativa.
5. Conta pessoal global sem afiliação em A nem em B.

Preencha em cópia privada do environment: `pessoal_*`, `membro_*`, `membro_b_*` (apenas se `allow_isolation=true`), `turma_id`, `orientador_id` (ID do usuário professor), `grupo_id` (opcional) e `turma_nome` (opcional, confirma o vínculo no detalhe).

## Segurança

- `allow_writes` vem `false`. Sem ele, todo POST é pulado e a execução faz somente GETs.
- Com `allow_writes=true`, cada POST só sai se o host estiver em `approved_write_hosts` (lista separada por vírgula, host exato). Fora da lista a execução para antes do POST.
- Cada execução cria no máximo um projeto privado pessoal e um institucional, com título `QA-PM ... <timestamp>`. Nada é excluído automaticamente.
- Senhas são `secret` no environment. Não publique environments preenchidos, cookies, relatórios com corpos de autenticação.
- Itens pulados não são aprovados. A execução sem sessão ou sem ID de projeto pula os dependentes.

## Executar

```sh
newman run docs/testing/postman/palacio-mental.postman_collection.json \
  -e /caminho/privado/pm-qa.json
```

Não ative redirects automáticos: os itens os desligam para que um POST inválido que reabre o formulário (200) não pareça sucesso. Execute a coleção inteira em ordem; o Runner interrompe quando um pré-requisito essencial falha.

## O que fica fora desta versão

Descoberta de projeto público (exige projeto público sintético fixo), comentário e marco de outro autor, participação em turma e grupo, convites, identidade visual e mídia. Entram quando houver regra e massa de teste definidas. Convite de grupo: vale a regra do código (somente Membro ativo do grupo emite).

## Verificação local

```sh
node tools/build_postman_collection.mjs
node --test tools/test_postman_guards.mjs
python manage.py test tools.postman_contract
```
