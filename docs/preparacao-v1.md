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
