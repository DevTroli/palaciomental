# PM-08: navegação de projetos entre ambientes

## Problema e evidência

A homologação em produção mostrou links da home institucional descritos como
“fora deste tenant”, mas apontando para o próprio subdomínio. O perfil contextual
listava projetos institucionais com linguagem de portfólio pessoal, e o cabeçalho
das telas de projeto usava a marca global.

Não foi reproduzido erro na criação ou reabertura legítima do projeto 12 no tenant
A. Os 404 reproduzidos foram de isolamento: o projeto de A no domínio global ou
em B, e o projeto pessoal no host de A. Essas respostas permanecem obrigatórias.

O código também gravava notificações de colaboração com URL relativa, que podia
ser aberta no host de outra organização. A correção se aplica às notificações
novas; registros históricos não são reescritos.

## Decisões implementadas

- Home: ações distintas para criar projeto institucional, consultar projetos
  próprios neste ambiente e abrir o espaço pessoal no domínio principal.
- Perfil contextual: inclui os privados do autor e usa rótulos institucionais;
  não passa a listar projetos de outros ambientes.
- Cabeçalho das telas compartilhadas: identidade do tenant, navegação contextual
  e marca P.M. somente no rodapé. A navegação global permanece separada.
- Voltar do detalhe do próprio projeto leva ao perfil contextual, que inclui
  privados, e não à vitrine exclusivamente pública.
- Notificações novas: domínio ativo cadastrado da organização do projeto,
  priorizando o principal; não usa Host arbitrário recebido do cliente.
- Sem migrações de banco, sem alteração de RLS ou de permissões.

## Validação

O arquivo `plataforma/tests/institucional/test_fluxo_projetos.py` acrescenta
oito testes: links da home, criação/contexto/reabertura/edição, privados no perfil,
identidade nas seis telas compartilhadas, preservação do global, URL canônica,
notificações de solicitação/decisão e bloqueio de outro tenant.

Um teste antigo teve sua expectativa de rótulo atualizada de “Meu Espaço” para os
dois percursos explícitos. As demais verificações de isolamento foram preservadas.

## Limites e próximos passos

- Revisar PR e CI antes de merge/deploy; repetir o percurso no Comet após deploy.
- Notificações históricas relativas continuam pendentes de eventual migração.
- Não inclui testes de envio de e-mail nem homologação de todos os papéis.
- Não remove o app label `listaEspera`: essa alteração exige um plano próprio
  para histórico de migrações, content types, permissões, tabelas e RLS.
- Com a role de runtime separada em produção, futuras tabelas também precisarão
  receber privilégios de dados apropriados antes de uso pelo runtime.
