# Capa e home institucional

Entrega da issue #114 na milestone #12. Depende do PR de tema #117; não substitui a autorização de merge do responsável.

## Problema e decisão

A organização precisa reconhecer o próprio ambiente e explicar seu contexto, sem perder a consistência do Palácio Mental. A referência aprovada se traduz em uma única página com scroll, não em duas telas desconectadas.

- Capa opcional com recorte central, logo sobreposta, nome e apresentação.
- Seis atalhos para rotas existentes e compatíveis com o papel. Gestão aparece somente para Proprietário/Gestor.
- Projetos autônomos, vinculados e destaques em três colunas no desktop; empilhados no mobile.
- Programas e turmas continuam disponíveis abaixo. Agenda/orientações não viraram funcionalidades novas.
- Navbar comum às telas institucionais com busca restrita aos projetos do host, caixa de entrada, criação e menu da conta. “Meu espaço pessoal” é explicitamente uma saída para o domínio global.
- Ranking continua provisório: votos e atualização, não a projeção Redis.

## Dados, segurança e persistência

Migration 0027 aditiva: `capa` e `apresentacao` opcionais. Nenhum nome físico legado é alterado. A capa usa o mesmo storage R2 configurado para mídias, sem nova credencial ou bucket.

Aceita PNG/JPEG/WebP estáticos, até 5 MB, entre 640×160 e 6.000×3.000 px, proporção horizontal 1,5:1 a 8:1. Recomendação de composição: 1.920×640 px. Normaliza a orientação EXIF, remove metadados e limita o maior lado a 2.400 px.

Cada upload tem chave nova para evitar imagem antiga em caches. Remover/substituir desfaz o vínculo no banco; não apaga objetos antigos do bucket automaticamente. Uma rotina de limpeza futura depende de política de retenção e autorização própria.

Apresentação de até 600 caracteres, renderizada com escape de HTML. As permissões existentes no servidor protegem o POST de logo, capa e cores. A capa é pública como identidade visual, não serve para documentos privados.

A home consulta apenas projetos públicos do próprio tenant. “Público” aqui não remove o gate institucional: afiliação continua necessária. Projetos privados ficam na área própria, respeitando as regras existentes.

E-mail, login e cadastro usam a identidade do tenant; o e-mail inclui a capa quando configurada. Nenhuma imagem CAMP é hardcoded. Classificação como Promoções/Principal continua sendo decisão do provedor do destinatário.

## Validação e rollback

Testes cobrem upload, normalização, chave nova, remoção, arquivo inválido, permissões, isolamento A/B, projetos privados/externos, fallback e e-mail com URL absoluta. A homologação visual local cobre desktop/mobile com capa e sem capa.

Rollback de código não requer remover as colunas. Antes de reverter migrações em produção, preservar dados e revisar dependências. Deploy/R2 reais só serão revalidados após merge manual.
