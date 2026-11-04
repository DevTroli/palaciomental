# PM10: mídia persistente e identidade visual dos convites

## Problema e escopo

Alguns templates institucionais interpolavam `identidade.logo` no `src`. Um
`FileField` convertido em texto fornece o nome armazenado, não a URL do storage.
Assim, ativar R2 sozinho não corrige a home, o login e as demais telas afetadas.
Este PR passa a usar `tenant_logo_url`, resolvido por `logo.url`, sem atualizar
nomes de arquivos ou registros no banco.

O backend R2 já existia na main. Esta entrega não cria outro storage, não troca o
armazenamento de estáticos e não adiciona migrações de banco. O bucket público
destina-se exclusivamente a imagens de identidade visual. Não é armazenamento
para anexos privados, documentos ou outros dados protegidos por tenant.

## Alterações de código

- `plataforma/branding.py`: resolução compartilhada do nome público, logo,
  paleta semântica e texto com contraste preto/branco.
- Context processor e remetentes de convites usam a mesma identidade.
- URLs de imagens dos e-mails são absolutas; URLs CDN existentes são mantidas.
- Templates HTML de organização e grupo estendem uma base com marca do tenant,
  papel, destinatário, validade, botão, endereço alternativo e instruções de aceite.
- Rodapé apresenta o Palácio Mental com o logo estático existente.
- Alternativas em texto, tokens, regras de vínculo e aceite POST são preservados.
- Subdomínio `media` reservado por padrão, fora da resolução de tenants.

Nenhuma mensagem é enviada por executar os testes ou publicar este PR.

## Configuração de produção

Valores não secretos da configuração aprovada em 04/11/2026:

```dotenv
R2_ENABLED=True
R2_ACCOUNT_ID=dd0921ce3c5cff7c80d2a43bb9a34fda
R2_BUCKET_NAME=palaciomental-branding-prod
R2_PUBLIC_URL=https://media.palaciomental.com.br
```

`R2_ACCESS_KEY_ID` e `R2_SECRET_ACCESS_KEY` ficam exclusivamente na configuração
protegida do serviço Django. A credencial tem leitura/escrita de objetos somente
nesse bucket, sem permissão de administração geral.

O backend existente usa `location=media`. Portanto o endereço esperado é
`https://media.palaciomental.com.br/media/tenants/<id>/branding/logo/<uuid>.<ext>`.
Não adicionar `/media` ao valor de `R2_PUBLIC_URL`.

O domínio de mídia foi conectado ao bucket mantendo o wildcard institucional.
Acesso público usa domínio próprio; o endpoint público de desenvolvimento r2.dev
permanece desativado. Não é necessário liberar CORS apenas para exibir imagens
em elementos `img`.

O mecanismo de domínio próprio está documentado pela Cloudflare:
https://developers.cloudflare.com/r2/buckets/public-buckets/#custom-domains

## Preservação e evidências

Antes do redeploy de configuração, o runtime apontava `R2_ENABLED=False` e
`FileSystemStorage`. Havia uma logo institucional local, de 57.819 bytes.
Ela foi copiada para o bucket com o mesmo nome relativo, sob o prefixo `media/`,
e o SHA-256 do conteúdo recuperado do R2 foi comparado ao original. O arquivo
local foi mantido, e nenhum registro do banco foi alterado.

A imagem copiada abriu no Comet via HTTPS no domínio de mídia. Essa evidência
comprova a cópia e leitura pública, não substitui o teste de novo upload pela
interface após o merge deste PR.

## Validação

Onze testes adicionais cobrem URL CDN, mídia local em URL absoluta, ausência de
identidade/logo, fallback de cores, contraste, contexto das telas, ambos os
templates HTML e os dois remetentes reais usando backend de e-mail em memória.
Um teste de regressão impede `src="{{ identidade.logo }}"` nos templates afetados.

Após merge e deploy:

- Confirmar backend S3 e existência da logo já preservada pelo storage Django.
- Reenviar uma logo pela gestão, verificar nova chave no R2 e imagem nas telas.
- Confirmar a imagem depois de um novo deploy, sem depender do disco do contêiner.
- Enviar o convite HTML autorizado e verificar entrega, imagens, cadastro e aceite.
- Confirmar isolamento de acesso entre as organizações A e B.

## Reversão e limites

Não desligar R2 cegamente: uploads feitos após a troca estarão no bucket e não no
disco de um novo contêiner. Uma reversão do storage exige copiar esses objetos
para um destino persistente antes de trocar a configuração. Reverter apenas o
layout de e-mail não exige desligar R2.

Arquivos que já desapareceram de contêineres antigos não podem ser recuperados
apenas por habilitar R2. Exigem backup ou novo upload. O banco registra nomes de
arquivos, não seus bytes.

A marca dentro do HTML não configura a foto de perfil do remetente nos clientes
de e-mail; essa apresentação continua uma frente separada.
