# Sprint Emergencial M4 — Multi-tenant CAMPPG v2

## Correção de escopo

A fundação multi-tenant do MVP não deve implementar o ecossistema PM Flow, PM VCS ou automações futuras. Esses produtos ficam fora da M4.

A M4 deve entregar a experiência institucional completa, incluindo backend, banco, subdomínio, front-end, UX, identidade visual, acessibilidade e vitrine do tenant. A camada visual não é um acabamento posterior: ela é parte do produto porque o usuário entende seu contexto, suas permissões e seus projetos pela interface.

O alinhamento sobre SQL, Redis e eventual MongoDB acontece em uma sprint paralela, sem bloquear o núcleo multi-tenant.

## Milestones

### M4: Sprint Emergencial — Multi-tenant CAMPPG

- [Milestone M4](https://github.com/DevTroli/palaciomental/milestone/9)
- Prazo: 14/11/2026.
- Escopo: modelagem Django, isolamento por linhas, tenant privado por subdomínio, entrada por convite, programas/grupos, projetos institucionais, separação do Meu Espaço, permissões, catálogo interno, front-end, UX e acessibilidade.

### M4.1: Alinhamento NoSQL do MVP

- [Issue paralela #81](https://github.com/DevTroli/palaciomental/issues/81)
- Prazo: 07/11/2026.
- Escopo: decisão documentada sobre SQL, Redis e eventual MongoDB.
- Fora do escopo: PM Flow, PM VCS e integrações completas do ecossistema.

## Sequência de desenvolvimento

### Fundação de dados e tenant

As issues #74–#77 definem o contrato arquitetural, criam as entidades em português, resolvem o subdomínio e garantem o isolamento por linhas.

### Estrutura institucional

A issue #78 cria programas, turmas e grupos opcionais. A issue #80 define papéis, convites e permissões. O modelo suporta tanto projetos orientados por professores quanto projetos autônomos, sem papel separado de mentor.

### Produto e experiência

A issue #79 separa projetos pessoais, institucionais e vitrines. As issues #83, #85, #86 e #87 completam a camada de front-end:

- shell institucional, navegação, breadcrumbs e contexto visual;
- home/vitrine institucional do CAMPPG;
- fluxo visual de programas, grupos e projetos;
- sistema visual, responsividade e acessibilidade.

A issue #82 fecha o piloto com DNS, Railway, Cloudflare, seed do CAMPPG e validação para 50–100 usuários.

## User stories visuais adicionadas

### Shell institucional

**Como um** usuário afiliado e autenticado do CAMPPG, **eu quero** reconhecer imediatamente que estou no ambiente institucional privado correto, **para que** eu não confunda projetos institucionais com meu espaço pessoal ou com conteúdo global.

A interface deve preservar a identidade base do Palácio Mental, apresentar o tenant atual e oferecer o Meu Espaço apenas como saída explícita do ambiente institucional.

### Home e vitrine institucional

**Como um** usuário afiliado e autenticado do CAMPPG, **eu quero** ver uma página inicial privada da organização com seus programas e projetos publicados, **para que** eu encontre o trabalho institucional sem expô-lo a terceiros ou misturá-lo à plataforma global.

A consulta precisa ser filtrada no backend pelo tenant e pela afiliação ativa. O front-end deve apresentar branding, programas publicados, projetos publicados, estados básicos, estados vazios e links conforme a visibilidade.

### Fluxo de programas e grupos

**Como um** professor, gestor ou participante afiliado, **eu quero** criar e navegar por programas, turmas, grupos e projetos institucionais com uma sequência visual simples, **para que** eu consiga orientar ou iniciar um projeto sem misturar o conteúdo do tenant com o P.M. global.

A entrada deve seguir o princípio do Palácio Mental: começar simples e aprofundar o contexto progressivamente.

### Sistema visual institucional

**Como um** usuário de uma instituição, **eu quero** uma interface consistente, legível e adaptável à identidade da organização, **para que** o ambiente pareça profissional sem perder a linguagem do Palácio Mental.

O branding deve ser controlado por tokens, com fallback seguro, contraste adequado, foco de teclado, hierarquia tipográfica, respiro, estados de erro e responsividade.

## Decisão de NoSQL para alinhamento paralelo

O PostgreSQL continua sendo a fonte oficial de:

- usuários;
- organizações;
- afiliações;
- permissões;
- programas, turmas e grupos;
- projetos;
- comentários e comentários aninhados;
- votos;
- marcos;
- notificações persistentes;
- planos e assinaturas.

Redis pode apoiar sessões, cache de tenant, TTL, locks, contadores e rankings derivados. Qualquer contador ou ranking em Redis deve ser reconstruível a partir do PostgreSQL.

MongoDB só entra se for aprovado um caso documental real, como snapshots flexíveis ou documentos de integração. Ele não deve substituir login, comentários, votos ou permissões no MVP.

## Definition of Done da M4

A M4 estará concluída quando o fluxo abaixo funcionar em ambiente de teste:

```text
convite → autenticação → afiliação → subdomínio → organização → programa/grupo opcional → projeto institucional → catálogo interno
```

Além disso:

- projetos pessoais continuam funcionando;
- o tenant não aceita cadastro anônimo nem acesso sem autenticação e afiliação;
- projetos institucionais, programas publicados e estados básicos ficam no catálogo interno do tenant nesta fase;
- projetos institucionais não aparecem na vitrine global;
- dentro do tenant, a criação é exclusivamente institucional; projetos pessoais ficam no Meu Espaço;
- dois tenants não conseguem acessar os dados um do outro;
- backend e templates respeitam os papéis;
- front-end é consistente com o P.M e o branding institucional;
- responsividade, contraste e teclado são verificados;
- migrations Django são reversíveis;
- o ambiente é testado com 50–100 usuários simulados;
- Redis não é fonte única de nenhum dado oficial;
- documentação de deploy e rollback está atualizada.

## Fora do escopo

- PM Flow completo;
- PM VCS completo;
- automações do ecossistema;
- billing real;
- domínio personalizado por instituição;
- banco ou schema separado por tenant;
- MongoDB como fonte oficial do domínio;
- RLS obrigatório nesta primeira implementação;
- relatórios institucionais avançados.
