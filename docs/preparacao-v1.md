# Preparação para a versão 1.0

Este documento reúne procedimentos para a branch candidata. A aprovação do lançamento depende das evidências das issues da milestone.

## E-mails e migração 0042

Antes do deploy, execute `python manage.py verificar_emails` com acesso ao banco de destino. O comando só lê dados e mostra IDs de contas duplicadas, sem imprimir endereços. Resolva cada conflito com aprovação do responsável; não apague nem una contas automaticamente. A migration interrompe o release se encontrar duplicatas normalizadas por caixa e espaços externos. E-mails vazios permanecem permitidos para contas técnicas.

## Limites de acesso

O limite inicial é de dez tentativas por conta e 60 por origem em 15 minutos, por fluxo de login ou cadastro. Cadastros por convite compartilham o limite de cadastro. Os contadores persistem no PostgreSQL; erro de banco interrompe o acesso temporariamente. Contas atrás do mesmo IP compartilham o limite por origem.

Por padrão, o endereço é obtido da conexão direta. Configure `AUTH_TRUSTED_PROXY_NETWORKS` somente com as redes dos proxies identificados e depois de impedir conexões diretas capazes de forjar `X-Forwarded-For`. Confirme a cadeia real antes do deploy. Monitore respostas 429 e 503 e ajuste a política conforme o uso.

## Avatar

`python manage.py limpar_avatars_orfaos` lista arquivos sem referência com mais de 24 horas. Após revisar o resultado, `--aplicar` remove os candidatos. Execute em armazenamento e ambiente identificados; a operação não substitui backups.

## Recuperação

Objetivos aprovados: backup diário, retenção de sete dias, RPO de 24 horas e RTO de duas horas. A lista de backups do PostgreSQL no Railway retornou vazia na consulta de 23/11/2026. Confirme eventuais backups externos, configure a rotina e restaure em banco separado para medir o tempo antes do lançamento.


## Ensaios da branch candidata

- PostgreSQL 18 com role `NOSUPERUSER NOBYPASSRLS` e Redis 7 descartáveis. O comando `pm_rls_status --strict` confirmou RLS habilitada e forçada em projetos e agenda.
- Dois processos simultâneos de migration concluíram com exclusão mútua via advisory lock. Um aplicou o schema e o outro confirmou ausência de versões pendentes.
- Backup restaurado em banco separado com uma conta, uma organização e cem projetos sintéticos. A restauração levou aproximadamente 0,73 segundo. As migrations 0042/0043 foram revertidas até 0041 e reaplicadas, preservando os cem projetos e a conta. Esse volume serve ao ensaio funcional. O tempo deve ser medido novamente com o volume real antes de assumir capacidade operacional.
- Para reverter esta atualização, interrompa os serviços que dependem do schema, preserve backup e restaure o código anterior. A reversão até 0041 remove o índice de e-mail e a tabela de contadores. Cadastros voltam a exigir controle até reaplicar a proteção. Valide o resultado em ambiente separado antes de executar no destino.
- Páginas de entrada global e CAMPPG retornaram HTTP 301 para HTTPS, HTTPS 200 e cookie CSRF com `Secure`. HSTS ausente na consulta. Falta validar cookie de sessão e identidade da origem atrás do proxy no ambiente candidato.
- Alertas externos aguardam webhook Discord e configuração de e-mail no Spring. Responsável pelo canal ainda precisa liberar acesso, conforme informado pela equipe.

## Ranking

A leitura usa ordenação SQL por relevância, atualização e ID. Em mil projetos sintéticos com 500 votos, cinco leituras de vinte IDs apresentaram mediana de 4 ms, uma consulta e pico de 14 KiB de alocações Python na última leitura. A leitura anterior apresentou 340 ms, duas consultas e 3.363 KiB, antes de um erro na saída do contexto do ensaio. As projeções Redis continuam disponíveis para reconstrução e integrações existentes.
