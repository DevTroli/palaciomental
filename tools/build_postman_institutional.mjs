// node tools/build_postman_institutional.mjs
import {Builder, status, redirect, csrf, login, form, projectCreated, contextFields} from './postman_kit.mjs';

const b = new Builder('palacio-mental-institucional', 'CAMPPG · Gestor e aluno',
  'Programa, turma, participação, grupo e projeto. Use contas de teste e execute em ordem.');
let role = 'gestor';
const add = (name, path, options = {}) => b.add(name, path, {auth: `auth_${role}`, ...options});
const ok = `${status(200, 'Página disponível')}\n${csrf}`;
const program = '/programas/{{program_id}}/';
const changed = redirect('Alteração aceita');
function session(prefix, nextRole) {
  role = nextRole;
  add(`${prefix}.1 · Login ${role}`, '/entrar/', {auth: '', code: ok});
  add(`${prefix}.2 · Entrar ${role}`, '/entrar/', {auth: '', method: 'POST', fields: login(`${role}_username`, `${role}_password`), code: `${changed}
const valid = pm.response.code === 302 && path === '${role === 'gestor' ? '/gestao/' : '/'}';
pm.test('Destino corresponde ao papel', () => pm.expect(valid).to.eql(true));
pm.variables.set('auth_${role}', valid);
if (!valid) pm.execution.setNextRequest(null);`});
}
function capture(pattern, key) {
  return `${status(200, 'Estrutura disponível')}
const found = pm.response.text().match(${pattern});
pm.test('ID da estrutura criada presente', () => pm.expect(Boolean(found)).to.eql(true));
if (found) pm.variables.set('${key}', found[1]); else pm.execution.setNextRequest(null);
${csrf}`;
}

b.group('10 · Gestor', 'Cria programa publicado e turma aberta com professor responsável.');
session('10', 'gestor');
add('10.3 · Gestão e convites', '/gestao/membros/', {code: ok});
add('10.4 · Criar programa', '/programas/novo/', {method: 'POST', fields: form({nome:'{{titulo_programa}}', descricao:'Programa de teste HTTP.', status:'publicado'}), code: String.raw`${changed}
const match = path.match(/^\/programas\/([a-f0-9-]+)\/$/);
pm.test('Programa criado', () => pm.expect(Boolean(match)).to.eql(true));
if (match) pm.variables.set('program_id', match[1]); else pm.execution.setNextRequest(null);`});
add('10.5 · Formulário da turma', '/gestao/programas/{{program_id}}/turmas/novo/', {need:'program_id', code:`${ok}
const professor = pm.environment.get('professor_id');
const valid = Boolean(professor) && pm.response.text().includes('value="' + professor + '"');
pm.test('Professor selecionado disponível', () => pm.expect(valid).to.eql(true));
if (!valid) pm.execution.setNextRequest(null);`});
add('10.6 · Criar turma com professor', '/gestao/programas/{{program_id}}/turmas/novo/', {need:'program_id', method:'POST', fields:form({nome:'{{titulo_turma}}', descricao:'Turma de teste HTTP.', professor_responsavel:'{{professor_id}}', politica_participacao:'aberta', status:'ativo'}), code:changed});
add('10.7 · Confirmar turma', program, {need:'program_id', code:capture('/id="turma-([a-f0-9-]+)"/', 'class_id')});
add('10.8 · Gestor não cria grupo', '/turmas/{{class_id}}/grupos/novo/', {need:'class_id', code:status(403,'Grupo reservado ao aluno participante')});
add('10.9 · Sair do gestor', '/sair/', {method:'POST', fields:form(), code:changed});

b.group('20 · Aluno', 'Participa da turma e cria seu grupo antes de vincular o projeto.');
session('20','aluno');
add('20.3 · Consultar programa publicado', program, {need:'class_id', code:ok});
add('20.4 · Participar da turma', '/turmas/{{class_id}}/participar/', {need:'class_id', method:'POST', fields:form(), code:changed});
add('20.5 · Criar grupo', '/turmas/{{class_id}}/grupos/novo/', {need:'class_id', method:'POST', fields:form({nome:'{{titulo_grupo}}', descricao:'Grupo de teste HTTP.', status:'ativo', aberto_para_entrada:'on'}), code:changed});
add('20.6 · Confirmar grupo', program, {need:'class_id', code:capture(String.raw`/href="\/grupos\/([a-f0-9-]+)\/membros\/"/`, 'group_id')});
add('20.7 · Novo projeto', '/projetos/novo/', {need:'group_id', code:ok});
add('20.8 · Criar projeto vinculado', '/projetos/novo/', {need:'group_id', method:'POST', fields:form({title:'{{titulo_projeto}}', direction:'Validar jornada institucional.', status:'ideia', visibility:'privado', tipo_projeto:'programa', turma:'{{class_id}}', grupo:'{{group_id}}', orientador:'{{professor_id}}'}), code:projectCreated('project_id')});
add('20.9 · Salvar contexto', '/projetos/{{project_id}}/contexto/', {need:'project_id', method:'POST', fields:contextFields(), code:changed});
add('20.10 · Confirmar projeto e vínculo', '/projetos/{{project_id}}/', {need:'project_id', code:`${ok}
for (const key of ['titulo_projeto','titulo_turma','titulo_grupo']) pm.test(key + ' presente', () => pm.expect(pm.response.text()).to.include(pm.variables.get(key)));`});
add('20.11 · Aluno sem gestão', '/gestao/membros/', {code:status(403,'Aluno não gerencia afiliações')});

b.group('30 · Limpeza', 'Remove somente os IDs criados nesta execução, na ordem das dependências.');
add('30.1 · Excluir projeto de teste', '/projetos/{{project_id}}/excluir/', {need:'project_id', method:'POST', fields:form(), code:changed});
add('30.2 · Excluir grupo de teste', '/grupos/{{group_id}}/excluir/', {need:'group_id', method:'POST', fields:form(), code:changed});
add('30.3 · Sair do aluno', '/sair/', {method:'POST', fields:form(), code:changed});
session('31','gestor');
add('31.3 · Renovar CSRF', program, {need:'program_id', code:ok});
add('31.4 · Excluir turma de teste', '/turmas/{{class_id}}/excluir/', {need:'class_id', method:'POST', fields:form(), code:changed});
add('31.5 · Excluir programa de teste', '/programas/{{program_id}}/excluir/', {need:'program_id', method:'POST', fields:form(), code:changed});
add('31.6 · Confirmar exclusão', program, {need:'program_id', code:status(404,'Programa de teste removido')});

b.write('palacio-mental-institucional', {
  tenant_a_base:'https://camppg.palaciomental.com.br', allow_writes:'false', approved_write_hosts:'',
  gestor_username:'', gestor_password:'', aluno_username:'', aluno_password:'', professor_id:'',
}, ['gestor_password','aluno_password'], {
  flags:['auth_gestor','auth_aluno'], ids:['program_id','class_id','group_id','project_id'],
  titles:{titulo_programa:'programa',titulo_turma:'turma',titulo_grupo:'grupo',titulo_projeto:'projeto'},
}, "CAMP-PG · Gestor e aluno");
