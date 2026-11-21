# Jornada institucional

Gere com `node tools/build_postman_institutional.mjs` e importe os dois arquivos
`palacio-mental-institucional.*.json`.

A coleção tem 20 requisições: gestor entra, consulta membros, publica programa,
cria turma com professor e confirma que não pode criar grupo. O aluno entra,
participa da turma aberta, cria grupo, vincula projeto, salva contexto e confirma
o vínculo. O aluno também precisa receber 403 ao acessar a gestão.

Preencha uma cópia privada do environment com as duas contas de teste,
`professor_id`, `allow_writes=true` e
`approved_write_hosts=camppg.palaciomental.com.br`. Execute a coleção inteira,
uma iteração, com cookie jar limpo.

```sh
newman run docs/testing/postman/palacio-mental-institucional.postman_collection.json -e /caminho/privado/institucional.json
postman collection run docs/testing/postman/palacio-mental-institucional.postman_collection.json -e /caminho/privado/institucional.json --no-report-events
```

Esta jornada deixa programa, turma, grupo e projeto privados de teste para
conferência manual; o programa publicado fica visível aos afiliados. Identifique
os IDs e os títulos únicos desta execução antes de remover os dados.

A consulta de membros não comprova envio ou aceite de convite. Envio real exige
destinatário controlado; o aceite exige um convite novo. Esses passos e a atuação
do professor ainda precisam de cenários próprios. Colaboração e isolamento
continuam nas coleções existentes.

Estado: geração e sintaxe verificadas. Esta nova jornada ainda não foi executada
contra o servidor; os resultados anteriores de Newman e Postman CLI correspondem
à coleção que usa turma já existente.
