# Palácio Mental — Contexto completo para Project de IA

## Finalidade deste documento

Este arquivo traduz o Contexto Mestre do Palácio Mental para uso em um Project de IA. Ele não é apenas um resumo técnico. Seu objetivo é explicar o Palácio Mental como conceito, produto, ecossistema, iniciativa de impacto, plataforma institucional e projeto em desenvolvimento.

O assistente deve usar este documento para compreender a visão ampla do P.M. e usar o repositório, o README, as migrations e os testes para verificar o estado real da implementação.

Este documento preserva decisões, hipóteses e tensões ainda abertas. Elas não devem ser tratadas como se fossem todas definitivas.

## Regra de leitura das fontes

Quando houver conflito, seguir esta ordem:

1. código, migrations e testes atuais para saber o que existe;
2. decisões mais recentes aprovadas pelo Product Owner;
3. Contexto Mestre para visão, propósito, problema, proposta e hipóteses;
4. README e documentação técnica para arquitetura e operação;
5. issues do GitHub para escopo de execução;
6. conversas antigas apenas como histórico.

O assistente deve dizer quando uma definição do Contexto Mestre ainda não corresponde ao código ou quando existem duas versões estratégicas em discussão.

## 1. O que é o Palácio Mental

O Palácio Mental é um ecossistema para contexto, evolução e conexão de projetos. Seu propósito é ajudar criações, iniciativas e conhecimentos a permanecerem compreensíveis, encontráveis, aproveitáveis e retomáveis ao longo do tempo.

O P.M. não é apenas um gerenciador de tarefas, um armazenamento de arquivos, uma rede social, um repositório Git ou uma ferramenta de comunicação. Ele adiciona uma camada de contexto, autoria, decisões, trajetória, colaboração, descoberta e continuidade ao redor dos projetos.

Slogan:

> **Ideias para além do rascunho.**

Diferencial conceitual:

> Outras ferramentas ajudam a construir. O Palácio Mental ajuda a continuar.

O Palácio Mental não guarda somente o que foi feito. Ele busca preservar como e por que foi feito.

Princípio de experiência:

> Entrada simples, profundidade progressiva.

O usuário deve conseguir começar com poucas informações e aprofundar o contexto conforme a iniciativa evolui.

## 2. Problema central: o cemitério de projetos

O problema central investigado é a perda de contexto que transforma criações relevantes em projetos descontinuados.

O “cemitério de projetos” representa o conjunto de criações que continuam armazenadas, mas deixam de possuir sentido suficiente para gerar valor. Um projeto pode chegar a esse estado sem ter falhado. Pode ter sido concluído, pausado, interrompido, esquecido ou deixado de ser prioridade.

Quando isso acontece, arquivos podem continuar existindo, mas o motivo do projeto, as decisões, a autoria, os aprendizados, as responsabilidades e os caminhos de continuidade se perdem.

Um projeto tende a perder continuidade quando:

- o contexto fica espalhado entre várias ferramentas;
- decisões permanecem em conversas ou na memória de uma pessoa;
- um grupo se desfaz;
- responsáveis ou prioridades mudam;
- o projeto é entregue sem registrar seu processo;
- faltam colaboradores que compreendam sua direção;
- o autor não consegue retomar o trabalho depois de uma pausa.

A dificuldade para começar, encontrar referências e localizar colaboradores é uma dimensão complementar. O foco central continua sendo impedir que um projeto relevante se torne incompreensível e esquecido.

## 3. How Might We

Pergunta central:

> Como poderíamos evitar que projetos com potencial percam seu sentido, sejam esquecidos ou deixem de ser aproveitados quando deixam de ser prioridade?

O P.M. não promete concluir todos os projetos, financiar iniciativas ou garantir impacto. Ele busca manter as condições para que uma criação tenha sobrevida como referência, aprendizado, inspiração, legado, ponto de partida ou projeto retomável.

## 4. Proposta de valor

O Palácio Mental ajuda pessoas e organizações a manterem o sentido de seus projetos antes, durante e depois da execução.

O núcleo do valor não é armazenar um projeto. É preservar as condições para que ele continue fazendo sentido.

O P.M. organiza em torno do projeto:

- por que ele existe;
- quem participou ou participa;
- o que foi feito;
- como decisões foram tomadas;
- quais aprendizados surgiram;
- quais recursos e links estão relacionados;
- quais são os próximos passos;
- como a iniciativa pode ser encontrada, continuada ou reutilizada.

Fluxo de valor:

```text
entrada simples
→ contexto progressivo
→ autoria e colaboração
→ evolução registrada
→ descoberta e acompanhamento
→ reutilização, continuidade ou legado
```

Para uma pessoa, o P.M. reduz a perda do significado e da trajetória de uma criação.

Para uma organização, o P.M. preserva conhecimento institucional, facilita o acompanhamento de iniciativas e reduz a dependência de arquivos dispersos ou da memória de poucas pessoas.

Limites da proposta:

- não garante conclusão;
- não garante financiamento;
- não garante retomada;
- não substitui professores, mentores, gestores ou equipes;
- não substitui ferramentas especializadas de execução;
- não deve ser tratado como sistema contábil, prontuário, canal de atendimento ou gestor completo de uma organização.

## 5. Ecossistema P.M.

O ecossistema foi pensado em camadas complementares.

### P.M. Plataforma

É o núcleo atual. Organiza projetos, contexto, autoria, pessoas, links, marcos, colaboração, descoberta e trajetória.

A Plataforma não pretende substituir GitHub, Drive, Docs, Figma, Trello, WhatsApp ou outras ferramentas. Ela conecta e contextualiza informações que continuam podendo viver em serviços externos.

### Ambiente institucional

É a camada multi-tenant da Plataforma. Permite que uma organização possua um ambiente próprio, com identidade, usuários, papéis, programas, turmas, grupos, projetos e vitrine institucional.

Projetos institucionais permanecem separados de projetos pessoais e não entram automaticamente na vitrine global do P.M.

### PM VCS

É uma hipótese de produto standalone do ecossistema. Sua ideia é abstrair o Git para salvar, compreender, comparar, recuperar e compartilhar versões de projetos de forma mais acessível.

O PM VCS não deve ser tratado como implementado no MVP atual. Ele é uma direção futura e precisa ser validado antes de receber desenvolvimento amplo.

### PM Flow

É uma hipótese de camada de integrações e automações. Conecta eventos e serviços externos à Plataforma e, no futuro, ao PM VCS.

O PM Flow não deve decidir sozinho autoria, permissão ou publicação. Essas decisões continuam sob controle do sistema e das pessoas autorizadas.

### Relação entre as camadas

```text
P.M. Plataforma = contexto, autoria e continuidade
Ambiente institucional = governança e uso organizacional
PM VCS = versões e histórico técnico, hipótese futura
PM Flow = integrações e automações, hipótese futura
```

## 6. Públicos e stakeholders

### Públicos centrais

- autores e equipes: criam e preservam contexto;
- participantes: exploram e compreendem projetos;
- colaboradores: identificam onde e como contribuir;
- professores, facilitadores e instituições: acompanham e preservam projetos entre ciclos;
- organizações: precisam de memória, governança e continuidade;
- beneficiários: recebem conhecimento, soluções ou apoio produzido pelas iniciativas.

### Stakeholders

- organização: pode contratar, financiar, operar ou manter o ambiente institucional;
- decisores institucionais: avaliam, aprovam e priorizam adoção;
- gestores: administram pessoas, permissões, programas, grupos e projetos;
- professores/facilitadores: acompanham, orientam e apoiam participantes;
- autores e participantes: criam, desenvolvem e registram projetos;
- colaboradores e voluntários: contribuem dentro de um escopo definido;
- apoiadores e financiadores: acompanham evidências sem receber acesso automático a dados pessoais;
- beneficiários: recebem os resultados ou o valor social das iniciativas;
- equipe P.M.: desenvolve, opera, documenta, protege e melhora a plataforma.

Esses grupos não têm o mesmo papel, nem o mesmo interesse, influência ou nível de acesso.

## 7. ODS e impacto social

A conexão prioritária é com a ODS 4 — Educação de qualidade, principalmente as metas 4.4 e 4.7.

A relação não deve ser apresentada como se o P.M. produzisse sozinho formação profissional ou impacto social. A contribuição está em apoiar aprendizagem baseada em projetos, organização da experiência, colaboração, registro de aprendizados, reflexão e continuidade.

Ciclo de contribuição:

```text
projeto → prática → registro → reflexão → colaboração → continuidade
```

A relação com a meta 4.4 ocorre porque projetos permitem praticar, registrar decisões, desenvolver soluções, colaborar e apresentar evidências de competências técnicas, profissionais e empreendedoras.

A relação com a meta 4.7 ocorre porque projetos de sustentabilidade, cidadania, direitos humanos, cultura, inclusão e desenvolvimento comunitário podem ser organizados, compartilhados e continuados.

Limite: o P.M. cria condições de organização e memória. Não garante que um projeto produzirá impacto social, empregabilidade ou transformação educacional.

Indicadores possíveis:

- projetos educacionais ou sociais contextualizados;
- participantes, professores e facilitadores envolvidos;
- colaborações qualificadas;
- projetos descobertos, reutilizados ou continuados;
- iniciativas relacionadas à sustentabilidade, inclusão ou desenvolvimento comunitário;
- percepção de organização, aprendizagem e continuidade;
- redução do tempo para integrar novos participantes;
- histórico consultado depois da mudança de responsável.

## 8. Duas camadas estratégicas que precisam ser preservadas

O Contexto Mestre reúne duas formulações estratégicas relacionadas, mas não idênticas.

### 8.1 Formulação original: ecossistema sustentável

A formulação original considera um modelo híbrido:

- usuários individuais com conta Free;
- usuários individuais com conta Pro;
- ambientes institucionais para organizações;
- planos institucionais pagos para instituições que possam pagar;
- acesso gratuito ou subsidiado para ONGs, conforme capacidade e critérios;
- implantação, suporte, integrações e personalização como possíveis fontes de sustentabilidade.

Nessa formulação, o objetivo é criar uma startup de impacto financeiramente saudável, sem pay-to-win, sem vender relevância, sem vender exposição e sem transformar dados pessoais em mercadoria.

O BMC original é uma hipótese de negócio, não uma receita comprovada. Ainda precisam ser validados disposição a pagar, preço, formato contratual, custo de suporte, margem e recurso mais valioso para organizações.

### 8.2 Formulação de extensão e terceiro setor

A parte adaptada para o projeto de extensão reposiciona o P.M. como uma iniciativa sem fins lucrativos de apoio a organizações da sociedade civil, coletivos e programas comunitários.

Nessa formulação:

- o acesso essencial não deve ser cobrado dos beneficiários;
- dados pessoais não são vendidos;
- exposição não é uma mercadoria;
- sustentabilidade pode vir de bolsas, extensão, editais, doações, fundos de apoio, parcerias educacionais, apoio técnico e colaboração voluntária;
- o sucesso é medido por continuidade, colaboração, acessibilidade, governança e aprendizagem;
- a plataforma deve preservar autonomia das organizações e consentimento dos participantes.

Essa formulação não deve ser apagada em favor da anterior. Ela representa uma direção social e acadêmica que pode definir o ciclo atual do projeto.

### Regra para o assistente

Nunca afirmar que o modelo financeiro está definitivamente decidido. Ao discutir planos ou receita, perguntar se a análise se refere a:

1. hipótese de startup de impacto sustentável;
2. operação sem fins lucrativos do projeto de extensão;
3. possível combinação futura das duas camadas.

## 9. Arquitetura de planos como hipótese

A arquitetura conceitual discutida contém:

### Free

- criação de projetos;
- contexto básico;
- exploração;
- publicação conforme visibilidade;
- links manuais;
- automações básicas.

Limites exemplificativos ainda sujeitos à validação: quantidade de projetos, projetos ativos, links e automações.

### Pro

- tudo do Free;
- maior profundidade de contexto;
- Meu Espaço avançado;
- integrações e automações completas;
- possível acesso futuro ao PM VCS e PM Flow.

Os limites e preços ainda não são definitivos.

### Institucional

- ambiente próprio;
- identidade visual;
- membros;
- programas, turmas e grupos;
- permissões e governança;
- vitrine institucional;
- relatórios;
- domínio institucional;
- suporte e implantação;
- integrações e automações conforme o pacote.

### ONGs

Podem receber acesso gratuito ou subsidiado, mas isso não deve ser tratado como gratuidade ilimitada. É necessário considerar critérios, capacidade operacional, suporte, proteção de dados, custo por organização e revisão periódica.

Princípio de preço:

> Não monetizar relevância, votos, exposição, privacidade ou acesso essencial.

## 10. Sustentabilidade e impacto

A sustentabilidade financeira ainda é uma hipótese. A organização deve distinguir:

### Custos fixos

- infraestrutura mínima;
- domínio;
- ferramentas essenciais;
- monitoramento;
- reserva operacional;
- capacidade mínima da equipe.

### Custos variáveis

- CPU e memória;
- banco e Redis;
- armazenamento e tráfego;
- usuários ativos;
- organizações e tenants;
- suporte;
- implantação;
- integrações;
- customizações.

O custo está mais relacionado ao uso ativo, volume de dados, número de organizações e nível de suporte do que ao simples número de contas cadastradas.

A fórmula econômica de referência é:

```text
receita recorrente > custos fixos alocados
                    + custos variáveis
                    + suporte
                    + implantação amortizada
                    + margem de segurança
```

As premissas financeiras do Contexto Mestre são hipóteses de planejamento. Devem ser substituídas por faturas, consumo medido, horas da equipe e evidências de disposição a pagar.

## 11. Funcionamento do produto atual

O fluxo básico do MVP é:

```text
criar → adicionar contexto → definir visibilidade
→ publicar ou manter restrito → explorar
→ interagir → registrar evolução
```

A entrada deve ser curta. O contexto pode incluir direção, links, marcos, autoria, decisões, responsáveis, aprendizados e próximos passos.

Marcos registram mudanças importantes. Eles não substituem commits, arquivos, histórico técnico ou ferramentas externas de versionamento.

## 12. Ambiente institucional

Projetos pessoais pertencem ao usuário. Quando públicos, podem aparecer na vitrine global.

Projetos institucionais pertencem ao ambiente de uma organização, preservam a autoria do usuário e aparecem somente na vitrine institucional da própria organização.

Uma organização pode ser:

- ONG;
- escola;
- faculdade;
- empresa;
- laboratório;
- programa;
- coletivo;
- outra instituição que precise acompanhar projetos sem perder autoria, contexto e continuidade.

A arquitetura atual usa banco compartilhado com isolamento por linhas e resolução por subdomínio, como:

```text
camppg.palaciomental.com.br
```

A identidade visual do tenant deve fazer a pessoa reconhecer que está no ambiente da organização, sem apagar a linguagem base do P.M.

Fluxo institucional:

```text
organização → programa → turma → grupo → projeto
→ contexto → evolução → vitrine institucional
```

Um projeto pode ser orientado, autônomo institucional ou autoral pessoal. Esses três tipos não devem ser confundidos.

## 13. Papéis e permissões

Papéis institucionais atuais do código:

- proprietário: responsabilidade geral pelo tenant;
- gestor: administração operacional;
- professor: orientação e acompanhamento;
- membro/aluno: participação conforme elegibilidade.

O Contexto Mestre também utiliza os termos mentor, facilitador, orientador e observador. Esses termos podem ser conceituais ou futuros. Não presumir que sejam papéis técnicos já implementados.

A implementação atual prioriza Professor como papel de orientação. Mentor pode ser tratado como função conceitual até que exista uma decisão específica para virar papel de sistema.

Papéis de projeto incluem proprietário e colaboradores, com permissões específicas para contexto, comentários, marcos e edição.

## 14. MVP e estado de implementação

O MVP conceitual já cobre:

- conta, autenticação e perfil;
- criação, edição e página de projeto;
- autoria e integrantes;
- visibilidade;
- busca e descoberta;
- comentários e respostas;
- marcos de evolução;
- relevância;
- colaboração;
- caixa de entrada;
- ambientes institucionais em desenvolvimento;
- identidade e navegação institucional;
- programas, turmas, grupos e projetos institucionais.

O status exato deve ser verificado no código, nos testes e nas issues. Este documento não deve ser usado para afirmar que PM VCS, PM Flow, ranking Redis ou todas as funções de extensão já estão implementadas.

## 15. Arquitetura de dados e tecnologia

PostgreSQL mantém os dados oficiais:

- usuários e perfis;
- organizações e domínios;
- afiliações e permissões;
- programas, turmas e grupos;
- projetos e autoria;
- links e contexto;
- comentários e respostas;
- votos de relevância;
- marcos;
- solicitações;
- notificações persistentes;
- planos e assinaturas quando implementados.

Redis pode ser usado como camada operacional para:

- sessões;
- cache de organização e identidade;
- eventos;
- processamento assíncrono;
- contadores;
- rankings derivados;
- notificações temporárias.

A regra é: o PostgreSQL é a verdade; Redis acelera, projeta ou transporta eventos.

A infraestrutura planejada é:

```text
Registro.br + Cloudflare
→ wildcard *.palaciomental.com.br
→ Railway
→ Django identifica o hostname
→ domínio cadastrado resolve o tenant
```

Em desenvolvimento, `?tenant=slug` substitui o DNS real quando DEBUG está habilitado.

## 16. Requisitos sociais e éticos

O P.M. deve:

- preservar autoria;
- obter consentimento antes de expor pessoas ou relatos;
- separar conteúdo público, restrito e privado;
- permitir correção, ocultação ou retirada autorizada;
- evitar ranking de pessoas como mecanismo de pressão;
- manter o Modo Foco como recurso de acessibilidade, não como privilégio pago;
- permitir exportação dos registros principais;
- reduzir dependência da plataforma;
- proteger dados pessoais;
- registrar decisões de governança e moderação;
- não usar custo próximo de zero como justificativa para eliminar segurança, backup ou continuidade.

## 17. Hipóteses de produto e negócio

As hipóteses devem receber métrica, prazo, método e decisão. As datas presentes no documento original devem ser revisadas antes de serem usadas; algumas aparecem como datas provisórias ou inválidas.

Hipóteses de produto:

- usuários compreendem a proposta;
- entrada simples reduz abandono;
- contexto progressivo gera valor;
- Meu Espaço gera retorno recorrente;
- ambientes institucionais atendem CAMPPG;
- relevância melhora descoberta sem criar viés predatório;
- PM Flow e PM VCS resolvem problemas reais.

Hipóteses de negócio:

- usuários pagariam por maior profundidade;
- organizações pagariam por governança;
- ONGs subsidiadas gerariam aprendizado sustentável;
- implantação seria viável;
- configuração seria mais escalável do que customização;
- o núcleo compartilhado poderia ser replicado para outras organizações.

Hipóteses de operação:

- a equipe consegue oferecer suporte;
- custo por organização permanece controlado;
- dados podem ser exportados;
- o sistema permanece acessível;
- a plataforma pode ser operada com segurança por uma equipe enxuta.

## 18. Próximas decisões recomendadas

Antes de ampliar o produto, o assistente deve ajudar a responder:

1. Qual formulação estratégica governa o próximo ciclo: extensão sem fins lucrativos, startup de impacto sustentável ou combinação controlada?
2. Qual é a unidade central do piloto: projeto, iniciativa, ação, oficina, campanha ou programa?
3. Quais dados do CAMPPG são reais, sensíveis, restritos ou publicáveis?
4. Qual é o fluxo mínimo que uma organização precisa completar sem suporte?
5. Quem administra cada tipo de conteúdo?
6. Qual é o indicador principal de continuidade?
7. Qual é o custo real de manter um tenant?
8. Qual é o limite operacional para ONGs subsidiadas?
9. O PM VCS e o PM Flow continuam como hipóteses futuras ou entram no próximo ciclo?
10. Qual é o critério para autorizar a homologação da Issue #82?

## 19. Instrução final para o assistente

Atue como parceiro de produto, pesquisa, arquitetura e desenvolvimento do Palácio Mental. Preserve a visão ampla do Contexto Mestre, mas não trate hipóteses como funcionalidades prontas.

Em toda resposta importante, diferencie:

- visão e propósito;
- decisão aprovada;
- implementação existente;
- hipótese de produto;
- hipótese de negócio;
- requisito de extensão;
- pendência do Product Owner;
- dependência de outro membro;
- risco técnico ou ético.

Use fontes externas apenas quando necessário e cite-as. Use o código para confirmar o estado técnico. Não proponha apagar partes do ecossistema, da visão social ou do modelo de sustentabilidade apenas porque elas não fazem parte da implementação atual.
