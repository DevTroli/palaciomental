# Postman · CAMPPG

Edite e execute os testes no workspace **PalacioMental** do Postman web.
Os JSONs deste diretório são cópias versionadas para revisão e recuperação.

| Coleção | Fluxo | Environment |
|---|---|---|
| CAMPPG · Gestor e aluno | Gestor cria programa e turma; aluno participa, cria grupo e projeto; limpeza | CAMP-PG · Gestor e aluno |
| Palácio Mental · Jornadas do MVP | Aluno cria projeto vinculado, salva contexto e verifica privacidade | P.M · Jornadas do MVP |
| CAMPPG - Colaboração | Troli publica; Carvalho comenta, vota e solicita participação; Troli aceita e exclui | CAMP-PG · Colaboração |

## Executar na web

1. Abra **Environments** e selecione o ambiente da coleção. Preencha os valores
   locais; marque senhas como sensíveis e não compartilhe seus valores.
2. Nos três ambientes, configure `tenant_a_base=https://camppg.palaciomental.com.br`,
   `allow_writes=true` e `approved_write_hosts=camppg.palaciomental.com.br`.
3. Preencha os campos específicos abaixo. Use contas de teste afiliadas ao CAMPPG.
4. Abra a coleção → **Run → Functional → Local**. Selecione o environment,
   Desktop Agent, uma iteração e atraso de **300 ms**. Execute a coleção inteira.

| Environment | Campos específicos |
|---|---|
| Gestor e aluno | `gestor_username/password`, `aluno_username/password`, `professor_id` |
| Jornadas do MVP | `membro_username/password`, `turma_id`, `orientador_id`; `grupo_id` opcional |
| Colaboração | `autor_username/password` (Troli), `colab_username/password` (Carvalho), `colab_display_name` |

`professor_id` e `orientador_id` são IDs numéricos; `turma_id` é UUID. O aluno
precisa participar da turma. Na jornada principal, mantenha `allow_isolation=false`:
cinco passos de outro tenant serão pulados. A consulta ao host global verifica
que o projeto institucional responde 404 fora do CAMPPG.

As rodadas validadas tiveram 50, 19 e 37 asserções, respectivamente. Itens pulados
não contam como aprovados. Falhas podem impedir a limpeza: confira os IDs da
rodada antes de remover dados. Convites por e-mail não fazem parte desta suíte.

## GitHub Actions e manutenção

Após o merge, abra **Actions → Postman · Jornadas do MVP → Run workflow**, escolha
`main` e autorize os dados de teste. O workflow executa as três coleções atuais
pelos IDs do workspace e publica os relatórios no Postman. Não sobrescreve as
edições da web e não roda contra produção automaticamente em PRs ou pushes.

A automação usa `POSTMAN_API_KEY` e `POSTMAN_TEST_ENV` nos secrets do GitHub. O
segundo contém `gestor_username`, `gestor_password`, `aluno_username`,
`aluno_password`, `professor_id`, `turma_id`, `orientador_id`, `colab_username`,
`colab_password` e `colab_display_name`. Atualize o secret ao trocar contas ou
IDs. O script cria environments temporários privados e os remove ao terminar.

Após editar e validar na web, exporte a coleção em **Collection v2.1** para o
respectivo `*.postman_collection.json`. Atualize os modelos de environment
somente com valores públicos e credenciais vazias. Não versione exports com
senhas, cookies ou tokens. Se recriar uma coleção, atualize seu ID em
`tools/run_postman_cloud.py`.

O CI comum verifica a automação com testes locais, sem acessar o CAMPPG.
As execuções manuais usam a versão disponível na web naquele momento; os JSONs
registram a versão exportada, não congelam o conteúdo das futuras execuções.
