# Jornada institucional

Gere com `node tools/build_postman_institutional.mjs` e importe os dois arquivos
`palacio-mental-institucional.*.json`.

A coleção tem 29 requisições: gestor entra, consulta membros, publica programa,
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

A limpeza remove projeto, grupo, turma e programa, nessa ordem. A última
requisição confirma HTTP 404 para o programa. Uma falha pode deixar resíduos;
confira somente os IDs criados pela rodada antes de qualquer remoção manual.

A consulta de membros não comprova envio ou aceite de convite. Envio real exige
destinatário controlado; o aceite exige um convite novo. Esses passos e a atuação
do professor ainda precisam de cenários próprios. Colaboração e isolamento
continuam nas coleções existentes.

Validada em 22/11/2026 com Newman e Postman CLI: 29 requisições e 50
asserções por ferramenta, sem falhas. Consulte os relatórios no README principal.
