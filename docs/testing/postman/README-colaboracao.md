# Outras pastas: colaboração pública

Execute o gerador `node tools/build_postman_collaboration.mjs` e importe os arquivos `palacio-mental-colaboracao.postman_collection.json` e `palacio-mental-colaboracao.postman_environment.json` no Postman.

Esta coleção permanece opcional e separada do percurso institucional prioritário. Tem 23 requisições: publicação, colaborador, decisão e encerramento. Não contém a pasta de homologação removida do escopo.

## Preparação

Duas contas sintéticas distintas, sem privilégios administrativos: autor e colaborador. Configure em cópia privada do environment `autor_username`, `autor_password`, `colab_username`, `colab_password`. Se o colaborador tiver nome completo, informe exatamente esse nome em `colab_display_name`, pois o template prefere nome completo ao username na equipe.

Ative `allow_writes=true` e aprove somente o hostname HTTPS efetivamente usado em `approved_write_hosts`. Não exporte nem versione senhas preenchidas. O modo sensível mascara o valor; não torna seguro compartilhar o arquivo.

## Newman

```sh
newman run docs/testing/postman/palacio-mental-colaboracao.postman_collection.json \
  -e /caminho/privado/colaboracao.json --delay-request 300
```

## Interface web

Importe coleção e environment, selecione a cópia privada e execute a coleção inteira no Runner, uma iteração, sem cookies de sessões anteriores. Não execute pastas isoladas: elas dependem do projeto criado na primeira pasta e das trocas de identidade.

## Provas

- Autor recebe 403 ao comentar e votar no próprio projeto.
- Busca encontra o projeto sintético pelo título.
- Comentário único reaparece no detalhe.
- Contador de relevância aumenta de zero para um.
- Pedido é identificado pelo username e mensagem única, não pelo primeiro formulário de decisão da página.
- Aceite usa `decision=aceita`; participante aparece em uma linha da equipe com papel Colaborador e o pedido deixa de estar pendente.
- Encerramento confirma o título exato no formulário de edição antes do POST de exclusão.

Não se depende mais do marco textual Contexto atualizado no detalhe. Não aumentamos a quantidade de requisições.

## Efeitos e limites

O projeto passa de privado a público durante a execução e pode aparecer na descoberta e ranking; não há duração garantida. Comentário, voto, afiliação ao projeto e notificações são efeitos reais. Excluir o projeto não garante apagar notificações nem efeitos de cache.

Não usar contas reais para produção. Autorizar o commit não autoriza executar esta jornada em produção. Uma falha de transporte ou autenticação pode impedir a limpeza; confira IDs antes de qualquer remoção manual. Não apague somente por prefixo de título.

As asserções foram alinhadas ao template versionado, não homologadas no deployment. Uma falha pode indicar divergência de versão, dados inválidos, defeito do produto ou da coleção; investigar antes de ajustar a expectativa.
