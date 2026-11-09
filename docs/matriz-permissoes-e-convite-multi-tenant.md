# Permissões institucionais

O acesso exige organização ativa, login e afiliação ativa no tenant do hostname. A matriz descreve o portal institucional; o Admin técnico exige autorização interna separada.

| Ação | Proprietário | Gestor | Professor autorizado | Membro |
|---|---:|---:|---:|---:|
| Entrar no tenant | Sim | Sim | Sim | Sim |
| Acessar `/gestao/` | Sim | Sim | Não por padrão | Não |
| Criar programa | Sim | Sim | Não | Não |
| Criar turma | Sim | Sim | Não | Não |
| Criar grupo em turma atribuída | Sim | Sim | Sim | Conforme política da turma |
| Criar projeto institucional vinculado | Sim | Sim | Sim | Sim |
| Emitir convite de grupo | Sim | Sim | Apenas grupo autorizado | Não |
| Alterar afiliações e papéis | Sim | Sim | Não | Não |
| Conceder proprietário | Sim | Não | Não | Não |
| Suspender a própria afiliação | Não | Não | Não | Não |
| Remover o último proprietário ativo | Não | Não | Não | Não |

O papel de professor não é um papel de mentor separado. No MVP, professor exerce orientação quando é responsável pela turma/grupo ou quando possui vínculo local de professor ativo naquele grupo.


## Regras permanentes

- O tenant de projetos e eventos é definido pelo servidor, nunca pelo POST.
- Projetos pessoais não entram na vitrine institucional; projetos institucionais não entram na vitrine global.
- Projetos privados ficam restritos ao proprietário. Gestão recebe agregados, sem conteúdo privado de outros autores.
- Colaboração exige aprovação do proprietário. No aceite, o solicitante deve continuar afiliado e ativo.
- Convites têm token aleatório, hash persistido, prazo e estado. Aceite valida o hostname, o e-mail e a disponibilidade da turma/grupo em transação.
- Convite de grupo não concede papel institucional privilegiado.
- Turmas podem exigir convite, aprovação ou permitir entrada direta; encerramento bloqueia novas entradas.
- Proprietário/gestor publica atividades para afiliados ativos. O destinatário registra entrega, mas não edita ou exclui a atividade institucional.
- Compromissos pessoais da agenda só podem ser mantidos pelo próprio participante, no tenant correto.
- Alterar a interface, ocultar um botão ou falhar o cache nunca modifica essas permissões.
