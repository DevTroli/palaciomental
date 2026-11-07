# Arquitetura e isolamento

A aplicação usa banco PostgreSQL compartilhado. O middleware resolve uma organização ativa pelo hostname cadastrado. Afiliação ativa e autorização por papel são verificadas no servidor. O domínio global contém projetos pessoais, com `organizacao_id = NULL`.

## Duas barreiras

1. Querysets e formulários filtram organização, usuário e visibilidade.
2. PostgreSQL força RLS em projetos e eventos da agenda, inclusive para a role proprietária das tabelas.

| Contexto RLS | Projetos | Agenda |
|---|---|---|
| `tenant` | Somente a organização corrente | Somente a organização corrente |
| `global` | Somente projetos pessoais | Nenhum evento |
| `system` | Acesso interno explicitamente autorizado | Acesso interno explicitamente autorizado |
| `deny` ou ausente | Nenhuma linha | Nenhuma linha |

A RLS por tenant não substitui autorização por proprietário ou destinatário. Tabelas filhas de projetos continuam dependendo dos filtros da aplicação. Usuários, perfis e sessões são globais.

O contexto é aplicado e restaurado pelo middleware. Comandos e jobs ficam em `deny` por padrão e precisam de escopo explícito. Roles superusuárias ou com BYPASSRLS ignoram essa proteção; verifique com `python manage.py pm_rls_status --strict`.

## Projeções e mídia

Redis é derivado: ranking é revalidado no SQL antes da exibição; sessões permanecem no banco quando o cache falha. Redis não concede autorização. Rebuild completo publica o escopo correspondente, sem misturar organizações.

Logo/capa são públicas, normalizadas e têm chaves novas por upload. Credenciais de storage ficam no ambiente. Dados privados não devem ser enviados ao bucket público de identidade.

## Compatibilidade

`plataforma` ainda mantém o app label histórico `listaEspera`, usado por tabelas e migrations anteriores. Não renomear esse label isoladamente. A agenda pertence à plataforma, usa `plataforma_eventocalendario` e não depende de app ou migrations CAMP.
