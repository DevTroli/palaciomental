# PM12: identidade institucional flexível

## Rastreabilidade e decisão

Milestone: https://github.com/DevTroli/palaciomental/milestone/12. Escopo: https://github.com/DevTroli/palaciomental/issues/112 e https://github.com/DevTroli/palaciomental/issues/113.

Foram comparados Pickr e Coloris. Pickr Nano foi escolhido pela preferência explícita do responsável e pelo encaixe compacto em um formulário Django sem framework adicional. O projeto informa conjunto de funcionalidades congelado; não se presume manutenção ativa ilimitada. Referências: https://github.com/simonwep/pickr e https://github.com/mdbassit/Coloris.

A distribuição NPM `@simonwep/pickr@1.10.3` foi fixada e copiada para `static/vendor/pickr-1.10.3`, incluindo licença MIT. SHA1 do pacote observado no NPM: `4d22d141215190655ce8cb04852307d8663191bd`. Nenhum CDN é necessário em runtime. O campo HEX permanece utilizável sem JavaScript.

## Papéis de cor

- Principal: cabeçalho e identificação.
- Secundária: ações de apoio e rodapé de e-mail.
- Destaque: ação principal.
- Fundo: página.
- Superfície: cartões e formulários.

O texto não é um sexto campo livre. Preto/branco e cores de links são derivados com contraste, evitando combinações de marca ilegíveis. Estados de erro não são redefinidos como cores de marca. Aceitam-se apenas valores `#RRGGBB`, sem opacidade, CSS, nomes de cores ou URLs.

## Dados e compatibilidade

A migration 0026 adiciona `tema` como JSON com default vazio. As três colunas semânticas anteriores não são renomeadas, removidas ou reescritas. Ausência de um token usa a paleta anterior. Uma reversão somente de código continua podendo ler as colunas antigas; não é necessário remover a coluna nova para fazer rollback.

O formulário mantém os campos legados ocultos e validados para compatibilidade. POSTs antigos continuam aceitos; os novos campos são gravados em `tema`. A autorização permanece no servidor: somente afiliação ativa com papel Proprietário ou Gestor altera a identidade.

O widget de imagem mostra “Ver imagem atual”, opção de remover e seletor de arquivo. A chave de storage continua existindo no href, mas não é exibida como rótulo técnico. Nenhum nome original fictício foi atribuído a uploads antigos.

## Propagação

O mesmo resolvedor fornece tokens para home, gestão, telas de projeto, login institucional, convite/cadastro e e-mails. O host global não carrega a folha de tema institucional. Login e convite usam a logo cadastrada no tenant; não há logo CAMPPG fixada em outros ambientes.

## Verificações e limites

Testes específicos cobrem HEX e CSS inválidos, compatibilidade, POST direto por papéis não autorizados, afiliação inativa, contraste, propagação e rótulo amigável do upload. A suíte anterior de convites/CSRF, branding e logo também é preservada.

Na validação local, 177 testes passaram. O navegador confirmou cinco seletores, abertura/fechamento do Nano, edição por HEX, salvamento/releitura e ausência de overflow em 375 px e de erros JavaScript. A revisão de uma cor principal quase branca com superfície escura expôs títulos legados ilegíveis; os seletores de texto foram corrigidos antes da entrega.

Não é uma prova de acessibilidade completa por leitor de tela. Não houve escrita em produção, envio real de e-mail ou merge automático nesta implementação. Capa e nova home ficam em branch dependente separada; Postman e auditoria têm suas próprias issues.
