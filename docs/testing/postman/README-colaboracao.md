# Colaboração entre alunos no CAMPPG

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
