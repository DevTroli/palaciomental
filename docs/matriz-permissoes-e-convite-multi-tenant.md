# Permissões, convites e checklist multi-tenant

## 1. Matriz do MVP

| Ação | Proprietário | Gestor | Professor autorizado | Membro |
|---|---:|---:|---:|---:|
| Entrar no tenant | Sim | Sim | Sim | Sim |
| Acessar `/gestao/` | Sim | Sim | Não por padrão | Não |
| Criar programa | Sim | Sim | Não | Não |
| Criar turma ou grupo | Sim | Sim | Não | Não |
| Criar projeto institucional autônomo | Sim | Sim | Sim | Sim |
| Emitir convite de grupo | Sim | Sim | Apenas grupo autorizado | Não |
| Alterar afiliações e papéis | Sim | Sim | Não | Não |
| Conceder proprietário | Sim | Não | Não | Não |
| Suspender a própria afiliação | Não | Não | Não | Não |
| Remover o último proprietário ativo | Não | Não | Não | Não |

O papel de professor não é um papel de mentor separado. No MVP, professor exerce orientação quando é responsável pela turma/grupo ou quando possui vínculo local de professor ativo naquele grupo.

## 2. Regras de segurança

- O tenant é resolvido pelo hostname ou, somente em `DEBUG`, pelo parâmetro `?tenant=slug`.
- O acesso institucional exige autenticação e afiliação ativa.
- `organizacao_id` de projeto nunca é aceito do formulário: vem do tenant resolvido pelo middleware.
- Projetos pessoais possuem `organizacao_id = NULL`.
- Projetos institucionais pertencem a uma única organização.
- Um vínculo local de grupo não cria acesso a outro tenant.
- Um projeto privado continua acessível somente pelo proprietário, salvo regra específica futura de projeto.
- Convites de grupo aceitam somente `membro` ou `professor`; não podem conceder `gestor` ou `proprietario`.
- O aceite preserva o papel organizacional existente do usuário; o papel do convite é apenas local ao grupo.
- O último proprietário ativo não pode ser suspenso, removido ou rebaixado.
- Nenhum cache ou camada futura de Redis pode conceder autorização; PostgreSQL permanece a fonte oficial.

## 3. Fluxo do convite HTML

```text
Gestor ou professor autorizado
        ↓
Seleciona o grupo e informa o e-mail
        ↓
Django cria convite com token aleatório
        ↓
Banco salva somente o hash do token
        ↓
Transação confirma o convite
        ↓
E-mail multipart é enviado (texto + HTML)
        ↓
Destinatário abre o link no subdomínio do tenant
        ↓
Autentica com o mesmo e-mail convidado
        ↓
Sistema cria/ativa afiliação básica
        ↓
Sistema cria vínculo na turma/grupo
        ↓
Convite é marcado como aceito
```

O HTML usa a identidade visual configurada no tenant, exibe organização, programa, grupo, papel inicial, expiração e botão de aceite. A versão texto simples permanece como fallback para clientes que não renderizam HTML.

Em desenvolvimento:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Nesse modo, o e-mail aparece no terminal do serviço Django. Em produção, configurar um provedor SMTP ou transacional e `DEFAULT_FROM_EMAIL` com domínio autenticado.

## 4. Checklist da arquitetura multi-tenant

| Requisito | Estado | Evidência |
|---|---|---|
| Resolução por subdomínio | Implementado | `TenantResolutionMiddleware` + `DominioOrganizacao` |
| Resolução local por query string | Implementado | `?tenant=slug`, somente com `DEBUG=True` |
| Banco compartilhado e linhas isoladas | Implementado no escopo MVP | consultas filtram `organizacao`; RLS permanece futuro |
| Tenant privado | Implementado | autenticação + afiliação ativa |
| Identidade visual por organização | Implementado | `IdentidadeOrganizacao` |
| Portal institucional separado do Admin | Implementado | `/gestao/` e middleware do Admin interno |
| Programas, turmas e grupos | Implementado | entidades institucionais e portal |
| Convites de grupo | Implementado | token hash, expiração, aceite e revogação |
| Convite por e-mail HTML | Implementado no backend | templates multipart e `EmailMultiAlternatives` |
| Separação pessoal/institucional | Implementado | `organizacao_id NULL` versus tenant resolvido |
| Vitrines separadas | Implementado | `_project_scope()` e catálogo contextual |
| Papéis e limites de afiliação | Implementado no MVP | views de afiliação e convite |
| RLS no PostgreSQL | Futuro | não bloquear o MVP atual |
| Redis/NoSQL | Sprint M4.1 | não é fonte de autorização |

## 5. Limites conhecidos antes da produção

- O envio atual é síncrono e adequado ao MVP; fila assíncrona deve ser adicionada antes de alto volume.
- O teste automatizado usa banco temporário SQLite; a homologação precisa repetir o fluxo com PostgreSQL no Compose.
- O DNS wildcard é responsabilidade do Cloudflare/Railway, não do Django Admin.
- Ações administrativas de permissões ainda devem ganhar auditoria detalhada antes de uma expansão institucional ampla.
