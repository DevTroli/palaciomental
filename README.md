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

### Instalação Local

Pré-requisitos: [Git](https://git-scm.com/), [Python 3.x](https://www.python.org/) e [Docker](https://www.docker.com/) (usado para rodar o banco de dados de forma isolada e idêntica para todo o time, sem precisar instalar PostgreSQL na máquina).

```bash
# 1. Clone o repositório
git clone https://github.com/DevTroli/palaciomental.git
cd palaciomental

# 2. Crie e ative um ambiente virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Copie o arquivo de variáveis de ambiente
cp .env.example .env
# edite o .env com suas credenciais de banco de dados

# 5. Suba o banco de dados via Docker
docker compose up -d
# isso inicia o PostgreSQL em background, usando as variáveis do seu .env

# 6. Rode as migrações
python manage.py migrate

# 7. Suba o servidor de desenvolvimento
python manage.py runserver
```

A aplicação estará disponível em `http://localhost:8000`.

> O frontend (HTML/CSS/JS) é servido pelo próprio Django via templates/arquivos estáticos nesta fase do projeto. Consulte `Docs/GUIA_GITHUB_GESTAO.md` para detalhes específicos do ambiente configurado.

**Comandos Docker úteis:**

| Comando | O que faz |
|---|---|
| `docker compose up -d` | Sobe o banco em background |
| `docker compose down` | Para e remove o container (dados persistem no volume) |
| `docker compose down -v` | Para e **apaga** os dados do banco também |
| `docker compose logs -f database` | Acompanha os logs do banco em tempo real |
| `docker compose ps` | Mostra o status dos containers |

---

**Feito com 💚 pela equipe Palácio Mental · Fatec Praia Grande · 2026**
