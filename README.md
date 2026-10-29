# Palácio Mental

> **Ideias para além do rascunho.**

O Palácio Mental é uma plataforma de contexto, evolução e conexão para projetos. Ela ajuda pessoas e organizações a preservar o sentido de uma iniciativa, organizar sua trajetória e criar condições para que um projeto seja compreendido, encontrado, continuado ou retomado.

A plataforma combina um espaço autoral individual com ambientes institucionais privados. O produto não substitui ferramentas como GitHub, Drive, Docs, Figma, Trello ou WhatsApp: ele reúne contexto, autoria, decisões, links e continuidade em torno do projeto.

## Estado atual

O repositório está na fase de implementação da arquitetura multi-tenant, começando pelo ambiente institucional do CAMPPG. A estratégia atual é **banco compartilhado com isolamento por linhas**:

- PostgreSQL é a fonte oficial de identidade, permissões, organizações e projetos;
- Redis é uma camada NoSQL derivada para sessões, cache, relevância e eventos;
- subdomínios resolvem organizações, como `camppg.palaciomental.com.br`;
- projetos pessoais permanecem no espaço global do autor;
- projetos institucionais ficam restritos ao tenant da organização;
- o domínio principal não expõe conteúdo institucional.

## Experiência do produto

### Espaço autoral

A pessoa pode criar projetos pessoais, adicionar contexto progressivamente, organizar links, registrar marcos, receber colaboração e publicar projetos públicos na vitrine global.

### Ambiente institucional

A organização possui um ambiente próprio, acessível por convite e afiliação ativa. No MVP, os papéis são:

- proprietário;
- gestor;
- professor;
- membro.

Os projetos institucionais podem ser orientados por um professor ou desenvolvidos autonomamente pelos membros, mas não se misturam ao espaço autoral nem à vitrine global.

## Stack

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| Aplicação | Django 5.2 / Python 3.12 | autenticação, projetos, permissões e interface |
| Relacional | PostgreSQL | fonte de verdade e integridade dos dados |
| NoSQL | Redis | sessões, cache, relevância, contadores e eventos derivados |
| Interface | Django Templates, HTML, CSS e JavaScript | experiência acessível e responsiva |
| Infraestrutura | Docker, Railway e Cloudflare | execução, deploy, DNS, TLS e subdomínios |
| Mídia | FileSystemStorage local / Cloudflare R2 em produção | logos e arquivos persistentes dos tenants |
| API de status | Spring Boot | observabilidade pública do ambiente |

### Mídia e uploads

O ambiente local usa `FileSystemStorage` e grava os arquivos em `MEDIA_ROOT`, persistido pelo Docker durante o desenvolvimento. Railway e homologação devem usar o Cloudflare R2, compatível com a API S3, para que as mídias não desapareçam quando um container for recriado.

Para habilitar o R2, configure no ambiente de produção:

```env
R2_ENABLED=True
R2_ACCOUNT_ID=...
R2_BUCKET_NAME=palacio-mental-media
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_PUBLIC_URL=https://media.palaciomental.com.br
```

Com `R2_ENABLED=True`, a aplicação exige todas as credenciais e não faz fallback silencioso para o disco local. Com `R2_ENABLED=False`, o Docker continua usando a mídia local. As chaves devem ser configuradas como secrets na Railway, nunca versionadas no repositório.

## Execução local

### Dependências

- Python 3.12 ou compatível;
- Docker e Docker Compose;
- PostgreSQL local ou o serviço `database` do Compose;
- Redis conforme a configuração do ambiente.

### Configuração

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Defina pelo menos `DJANGO_SECRET_KEY` e `DATABASE_URL` no `.env`. Para testar tenants localmente, use também:

```env
PALACIO_BASE_DOMAIN=palaciomental.com.br
TENANT_RESERVED_HOSTS=www,api,status,admin,app
```

### Banco e servidor

```bash
python manage.py migrate
python manage.py runserver
```

A aplicação estará disponível em [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

## Como validar como Product Owner

A validação pode ser feita em três níveis.

### 1. Validação automática

Execute:

```bash
DJANGO_SECRET_KEY=test-secret-key \
DATABASE_URL=sqlite:////tmp/palaciomental-test.sqlite3 \
python manage.py check

DJANGO_SECRET_KEY=test-secret-key \
DATABASE_URL=sqlite:////tmp/palaciomental-test.sqlite3 \
python manage.py test
```

O resultado esperado é `System check identified no issues` e todos os testes concluídos com `OK`.

Também confirme que não há migration esquecida:

```bash
DJANGO_SECRET_KEY=test-secret-key \
DATABASE_URL=sqlite:////tmp/palaciomental-test.sqlite3 \
python manage.py makemigrations --check --dry-run
```

O resultado esperado é `No changes detected`.

### 2. Validação funcional do espaço global

1. Abra `/` e confirme que a home do Palácio Mental aparece.
2. Crie uma conta em `/cadastrar/`.
3. Entre em **Meu espaço**.
4. Crie um projeto pessoal.
5. Adicione contexto, links e altere a visibilidade.
6. Verifique que o projeto pessoal aparece apenas no espaço autoral e, quando público, na vitrine global.
7. Abra `/status/` e confirme que a página funciona mesmo se a API externa estiver indisponível.

### 3. Validação funcional do tenant CAMPPG

O Django Admin foi organizado para que `Organização` seja o ponto central da configuração. No admin, crie uma organização e, na própria tela dela:

1. informe nome, nome legal, slug e situação do ambiente;
2. adicione a identidade visual no bloco **Identidade exibida**;
3. adicione o hostname no bloco **Domínios das organizações**;
4. depois crie a afiliação do usuário em **Afiliações organizacionais**;
5. use **Convites das organizações** quando a entrada precisar ser controlada por convite.

O token técnico do convite é gerado automaticamente e o administrador que o criou é registrado. O admin também normaliza hostnames e impede que a equipe informe protocolo ou barras por engano. Campos técnicos, identificadores e datas de auditoria ficam protegidos ou recolhidos para não competir com as decisões operacionais.

Ao abrir o índice do admin, a equipe encontra quatro fluxos guiados, em vez de uma lista solta de tabelas:

1. **Preparar um ambiente institucional** — criar a organização, completar identidade e domínio.
2. **Controlar quem entra** — criar afiliações ou convites e revisar papel e situação.
3. **Operar projetos** — consultar projetos, links, membros, marcos e colaboração.
4. **Revisar e corrigir** — investigar domínios, acessos e histórico antes de alterar dados.

A lista completa de modelos técnicos continua disponível em uma seção avançada, para manutenção especializada sem competir com os fluxos cotidianos.

### Separação de administração

O `/admin/` é exclusivo da equipe interna do Palácio Mental. Usuários institucionais não devem receber `is_staff` para operar essa área, porque ela dá acesso à estrutura técnica completa da plataforma.

Gestores, proprietários e professores acessam a gestão pelo subdomínio da própria organização, em `/gestao/`. Esse portal mostra o tenant atual, aplica a afiliação e o papel institucional e será ampliado pela M4 para programas, turmas, grupos e permissões. O grupo interno padrão do Django Admin é `Equipe PM`, configurável por `PM_INTERNAL_ADMIN_GROUPS`.

O primeiro fluxo da Issue #78 já está disponível no portal:

- `/gestao/programas/` lista e cria programas da organização atual;
- `/gestao/programas/<id>/` mostra a estrutura de um programa;
- `/gestao/programas/<id>/grupos/novo/` cria uma turma ou grupo;
- projetos autônomos continuam possíveis sem programa;
- todas as consultas filtram a organização resolvida pelo subdomínio.

Depois, teste:

- usuário não autenticado no subdomínio: deve ser direcionado para login;
- usuário autenticado sem afiliação: deve receber `403`;
- usuário com afiliação ativa: deve acessar o ambiente;
- criação de projeto no subdomínio: deve gravar `Projeto.organizacao` automaticamente;
- projeto pessoal acessado pelo subdomínio: deve retornar `404`;
- projeto institucional acessado pelo domínio principal: deve retornar `404`;
- subdomínio desconhecido: deve retornar `404`, sem mostrar dados de outro tenant.

> Para testar localmente um hostname, adicione uma entrada ao arquivo `hosts`, por exemplo `127.0.0.1 camppg.palaciomental.com.br`, e inclua o domínio em `ALLOWED_HOSTS`.

## Documentação

Toda a documentação do projeto fica em [`docs/`](docs/):

- [Modelagem multi-tenant v2](docs/modelagem-multi-tenant-v2.md)
- [DER multi-tenant em português](docs/der-multi-tenant-pt.mmd)
- [Sprint emergencial multi-tenant](docs/sprint-emergencial-multi-tenant-v2.md)
- [Integração Redis no produto](docs/redis-django-mvp.md)
- [Relatório de acessibilidade e IHC](docs/relatorio-acessibilidade-ihc.docx)
- [Roteiro de demonstração](docs/roteiro-demo-produto-1-minuto.md)

Os documentos de estratégia e contexto mestre também ficam nessa pasta, separados do código executável.

## Organização do código

```text
core/                 Home pública e navegação institucional
plataforma/           Identidade, projetos, colaboração, tenants e status
setup/                Configuração Django, URLs e WSGI
status_api/           Serviço separado de status
templates/            Templates HTML da interface
static/               CSS, JavaScript e imagens
assets/               Materiais visuais de apoio
docs/                 Documentação técnica, produto e operação
compose.yaml          Ambiente local conteinerizado
```

O pacote `plataforma` substituiu a antiga app de lista de espera. O identificador histórico presente nas migrations existe apenas para preservar bancos já migrados; a funcionalidade de lista de espera, suas rotas e sua interface foram removidas.

## Desenvolvimento

Antes de abrir um Pull Request:

```bash
git diff --check
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Commits deste repositório devem usar a identidade de desenvolvimento definida pelo projeto:

```bash
git config user.name "DevTroli & git"
git config user.email "brawlixo123@gmail.com"
```

## Princípios do produto

- contexto antes de complexidade;
- entrada simples e profundidade progressiva;
- privacidade institucional por padrão;
- PostgreSQL como verdade, Redis como camada derivada;
- não misturar propriedade intelectual do Palácio Mental com o conteúdo do cliente;
- acesso inclusivo, compreensível e orientado por boas práticas de IHC;
- crescimento sustentável, sem métricas predatórias ou dependência de customizações frágeis.
