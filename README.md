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
| API de status | Spring Boot | observabilidade pública do ambiente |

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

No admin Django, crie:

1. uma `Organização` com slug `camppg`;
2. um `Domínio da organização` com hostname `camppg.palaciomental.com.br`;
3. uma `Afiliação organizacional` ativa para um usuário;
4. opcionalmente, uma identidade visual para a organização.

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
