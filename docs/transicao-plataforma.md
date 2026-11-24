# Transição para plataforma

O app, as URLs do Django Admin e as tabelas passam a usar `plataforma`.
Projetos, usuários, organizações e permissões mantêm seus IDs e relacionamentos.

| Ambiente | Procedimento |
|---|---|
| Banco novo | Instalação normal; as migrations já usam o novo identificador. |
| Banco existente | Transição explícita antes das migrations, com backup e serviços parados. |

## Banco existente

1. Confirme o banco de destino e um backup restaurável. Ensaie primeiro em uma cópia.
2. Interrompa os processos Django web, worker e tarefas agendadas que usam esse banco. Código antigo não pode rodar após a renomeação.
3. Com o **código novo** e as **credenciais de migration**, execute:

   ```bash
   python manage.py transicionar_plataforma
   python manage.py transicionar_plataforma --aplicar
   python manage.py migrar_com_bloqueio --noinput
   ```

4. Com a role comum, confira `python manage.py pm_rls_status --strict`.
5. Inicie web, worker e tarefas com a mesma versão. Verifique login, admin, projetos e isolamento entre organizações.

O primeiro comando apenas confere conflitos e informa quantos objetos serão renomeados.
A aplicação é transacional e usa o mesmo lock das migrations. Conflitos interrompem a operação;
não há cópia, exclusão ou fusão de registros. Execute novamente apenas após entender o erro.

**Retorno:** se a transição falhar, o PostgreSQL desfaz suas alterações. Se ela concluir,
voltar apenas o código antigo não funciona. Mantenha os serviços parados e restaure o backup
junto com a versão anterior, antes de reabrir o acesso. Não aceite novas escritas nesse intervalo.

## Histórico e compatibilidade

Os arquivos de migrations mantêm seus nomes e operações, com referências ao novo app.
O comando atualiza o identificador no histórico aplicado, evitando executar migrations antigas novamente.
Content types mantêm seus IDs, preservando permissões e registros do admin. Tabelas, constraints, índices e sequências
são renomeados; políticas RLS, privilégios e vínculos permanecem nos mesmos objetos PostgreSQL.

O identificador antigo fica somente no adaptador de transição. As migrations históricas de criação e
remoção da lista de espera permanecem para representar a evolução do banco. Elas não disponibilizam
cadastro de espera nem recuperam contatos apagados. URLs antigas do admin deixam de funcionar;
atualize favoritos para `/admin/plataforma/`.

A API Spring e o schema `guardiao` não são alterados. Os contatos da antiga lista só podem ser
recuperados de uma exportação ou backup anterior à remoção da tabela.
