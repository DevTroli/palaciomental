// Geração determinística. Execute: node tools/build_postman_collection.mjs
import {Builder, status, redirect, csrf, login, form, projectCreated, detailPath, contextFields, deleteStep, assertContext} from "./postman_kit.mjs";

const b = new Builder("palacio-mental", "Palácio Mental · Jornadas do MVP",
  "Fluxo principal do aluno no CAMPPG: projeto vinculado, contexto e privacidade. Isolamento entre tenants é opcional. Leia README.md.");
const add = b.add.bind(b);

b.group("10 - FLUXO DE USO PRINCIPAL", "Aluno do CAMPPG cria projeto vinculado a turma e orientador; negativas de gestão, host e afiliação. Itens do tenant B exigem allow_isolation.", "10.15 · Excluir projeto de teste");
add("10.1 · Formulário de login", "/entrar/", {code: `${status(200, "Login abre")}\n${csrf}`});
add("10.2 · Entrar", "/entrar/", {method: "POST", fields: login("membro_username", "membro_password"),
  code: `${redirect("Login de membro não vai à gestão nem volta ao login", 'pm.expect(path).to.not.match(/^\\/(gestao|entrar)\\//);')}
pm.variables.set("auth_membro", pm.response.code === 302 && !/^\\/(gestao|entrar)\\//.test(path));`});
add("10.3 · Formulário de projeto institucional", "/projetos/novo/", {
  auth: "auth_membro",
  code: `${status(200, "Formulário abre")}
pm.test("Formulário oferece vínculo com turma", () => pm.expect(pm.response.text()).to.include('name="tipo_projeto"'));
${csrf}`,
});
add("10.4 · Membro sem acesso à gestão", "/gestao/identidade/", {
  auth: "auth_membro",
  code: `${status(403, "Membro recebe 403 na identidade institucional")}
pm.test("Resposta explica a restrição", () => pm.expect(pm.response.json().detail).to.be.a("string"));`,
});
add("10.5 · Criar projeto vinculado", "/projetos/novo/", {
  auth: "auth_membro", linked: true, method: "POST",
  fields: form({title: "{{titulo_inst}}", direction: "Verificar vínculo com turma.", status: "ideia", visibility: "privado",
    tipo_projeto: "programa", turma: "{{turma_id}}", orientador: "{{orientador_id}}", grupo: "{{grupo_id}}"}),
  code: projectCreated("project_inst_id"),
});
add("10.6 · Salvar contexto", "/projetos/{{project_inst_id}}/contexto/", {
  auth: "auth_membro", need: "project_inst_id", method: "POST", fields: contextFields(),
  code: redirect("Contexto salvo e retorno ao detalhe", `pm.expect(path).to.eql(${detailPath("project_inst_id")});`),
});
add("10.7 · Projeto vinculado persistido", "/projetos/{{project_inst_id}}/contexto/", {
  auth: "auth_membro", need: "project_inst_id", code: `(${assertContext.toString()})();\n${csrf}`,
});
const leak = `pm.test("Título não vazou", () => pm.expect(pm.response.text()).not.to.include(pm.variables.get("titulo_inst")));`;
add("10.8 · Projeto institucional no host global", "/projetos/{{project_inst_id}}/", {
  base: "global_base", need: "project_inst_id", code: `${status(404, "Projeto institucional não existe no escopo global")}\n${leak}`,
});
add("10.9 · Tenant inexistente", "/entrar/", {
  base: "missing_tenant_base",
  code: `${status(404, "Subdomínio sem organização responde 404")}
pm.test("Sem queda para o ambiente global", () => pm.expect(pm.response.text()).to.include("Ambiente institucional não encontrado"));`,
});
add("10.10 · Formulário de login no tenant B", "/entrar/", {base: "tenant_b_base", gate: "allow_isolation", need: "project_inst_id", code: `${status(200, "Login do tenant B abre")}\n${csrf}`});
add("10.11 · Entrar como membro do tenant B", "/entrar/", {
  base: "tenant_b_base", gate: "allow_isolation", need: "project_inst_id", method: "POST", fields: login("membro_b_username", "membro_b_password"),
  code: `${redirect("Login do membro B conclui", 'pm.expect(path).to.not.match(/^\\/entrar\\//);')}
pm.variables.set("auth_b", pm.response.code === 302);`,
});
add("10.12 · Projeto do tenant A no tenant B", "/projetos/{{project_inst_id}}/", {
  base: "tenant_b_base", gate: "allow_isolation", auth: "auth_b", need: "project_inst_id",
  code: `${status(404, "Afiliado de B não encontra projeto de A")}\n${leak}`,
});
add("10.13 · Formulário de login para conta sem afiliação", "/entrar/", {base: "tenant_b_base", gate: "allow_isolation", need: "project_inst_id", code: `${status(200, "Login do tenant B abre")}\n${csrf}`});
add("10.14 · Conta sem afiliação", "/entrar/", {
  base: "tenant_b_base", gate: "allow_isolation", need: "project_inst_id", method: "POST", fields: login("sem_afiliacao_username", "sem_afiliacao_password"),
  code: status(403, "Autenticação sem afiliação ativa recebe 403"),
});
add("10.15 · Excluir projeto de teste", "/projetos/{{project_inst_id}}/excluir/", {auth: "auth_membro", fail: null, ...deleteStep("project_inst_id")});

b.write("palacio-mental", {
  global_base: "https://palaciomental.com.br", tenant_a_base: "https://camppg.palaciomental.com.br",
  tenant_b_base: "https://homolog-b.palaciomental.com.br", missing_tenant_base: "https://qa-inexistente.palaciomental.com.br",
  allow_writes: "false", approved_write_hosts: "", allow_isolation: "false",
  sem_afiliacao_username: "", sem_afiliacao_password: "", membro_username: "", membro_password: "", membro_b_username: "", membro_b_password: "",
  turma_id: "", orientador_id: "", grupo_id: "",
}, ["sem_afiliacao_password", "membro_password", "membro_b_password"], {
  flags: ["auth_membro", "auth_b"], ids: ["project_inst_id"],
  titles: {titulo_inst: "inst"},
}, "P.M · Jornadas do MVP");
