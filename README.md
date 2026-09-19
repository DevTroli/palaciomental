# 🧠 Palácio Mental

> Plataforma de Colaboração e Memória Institucional para Projetos Sociais — um espaço gratuito e colaborativo onde iniciativas sociais ganham memória viva, transparência e continuidade.

**Projeto de Extensão Acadêmica**
Fatec Praia Grande · Desenvolvimento de Software Multiplataforma · 2º Semestre de 2026

---

## Equipe

| Membro | Papel |
|---|---|
| Pablo Troli | Product Owner |
| Yohan Ruiz | Scrum Master |
| Felipe Figueiredo | Dev Team |
| Iago Sampaio | Dev Team |
| Matheus Fernandes | Dev Team |

---

## Arquitetura

| Camada | Tecnologia |
|---|---|
| **Banco de Dados** | PostgreSQL / MySQL |
| **Backend** | Python (Django) / Java (Spring Boot) |
| **Frontend** | HTML5, CSS3, JavaScript — foco em acessibilidade e responsividade |
| **Design & UX** | Figma (Modo Foco e baixa carga sensorial) |
| **DevOps** | Docker + GitHub Actions (CI/CD) |

### Backend
Stack ainda em avaliação entre Django e Spring Boot, expondo API para o consumo do frontend e controle de permissões por papel de usuário.

### Frontend
Interface responsiva construída com foco em acessibilidade cognitiva, incluindo o Modo Foco como recurso nativo de redução de estímulos visuais.

### DevOps
Aplicação conteinerizada com Docker. CI/CD via GitHub Actions.

---

## Modelagem de Dados

**Entidades:** `USUARIO` (papéis: administrador, coordenador, colaborador, participante, voluntário, visitante) · `ORGANIZACAO` · `INICIATIVA` (central) · `HISTORICO`/`ATUALIZACAO` · `CATEGORIA` & `TAG` · `COMENTARIO` (classificado) · `PERMISSAO`/`VISIBILIDADE`

- Modelo Conceitual: `database/docs/modelo_conceitual_palaciomental.png`
- Modelo Lógico: `database/docs/modelo_logico_palaciomental.png`
- Dicionário de Dados: `database/docs/dicionario_dados.md`
- Scripts DDL: `database/scripts/`

---

## Regras e Princípios de Governança

- **Finalidade social:** sem monetização sobre dados ou cobrança de funcionalidades essenciais
- **Proteção e consentimento:** publicação de conteúdos e mídias de participantes exige autorização expressa da organização
- **Modo Foco acessível:** funcionalidade nativa e gratuita, disponível a todos os usuários
- **Portabilidade:** exportação de dados e relatórios da iniciativa em formatos legíveis

---

## Como Contribuir

1. Leia `Docs/GUIA_GITHUB_GESTAO.md` antes de qualquer coisa
2. Pegue uma issue do board (GitHub Projects)
3. Crie uma branch a partir de `develop`: `feature/nome-da-feature` ou `fix/nome-do-bug`
4. Abra Pull Request para `develop` solicitando revisão do time
5. Commits diretos em `main` ou `develop` são bloqueados

---

### Instalação Rápida (Docker Compose — Recomendado)

Pré-requisitos: [Git](https://git-scm.com/) e [Docker](https://www.docker.com/) + Docker Compose.

```bash
# 1. Clone o repositório
git clone https://github.com/DevTroli/palaciomental.git
cd palaciomental

# 2. Configure variáveis de ambiente
cp .env.example .env
# (as defaults já funcionam para desenvolvimento)

# 3. Suba tudo de uma vez
docker compose up --build -d
```

| Serviço | URL | Descrição |
|---|---|---|
| **Django** | http://localhost:8000 | Frontend (Lista de Espera) + API REST |
| **Spring Boot** | http://localhost:8080/actuator/health | API de status/saúde |
| **PostgreSQL** | localhost:5433 | Banco de dados (credenciais no `.env`) |

> O `docker compose` sobe os 3 serviços com healthchecks: banco → Django → API Java. O Django roda migrações automaticamente no entrypoint.

---

### Desenvolvimento com Hot-Reload (Opcional)

Se quiser editar código Django e ver mudanças instantâneas sem rebuild:

```bash
# 1. Suba apenas o banco
docker compose up -d database

# 2. Ambiente virtual local
python -m venv venv && source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. Dependências e migrações
pip install -r requirements.txt
python manage.py migrate

# 4. Runserver com hot-reload
python manage.py runserver
```

> A API Java (`status_api`) continua no Docker se quiser — basta não derrubar o container dela (`docker compose up -d status_api`).

---

**Comandos Docker do dia a dia:**

| Comando | O que faz |
|---|---|
| `docker compose up --build -d` | Sobe **tudo** (DB + Django + API Java) |
| `docker compose up -d database` | Sobe só o PostgreSQL |
| `docker compose down` | Para tudo (dados persistem no volume `pgdata`) |
| `docker compose down -v` | Para e **apaga** dados do banco |
| `docker compose logs -f django` | Logs do Django em tempo real |
| `docker compose logs -f status_api` | Logs da API Java |
| `docker compose ps` | Status de todos os containers |

---

**Feito com 💚 pela equipe Palácio Mental · Fatec Praia Grande · 2026**
