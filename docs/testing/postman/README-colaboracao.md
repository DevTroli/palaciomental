# CAMPPG - Colaboração

A coleção testa um fluxo institucional entre duas contas de aluno: Troli publica
um projeto, Carvalho comenta, reconhece relevância e pede para participar;
Troli aceita e remove o projeto criado. Gestores não participam dessa jornada.

## Environment

Gere os arquivos com `node tools/build_postman_collaboration.mjs`. Na cópia local
do environment, configure:

- `tenant_a_base=https://camppg.palaciomental.com.br`
- `allow_writes=true`
- `approved_write_hosts=camppg.palaciomental.com.br`
- `autor_username` e `autor_password`: conta do aluno autor (Troli)
- `colab_username` e `colab_password`: segundo aluno (Carvalho)
- `colab_display_name`: nome exibido de Carvalho na equipe

As duas contas precisam de afiliação ativa no CAMPPG. Senhas ficam locais e
sensíveis. Não compartilhe nem versione o environment preenchido.

## Execução

Execute a coleção inteira no Runner, uma iteração e atraso de 300 ms. Não rode
pastas isoladas: as etapas usam IDs e sessão criados nas pastas anteriores. A
coleção cria um projeto institucional público durante o teste e o remove no fim.
Uma interrupção pode deixar registros e notificações; confira apenas os IDs da
rodada antes de qualquer limpeza manual.

O teste verifica se ambos entram no tenant, se o autor pode publicar buscando
colaboradores, se o segundo aluno pode interagir, se o pedido fica associado à
conta certa e se o autor consegue aceitar e excluir o projeto.

Validada com Newman: 21 requisições enviadas e 37 asserções aprovadas. Os dois
passos de reautenticação do encerramento são dispensados quando o autor já está
autenticado. Ambos os logins esperam `/`. A criação usa `tipo_projeto=autonomo`,
pois a turma não é obrigatória nesta jornada.


Versão sincronizada no workspace PalacioMental como **CAMPPG - Colaboração**.
O modelo **CAMP-PG · Colaboração** foi publicado com senhas vazias: preencha
somente os valores locais. Usa `tenant_a_base`; `global_base` não é mais usado.

[Execução validada no Postman](https://go.postman.co/workspace/93cde965-fda5-4c07-b79b-7966778b859e/run/30871897-f23328f0-a15c-4dbd-bb24-ebda0a95a1a5)
