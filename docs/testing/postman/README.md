# Postman: documentação executável do MVP

Duas coleções geradas por `node tools/build_postman_collection.mjs` e `node tools/build_postman_collaboration.mjs`. Falam com formulários reais do Django e não substituem a suíte Django nem comprovam RLS em SQL.

## Jornadas do MVP (`palacio-mental`)

| Pasta | O que comprova |
|---|---|
| 10 · Público e pessoal | Autor cria projeto privado, salva contexto e a releitura mostra título e marco "Contexto atualizado". |
| 20 · Organização e privacidade | Membro cria projeto vinculado a turma e orientador. Membro recebe 403 na gestão. Projeto institucional dá 404 no host global e no tenant B. Tenant inexistente dá 404. Conta sem afiliação dá 403. |

Os itens do tenant B (20.10 a 20.14) só rodam com `allow_isolation=true`. Cada pasta exclui no fim o projeto que criou, pelo ID devolvido na criação.

## Colaboração pública (`palacio-mental-colaboracao`)

Execute só quando quiser verificar este fluxo. Duas contas pessoais: autor publica projeto público, não comenta nem vota no próprio projeto (403); o colaborador acha o projeto na busca, comenta, reconhece a relevância e pede para colaborar; o autor aceita e o colaborador passa a integrar o projeto.

O projeto de teste fica público e visível na lista do site durante a execução (segundos). Se algum passo falhar, a coleção salta para o encerramento, refaz o login do autor e o exclui. Se a execução for interrompida à força, remova-o pelo título `QA-PM-colab`.

## Preparação (fora da coleção)

1. Tenants A e B de teste, com domínios ativos.
2. Em A: Gestor cria programa publicado e turma ativa com professor responsável. O Membro entra na turma. O grupo, se usado, é criado por esse Membro (só Membro ativo da turma cria grupo).
3. Em B: Membro com afiliação ativa.
4. Contas pessoais sem afiliação em A nem em B: uma para as jornadas e a de colaboração (autor), outra para o colaborador.

Preencha uma cópia privada de cada environment. Senhas são `secret`. Não publique environments preenchidos, cookies nem relatórios com corpos de autenticação.

## Segurança

- `allow_writes=false` por padrão: todo POST é pulado.
- Com `allow_writes=true`, cada POST só sai para hosts em `approved_write_hosts` (lista separada por vírgula); fora dela a execução para antes do POST.
- Itens pulados não são aprovados.
- Se uma pasta falhar, ela salta para o próprio encerramento. Se parar à força, os projetos `QA-PM-...` ficam e devem ser removidos manualmente.

## Executar e verificar

```sh
newman run docs/testing/postman/palacio-mental.postman_collection.json -e /caminho/privado/pm.json
node tools/build_postman_collection.mjs && node tools/build_postman_collaboration.mjs
node --test tools/test_postman_guards.mjs
python manage.py test tools.postman_contract
```

Não ative redirects automáticos: os itens os desligam para que um POST inválido que reabre o formulário (200) não pareça sucesso.

## Ainda sem prova

Contador de relevância, rejeição de pedido, marco de colaborador, convites, identidade visual e mídia. Convite de grupo: vale a regra do código (somente Membro ativo do grupo emite).
