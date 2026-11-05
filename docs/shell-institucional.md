# Shell institucional compartilhado

O shell institucional é usado pelas telas do tenant sem misturar o ambiente da organização com a vitrine global.

## Componentes

- `templates/institutional/partials/shell_nav.html`: atalho de teclado, início do tenant, projetos do tenant, gestão conforme papel e saída para Meu Espaço.
- `templates/institutional/partials/shell_footer.html`: identidade da organização, retorno ao ambiente e Meu Espaço.
- `static/css/institutional.css`: layout responsivo, foco visível, contraste, cards, formulários, estados vazios e navegação mobile.
- `static/favicon.ico`: fallback para evitar erro de recurso e manter identidade básica do ambiente.

## Regras de experiência

1. O tenant é sempre o contexto principal do cabeçalho e dos breadcrumbs.
2. Meu Espaço aparece como saída explícita; não é misturado aos projetos institucionais.
3. Gestão só aparece para proprietários e gestores.
4. Toda página inicia com um link “Pular para o conteúdo principal”.
5. A ação principal usa foco visível e contraste compatível com WCAG AA.
6. Estados vazios devem explicar o próximo passo em linguagem direta.
7. A organização pode fornecer logo e cores, mas a interface mantém fallback seguro quando a identidade estiver ausente ou com baixo contraste.

## Validação da #98

A home do tenant CAMPPG foi auditada com Lighthouse em desktop e mobile, usando sessão autenticada. Resultado final: acessibilidade 100%, performance 100% e boas práticas 100%. As páginas de programas e gestão também alcançaram 100% em acessibilidade e boas práticas.
