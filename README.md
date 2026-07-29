# 🧠 Palácio Mental

### Rede Acadêmica de Compartilhamento de Projetos

> **Imagine o GitHub, mas pensado para o projeto acadêmico em sua totalidade — não só o código, mas a ideia, o processo, a documentação e a evolução. O Palácio Mental é onde o trabalho do semestre deixa de morrer num ZIP e passa a existir.**

**Trabalho Semestral — Engenharia de Software**
**Fatec Praia Grande · Desenvolvimento de Software Multiplataforma · 1º Semestre de 2026**

---

## 👥 Equipe

| Membros |
|---|
| Pablo Troli |
| Felipe Figueiredo |
| Eduardo Elias |
| Iago Sampaio |
| Yohan Ruiz |
| DevOps & Docs | Matheus Fernandes |

---

## 💡 Proposta de Valor

| Para quem | Dor atual | O que o Palácio Mental oferece |
|---|---|---|
| Estudante de tecnologia | Projetos ficam esquecidos após a entrega | Portfólio vivo, construído ao longo do curso |
| Estudante iniciante | Não sabe o que os colegas mais avançados estão fazendo | Feed de projetos por categoria e nível |
| Professor / orientador | Não tem visibilidade do progresso dos alunos fora da sala | Projetos públicos com histórico de atualizações |
| Recrutador / empresa | Dificuldade de encontrar talentos acadêmicos emergentes | Perfis com projetos reais, comentados pela comunidade |

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Banco de Dados | MariaDB 11.8 (MySQL-compatible) |
| Backend | A definir |
| Frontend | A definir |
| Design | Figma |
| DevOps | Docker + GitHub Actions|

---

## 🗃️ Modelagem de Banco de Dados

### Entidades

- **USUARIO** — perfis de criadores da plataforma
- **PROJETO** — ideias e trabalhos publicados (entidade central)
- **CATEGORIA** — classificação principal dos projetos
- **TAG** — palavras-chave livres para descoberta
- **COMENTARIO** — feedback da comunidade (entidade fraca)
- **MIDIA** — arquivos e links associados aos projetos (entidade fraca)
- **CURTIDA** — interação N:M entre USUARIO e PROJETO
- **SALVO** — curadoria pessoal N:M entre USUARIO e PROJETO
- **PROJETO_TAG** — tabela associativa N:M entre PROJETO e TAG

### Diagramas e Documentação

- Modelo Conceitual: `database/docs/modelo_conceitual_palaciomental.png`
- Modelo Lógico: `database/docs/modelo_logico_palaciomentasl.png`
- Dicionário de Dados: `database/docs/dicionario_dados.md`
- DDL MySQL: `database/mysql/palacio_mental_mysql.sql`

---

## 🔧 Como Contribuir

1. Leia o `Docs/GUIA_GITHUB_GESTAO.md` antes de qualquer coisa
2. Pegue uma issue do board (GitHub Projects)
3. Crie uma branch: `feature/nome-da-feature` a partir de `develop`
4. Abra Pull Request para `develop` com pelo menos 1 aprovação
5. Nunca commite direto em `main` ou `develop`

---

**Feito com 💚 pela equipe Palácio Mental · Fatec Praia Grande · 2026**
