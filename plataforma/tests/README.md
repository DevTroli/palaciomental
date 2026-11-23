# Testes do Palácio Mental

Execute os comandos na raiz do projeto, com o Compose ativo.

| O que verificar | Comando |
|---|---|
| Aplicação inteira | `docker compose exec django python manage.py test --noinput` |
| Fluxos institucionais | `docker compose exec django python manage.py test plataforma.tests.institucional` |
| Isolamento e RLS | `docker compose exec django python manage.py test plataforma.tests.seguranca` |
| Guardião | `docker compose exec django python manage.py test plataforma.tests.test_guardiao_envio plataforma.tests.test_guardiao_consulta plataforma.tests.test_guardiao_ameacas_formulario plataforma.tests.test_guardiao_alertas plataforma.tests.test_guardiao_rejeicoes plataforma.tests.test_guardiao_tenants` |
| Inicialização e automação | `docker compose exec django python -m unittest discover -s scripts/tests` |

Para uma correção pontual, passe o módulo afetado ao `manage.py test`. Antes do PR, execute a suíte completa. O CI usa PostgreSQL com role comum e Redis real. Testes de RLS, concorrência e Redis exigem esses serviços para comprovar a integração. Configure `TEST_REDIS_URL` em banco Redis descartável para ativar seus testes.

A base institucional usa o hasher rápido do Django para as contas fictícias. Login, troca de senha e sessão continuam sendo exercitados pelos fluxos reais dos testes. A configuração de produção continua definida em `setup/settings.py`.

## Onde encontrar

| Pasta | Responsabilidade |
|---|---|
| `institucional/` | Acesso, convites, programas, turmas, grupos, projetos e agenda. |
| `seguranca/` | Isolamento entre organizações, RLS, CSRF e redirecionamentos. |
| `administracao/` | Admin técnico e acesso aos ambientes. |
| `comunidade/` e `projetos/` | Projetos, comentários, relevância e colaboração. |
| Arquivos `test_guardiao_*` | Fila, resultados, ameaças, notificações e recuperação. |
| `core/` | Ranking, projeções Redis e entrada pública. |
| `status_api/src/test/` | Motor Spring, monitoramento, incidentes e Flyway. |

A suíte Spring possui execução própria no CI e instruções no [guia da API](../../status_api/README.md). As jornadas HTTP ficam no [Postman](../../postman/README.md).

## Manter enxuto

Adicione teste para uma regra nova, um limite de autorização ou uma regressão específica. Reutilize o cenário existente quando ele já cobre a mesma decisão. Casos de entrada semelhantes podem usar `subTest`, desde que a falha identifique o caso. Agrupar funções sem reduzir preparação ou ações repetidas apenas muda a contagem.

O refinamento da v1.0 reduziu a suíte Django de 413 para 378 cenários e retirou 35 testes sobrepostos ou de implementação. Foram removidas cópias da home, contratos de strings CSS/HTML, persistência trivial da quarentena e verificações antigas de ordenação Redis substituídas por SQL. Permanecem os testes de envio real de convites, papéis, visibilidade, contraste numérico, RLS, recuperação da fila, concorrência e falhas externas. A revisão não encontrou repetição equivalente que justificasse corte no motor Spring.
