# PM11: cadastro por convite, CSRF e apresentação do e-mail

## Problema e escopo aprovado

O cadastro pelo convite institucional retornou 403 tanto no teste automatizado de produção quanto no relato de teste manual. O formulário também exigia informação desnecessária para a entrada, e o rodapé do e-mail precisava integrar melhor a apresentação do Palácio Mental.

Este ajuste mantém a arquitetura de organizações, domínios e convites existente. Não altera RLS, conexão ao banco, SMTP/Resend, DNS, R2 nem esquema de dados. O cadastro público global não foi redesenhado.

## Evidências e diagnóstico

- A página do convite definia `Referrer-Policy: no-referrer`.
- A documentação do Django descreve a validação de Origin e, para HTTPS sem Origin, a validação estrita de Referer. A mesma documentação alerta para incompatibilidade de `no-referrer` com esse fluxo: https://docs.djangoproject.com/en/5.2/ref/csrf/.
- Em Chromium local, com HTTPS e o formulário real, simular a política antiga produziu `Origin: null`, sem Referer, e resultou em 403 mesmo com token válido.
- Com `strict-origin`, o mesmo fluxo enviou Origin válido e Referer contendo somente a origem, sem o caminho do convite. Cadastro e aceite funcionaram.
- Os cabeçalhos do envio original de produção não foram capturados. A reprodução comprova o defeito da política antiga, mas a resolução do incidente em produção só deve ser declarada após deploy e novo teste.

## Alterações

- Convites usam `strict-origin`, sem desativar CSRF nem ampliar origens confiáveis.
- Tela contextual de CSRF mantém o status 403, não armazena em cache e oferece reabertura por GET para rotas de formulário conhecidas. Não repete automaticamente o POST.
- O tratamento de PermissionDenied apresenta orientação segura, sem detalhes internos nem nova tentativa enganosa para convite expirado.
- Logs adicionais registram somente a categoria do bloqueio, sem token do convite, dados enviados, senha ou e-mail.
- Cadastro por convite tem três campos visíveis: usuário, senha e confirmação. O e-mail permanece fixo e validado pelo servidor; o nome deixa de ser obrigatório nesse fluxo.
- Um indicador apresenta as etapas reais: criar conta e confirmar entrada. A criação da conta não afilia automaticamente a organização.
- Regras de senha ficam em uma seção expansível, aberta quando há erro de senha. Validadores e mensagens continuam ativos.
- O formulário não força foco inicial que desloque a página em telas pequenas.
- Rodapé HTML compartilha uma linha de logo e apresentação no desktop e empilha em telas estreitas. Identidade da instituição, escopo do convite, CTA e alternativa em texto permanecem.

## Validação

### Testes de regressão

Suíte completa: 167 testes passaram. `manage.py check` não encontrou problemas, `makemigrations --check --dry-run` não detectou mudanças de esquema, e `git diff --check` passou.

Cobertura com CSRF efetivamente habilitado:

- HTTPS sem Origin/Referer continua bloqueado.
- Origin nulo, origem externa e token inválido continuam bloqueados.
- Referer contendo somente a origem permite cadastro e aceite.
- Origem válida continua suportada.
- E-mail enviado pelo cliente não substitui o destinatário do convite.
- Conta sem nome pode ser criada; afiliação exige aceite explícito.
- Senhas divergentes não criam conta.
- Convite expirado não oferece cadastro nem reabertura enganosa.
- Logs não incluem dados sensíveis.
- Formulário compacto e rodapé HTML mantêm seus elementos essenciais.

### Navegação local

Em banco local, sem enviar mensagens:

- Reprodução do 403 com política antiga e recuperação pelo link da tela.
- Erro de senhas divergentes exibido junto ao campo.
- Cadastro com política nova chega à confirmação de entrada.
- Página inicial institucional responde 403 antes do aceite.
- Aceite leva à lista de projetos institucional.
- Sem erros JavaScript no percurso observado.
- Formulário e e-mail revisados em desktop e 375 px, sem rolagem horizontal.

A inspeção visual de HTML em Chromium não substitui homologação em clientes de e-mail, como Gmail e Outlook.

## Riscos, hipóteses e critérios

- **Hipótese de UX:** reduzir os campos iniciais e explicitar as duas etapas diminui a carga de entrada. Ainda não foi medido abandono ou tempo de conclusão com usuários.
- **Métrica sugerida:** proporção de convites abertos que chega ao aceite e frequência de 403 no cadastro, sem registrar token ou conteúdo pessoal nos logs.
- **Critério funcional:** um convite válido permite criar conta, confirmar afiliação e entrar somente no ambiente autorizado; entradas inválidas continuam bloqueadas.
- **Entrega de e-mail:** o usuário confirmou recebimento do HTML em Promoções. Nenhuma alteração desta branch promete classificação como Principal, que depende do provedor e do destinatário.
- **Persistência de mídia:** R2 e logos já configurados não são modificados aqui. A confirmação de um novo upload pela interface de produção segue como verificação separada.

## Após o merge feito pelo responsável

- Aguardar o Railway concluir o deploy do commit aprovado.
- Reabrir o link do convite por uma navegação nova, evitando submeter a página antiga ainda carregada.
- Confirmar que o convite continua pendente e válido; se expirou, a gestão deve emitir novo convite.
- Fazer cadastro, observar etapa de confirmação e aceitar.
- Verificar acesso ao ambiente correto e bloqueio do mesmo usuário em outra organização não afiliada.
- Confirmar a tela de recuperação caso haja novo bloqueio. Investigar a categoria sanitizada antes de mudar configurações de segurança.
- Revisar o rodapé em uma nova mensagem autorizada e confirmar um upload pela interface de gestão.

Não fazer merge automático nem reenviar convites reais como parte desta branch. Reverter este PR restaura a apresentação anterior e também a política antiga problemática; não é uma solução de segurança para o incidente.
