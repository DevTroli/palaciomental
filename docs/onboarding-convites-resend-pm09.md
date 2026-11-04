# PM-09: entrada por convite e envio transacional

## Problema confirmado no código

O aceite de um convite funcionava para uma conta já autenticada, mas o percurso
normal estava incompleto: o login institucional barrava quem ainda não tinha
afiliação antes de retornar ao convite, e não existia cadastro vinculado ao token.
Os testes anteriores usavam `force_login` para o aceite, sem percorrer esse login.
Além disso, abrir o link com GET consumia o convite e alterava a afiliação.

Criar usuário e afiliação manualmente pelo Admin é uma intervenção privilegiada,
não uma comprovação do onboarding por convite.

## Fluxo implementado

- GET do link válido mostra a organização, destinatário, validade e opções de
  entrada. Não cria afiliação nem consome o convite.
- Quem ainda não tem conta cadastra nome, usuário e senha no próprio link.
  O e-mail é fixado pelo servidor ao destinatário do convite, não pelo POST.
- Quem já tem conta pode autenticar-se e retornar ao convite válido, mesmo antes
  da afiliação. Essa exceção não libera outras páginas do tenant.
- Após autenticação, o destinatário confirma o aceite em POST protegido por CSRF.
- A transação bloqueia a linha do convite com `SELECT FOR UPDATE`, revalida
  host, estado, expiração e e-mail, cria as relações e consome o token.
- Convites de grupo também criam a afiliação e a participação na turma. Não
  contornam afiliação institucional ou participação na turma suspensas.
- O cadastro institucional sem token continua fechado. Uma conta pessoal não
  concede afiliação automaticamente.
- O cadastro pelo convite não adiciona privilégios de staff/superusuário.

O convite individual é um segredo: não deve ser publicado ou compartilhado.
Permanece armazenado somente o hash do token no banco. A página de convite usa
`Cache-Control: no-store` e `Referrer-Policy: no-referrer`; os avisos de envio não
exibem o token. Em desenvolvimento, o backend console pode mostrar o link no
terminal, como antes.

## Resend via HTTPS

O backend `plataforma.email_backends.ResendEmailBackend` implementa o contrato
de e-mail do Django para as mensagens de texto/HTML dos convites. Usa
`POST https://api.resend.com/emails`, chave Bearer, timeout e idempotência por
convite. Não requer novo pacote. Anexos não são suportados e falham
explicitamente, em vez de serem descartados.

Referência do contrato: [Resend Send Email](https://resend.com/docs/api-reference/emails/send-email).

O plano gratuito consultado oferece 3.000 mensagens/mês, com limite de 100/dia.
Esses limites precisam ser acompanhados antes de convites em lote:
[Resend Pricing](https://resend.com/pricing).

A escolha de HTTPS evita depender de SMTP, que o Railway restringe aos planos
Pro ou superiores: [Railway Outbound Networking](https://docs.railway.com/networking/outbound-networking).

## Ativação após revisão, em etapa separada

Este PR não cria conta no provedor, não cadastra domínio, não altera DNS,
variáveis de produção nem executa envio real.

1. Criar a conta gratuita no Resend e verificar um domínio/subdomínio de envio.
2. Aplicar somente os registros DNS indicados pelo provedor, preservando os
   registros atuais do site, wildcard institucional, Railway e e-mail.
3. Criar uma chave restrita a envio e ao domínio necessário. Não colocar a
   chave no Git, chat, documentação ou logs.
4. Após aprovação explícita, configurar no serviço Django:

   ```text
   EMAIL_BACKEND=plataforma.email_backends.ResendEmailBackend
   RESEND_API_KEY=<segredo na variável protegida do Railway>
   RESEND_TIMEOUT=10
   DEFAULT_FROM_EMAIL=Palácio Mental <endereço do domínio verificado>
   ```

5. Fazer o deploy aprovado e testar um convite real para um endereço controlado.
   Confirmar tanto recebimento quanto cadastro/login, aceite e acesso no tenant.

Sem essa ativação, o backend existente permanece selecionado. O backend console
em desenvolvimento continua disponível; não deve substituir o envio real em
produção.

## Falha de envio e limites

O convite é persistido antes do envio. Se configuração ou provedor falharem, o
sistema retorna à gestão com aviso explícito; não apresenta sucesso de envio nem
derruba a página com 500 por essa falha. O convite pendente continua revogável.
Após corrigir o envio, revogar e emitir outro convite pela interface.

Não há fila, reenvio automático ou acompanhamento de entrega/bounce neste escopo.
Aceitação da API não garante recebimento na caixa de entrada. Os testes do backend
usam transporte simulado e não comprovam entrega real.

Não implementa confirmação geral de e-mail de contas pessoais nem recuperação de
conta. O acesso institucional exige posse do token e autenticação com o e-mail
destinatário. Se esse e-mail já existir, o fluxo pede login e nunca substitui sua
senha; a recuperação segura de contas segue como uma frente própria.

## Critérios de validação

- Sem convite, login ou afiliação válidos, não entra no tenant.
- Conta nova: convite → cadastro → confirmação → afiliação → home institucional.
- Conta existente sem afiliação: convite → login real → confirmação → entrada.
- GET e robôs de pré-visualização não consomem o convite.
- Token inválido, expirado, revogado, reutilizado ou em outro host não concede
  acesso.
- POST sem CSRF não cria conta nem aceita convite.
- Dois aceites concorrentes no PostgreSQL resultam em um sucesso e uma recusa.
- Erros de rede, autenticação, limite do provedor e resposta inválida não são
  registrados como envio bem-sucedido.

Sem migrações de banco, concessões adicionais de RLS ou alteração do label legado.
