# Atualização do Contexto Mestre — Outubro de 2026

## 12. Direção atual do produto

O Palácio Mental deixa de ser pensado apenas como uma plataforma individual de projetos e passa a funcionar como um ecossistema híbrido: pessoas podem criar e explorar projetos autorais, enquanto organizações podem operar ambientes próprios para seus projetos, grupos e programas.

A proposta central permanece a mesma: preservar contexto, autoria e evolução para que projetos continuem compreensíveis, encontráveis e úteis. A mudança é estrutural: o Palácio Mental passa a atender tanto a continuidade individual quanto a continuidade institucional.

## 13. Ambiente institucional e multi-tenant

Cada organização poderá ter um ambiente isolado dentro da mesma plataforma, inicialmente por subdomínio, como `camppg.palaciomental.com.br`. O ambiente terá sua própria vitrine, projetos, membros, permissões e identidade visual.

A arquitetura usará banco compartilhado com isolamento por linhas. O PostgreSQL será a fonte oficial dos dados e cada registro institucional deverá estar vinculado à sua organização. Projetos institucionais não aparecerão na vitrine global; somente projetos explicitamente públicos poderão aparecer na vitrine da própria organização.

O modelo deve suportar projetos orientados por professor, coordenador ou mentor e projetos autônomos, criados por iniciativa dos próprios participantes. Usuário, membro institucional, gestor e beneficiário são papéis diferentes e não devem ser confundidos com o cliente pagante.

A primeira validação institucional será feita com o CAMPPG. O ambiente deve ser configurável para outras ONGs, instituições de ensino, programas e organizações privadas sem transformar cada novo cliente em um produto separado.

## 14. Modelo de negócio

O modelo é híbrido e ainda é uma hipótese em validação:

- entrada individual, com contas Free e Pro;
- entrada institucional, com ambientes para organizações;
- ONGs gratuitas ou subsidiadas quando houver capacidade e critérios definidos;
- instituições privadas e outros clientes pagando por governança, escala, implantação, suporte, integrações ou personalização;
- usuários, clientes, organizações parceiras e beneficiários tratados como grupos diferentes.

O Palácio Mental não deve depender de métricas predatórias nem de cobrança para liberar o valor essencial. A sustentabilidade deve vir de recursos de profundidade, volume, governança e operação institucional.

## 15. BMC revisado

O BMC passa a separar dois caminhos de aquisição e valor:

- **Individual:** autores e exploradores entram pelo produto, comunidade, apresentações, indicação e conteúdo.
- **Institucional:** organizações entram por pilotos, professores, coordenadores, programas, parceiros de impacto e venda consultiva.

Para indivíduos, o valor principal é começar, contextualizar, organizar, apresentar e continuar projetos. Para organizações, o valor é oferecer ambiente próprio, governança, permissões, acompanhamento de grupos, preservação institucional e relatórios.

As receitas potenciais são separadas entre conta Pro, planos institucionais, implantação, treinamento, suporte, integrações, automações e personalização. Os custos devem ser analisados em três camadas: operação individual, operação institucional e custos variáveis de infraestrutura e atendimento.

## 16. Arquitetura de planos

Os planos devem seguir o princípio de não pay-to-win: o pagamento não compra relevância artificial nem impede a criação básica.

A conta Free oferece as funções essenciais para criar, contextualizar, explorar e preservar projetos. A conta Pro pode ampliar potência, volume, organização, automações, integrações, coleções e recursos avançados de apresentação.

A conta institucional oferece ambiente organizacional, gestão de membros, permissões, grupos ou turmas, acompanhamento de projetos, identidade visual, suporte e governança. ONGs podem receber acesso gratuito ou subsidiado, sempre condicionado à capacidade operacional, critérios internos e revisão periódica.

PM Flow, PM VCS e automações avançadas pertencem à arquitetura futura do ecossistema. Não são pré-requisitos para o MVP institucional atual.

## 17. Ecossistema Palácio Mental

O ecossistema é organizado em camadas:

- **PM Plataforma:** núcleo atual de projetos, contexto, autoria, descoberta e continuidade;
- **camada institucional:** ambientes multi-tenant, membros, permissões, vitrines e governança;
- **PM Flow:** módulo futuro para fluxos, tarefas e acompanhamento operacional;
- **PM VCS:** módulo futuro para versões, histórico e evolução mais avançada.

Hoje, o núcleo da plataforma e a camada institucional são as prioridades. PM Flow e PM VCS são produtos ou módulos futuros, ainda sujeitos à validação. Nenhum componente futuro deve aumentar a complexidade do MVP antes de existir uma necessidade comprovada.

## 18. Redis e NoSQL no MVP

O PostgreSQL permanece responsável pela verdade do domínio: usuários, organizações, permissões, projetos, comentários, votos e marcos. Redis será usado de forma complementar para cache de tenant e branding, sessões aceleradas, rankings derivados e eventos transitórios.

A relevância dos projetos poderá usar Sorted Sets, com `ZINCRBY` e `ZRANGE`, mas o voto oficial permanece no PostgreSQL e o ranking deve ser reconstruível. A gamificação inicial deve destacar projetos úteis, explorados ou relevantes, sem criar competição predatória entre pessoas.

Comentários aninhados permanecem no PostgreSQL com `comentario_pai_id`. Redis Pub/Sub poderá avisar usuários conectados após o commit do comentário, mas não será usado como banco de comentários nem como fila garantida. A falha do Redis não pode causar perda de dados ou concessão indevida de acesso.

## 19. Estratégia de impacto

O Palácio Mental pode oferecer acesso gratuito ou subsidiado a ONGs para gerar impacto e casos de uso, mas não deve prometer gratuidade ilimitada. A política precisa considerar critérios de elegibilidade, consentimento para divulgação de casos, proteção de dados, capacidade de suporte e custo de infraestrutura.

O benefício para a ONG é ter uma estrutura acessível para organizar e preservar projetos. O benefício para o Palácio Mental é aprender com necessidades reais e demonstrar valor para organizações que podem pagar no futuro, sem transformar pessoas vulneráveis em recurso de marketing.

## 20. Sustentabilidade

A sustentabilidade deve acompanhar o uso real. Devem ser acompanhados custos fixos de hospedagem, domínio, banco, armazenamento, monitoramento e desenvolvimento; custos variáveis por organização, tráfego, suporte e implantação; e riscos de customizações que não possam ser reaproveitadas.

Planos institucionais precisam considerar margem, tempo de implantação, treinamento, suporte e limites operacionais. A personalização deve ocorrer preferencialmente por configuração, não por código exclusivo para cada cliente.

## 21. Hipóteses a validar

**Produto:** usuários entendem a proposta; Meu Espaço gera valor; a vitrine ajuda a descobrir projetos; o PM VCS será útil; o PM Flow reduzirá trabalho; organizações precisam de ambientes próprios.

**Negócio:** pessoas pagarão por maior profundidade; organizações pagarão por governança; ONGs gratuitas ou subsidiadas gerarão aprendizado sustentável; implantação e suporte serão economicamente viáveis; o modelo poderá se replicar para outros segmentos.

**Operação:** a equipe conseguirá apoiar organizações; o núcleo compartilhado atenderá diferentes contextos; a personalização por configuração será suficiente; os custos crescerão de forma controlada.

Todas essas afirmações são hipóteses, não fatos comprovados. O próximo ciclo deve priorizar uso real, entrevistas, pilotos, retenção, custo de atendimento e evidências de valor antes de ampliar o escopo do ecossistema.
