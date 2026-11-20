// Geração determinística. Execute: node tools/build_postman_collection.mjs
import {createHash} from "node:crypto";
import {mkdirSync, writeFileSync} from "node:fs";

const out = "docs/testing/postman";
mkdirSync(out, {recursive: true});
const id = name => {
  const h = createHash("sha256").update(`palacio-mental:${name}`).digest("hex");
  return `${h.slice(0,8)}-${h.slice(8,12)}-4${h.slice(13,16)}-a${h.slice(17,20)}-${h.slice(20,32)}`;
};
const script = (listen, code) => ({listen, script: {type: "text/javascript", exec: code.split("\n")}});
const folders = [];
let folder;
function group(name, description) {
  folder = {name, description, item: []};
  folders.push(folder);
}
// auth: variável de sessão exigida; need: variável de projeto exigida; gate: flag opcional do environment.
function add(name, path, {method = "GET", fields, code = "", gate = "", auth = "", need = "", base = "tenant_a_base"} = {}) {
  const pre = [
    gate ? `if (pm.environment.get("${gate}") !== "true") pm.execution.skipRequest();` : "",
    auth ? `if (pm.variables.get("${auth}") !== true) pm.execution.skipRequest();` : "",
    need ? `if (!pm.variables.get("${need}")) pm.execution.skipRequest();` : "",
  ].filter(Boolean).join("\n");
  folder.item.push({
    id: id(name), name,
    request: {
      method, url: `{{${base}}}${path}`,
      header: method === "POST" ? [
        {key: "Origin", value: `{{${base}}}`},
        {key: "Referer", value: `{{${base}}}/`},
      ] : [],
      ...(fields ? {body: {mode: "urlencoded", urlencoded: Object.entries(fields).map(([key, value]) => ({key, value, type: "text"}))}} : {}),
    },
    protocolProfileBehavior: {followRedirects: false},
    event: [script("prerequest", pre), script("test", code)],
  });
}

// Blocos reutilizados nas asserções.
const status = (code, label) => `pm.test("${label}", () => pm.response.to.have.status(${code}));`;
const where = 'const path = (pm.response.headers.get("Location") || "").replace(/^https?:\\/\\/[^/]+/, "");';
const redirect = (label, check = "") => `${where}
pm.test("${label}", () => { pm.expect(pm.response.code).to.eql(302); ${check} });
if (pm.response.code !== 302) pm.execution.setNextRequest(null);`;
const csrf = `const match = pm.response.text().match(/name=["']csrfmiddlewaretoken["'][^>]*value=["']([^"']+)/);
pm.test("CSRF presente", () => pm.expect(match).not.to.equal(null));
if (!match) pm.execution.setNextRequest(null); else pm.variables.set("csrf", match[1]);`;
const token = "{{csrf}}";
const login = (user, pass) => ({csrfmiddlewaretoken: token, username: `{{${user}}}`, password: `{{${pass}}}`});
const projectId = target => `${redirect("Projeto criado e destino de contexto correto", 'pm.expect(path).to.match(/^\\/projetos\\/\\d+\\/contexto\\/$/);')}
const created = path.match(/^\\/projetos\\/(\\d+)\\/contexto\\/$/);
if (created) pm.variables.set("${target}", created[1]); else pm.execution.setNextRequest(null);`;
const contextFields = {
  csrfmiddlewaretoken: token, category: "QA-PM", tags: "qa,postman", visibility: "privado",
  "links-TOTAL_FORMS": "0", "links-INITIAL_FORMS": "0", "links-MIN_NUM_FORMS": "0", "links-MAX_NUM_FORMS": "1000",
};
const persisted = (titleVar, extra = "") => `${status(200, "Detalhe abre")}
const html = pm.response.text();
pm.test("Título do projeto presente", () => pm.expect(html).to.include(pm.variables.get("${titleVar}")));
pm.test("Marco automático do contexto presente", () => pm.expect(html).to.include("Contexto atualizado"));${extra}`;

group("00 · Pré-condições", "Destino acessível e tenant de teste identificado. Sem login.");
add("00.1 · Aplicação pronta", "/pronto", {
  base: "global_base",
  code: `${status(200, "Prontidão responde 200")}
pm.test("Banco e migrations ok", () => pm.expect(pm.response.json().status).to.eql("ok"));`,
});
add("00.2 · Tenant A identificado", "/entrar/", {
  code: `${status(200, "Login do tenant A abre")}
pm.test("Marca de login institucional", () => pm.expect(pm.response.text()).to.include('data-status-probe="organizacao"'));`,
});

group("10 · Público e pessoal", "Autor pessoal cria projeto privado, salva contexto e relê. Host global.");
add("10.1 · Formulário de login", "/entrar/", {base: "global_base", code: `${status(200, "Login global abre")}\n${csrf}`});
add("10.2 · Entrar como autor pessoal", "/entrar/", {
  base: "global_base", method: "POST", fields: login("pessoal_username", "pessoal_password"),
  code: `${redirect("Login redireciona para a lista de projetos", 'pm.expect(path).to.eql("/projetos/");')}
pm.variables.set("auth_pessoal", pm.response.code === 302 && path === "/projetos/");`,
});
add("10.3 · Formulário de projeto", "/projetos/novo/", {base: "global_base", auth: "auth_pessoal", code: `${status(200, "Formulário abre")}\n${csrf}`});
add("10.4 · Criar projeto privado", "/projetos/novo/", {
  base: "global_base", auth: "auth_pessoal", method: "POST",
  fields: {csrfmiddlewaretoken: token, title: "{{titulo_pessoal}}", direction: "Verificar criação e contexto de projeto pessoal.", status: "ideia", visibility: "privado"},
  code: projectId("project_pessoal_id"),
});
add("10.5 · Formulário de contexto", "/projetos/{{project_pessoal_id}}/contexto/", {base: "global_base", auth: "auth_pessoal", need: "project_pessoal_id", code: `${status(200, "Contexto abre")}\n${csrf}`});
add("10.6 · Salvar contexto", "/projetos/{{project_pessoal_id}}/contexto/", {
  base: "global_base", auth: "auth_pessoal", need: "project_pessoal_id", method: "POST", fields: contextFields,
  code: redirect("Contexto salvo e retorno ao detalhe", 'pm.expect(path).to.eql("/projetos/" + pm.variables.get("project_pessoal_id") + "/");'),
});
add("10.7 · Contexto persistido", "/projetos/{{project_pessoal_id}}/", {base: "global_base", auth: "auth_pessoal", need: "project_pessoal_id", code: persisted("titulo_pessoal")});

group("20 · Organização", "Membro do tenant A cria projeto vinculado a turma e orientador. Exige a preparação descrita no README.");
add("20.1 · Formulário de login", "/entrar/", {code: `${status(200, "Login do tenant A abre")}\n${csrf}`});
add("20.2 · Entrar como membro", "/entrar/", {
  method: "POST", fields: login("membro_username", "membro_password"),
  code: `${redirect("Login de membro não vai à gestão nem volta ao login", 'pm.expect(path).to.not.match(/^\\/(gestao|entrar)\\//);')}
pm.variables.set("auth_membro", pm.response.code === 302 && !/^\\/(gestao|entrar)\\//.test(path));`,
});
add("20.3 · Membro sem acesso à gestão", "/gestao/identidade/", {
  auth: "auth_membro",
  code: `${status(403, "Membro recebe 403 na identidade institucional")}
pm.test("Resposta explica a restrição", () => pm.expect(pm.response.json().detail).to.be.a("string"));`,
});
add("20.4 · Formulário de projeto institucional", "/projetos/novo/", {
  auth: "auth_membro",
  code: `${status(200, "Formulário abre")}
pm.test("Formulário oferece vínculo com turma", () => pm.expect(pm.response.text()).to.include('name="tipo_projeto"'));
${csrf}`,
});
add("20.5 · Criar projeto vinculado", "/projetos/novo/", {
  auth: "auth_membro", method: "POST",
  fields: {
    csrfmiddlewaretoken: token, title: "{{titulo_inst}}", direction: "Verificar projeto vinculado a turma e orientador.", status: "ideia", visibility: "privado",
    tipo_projeto: "programa", turma: "{{turma_id}}", orientador: "{{orientador_id}}", grupo: "{{grupo_id}}",
  },
  code: projectId("project_inst_id"),
});
add("20.6 · Formulário de contexto", "/projetos/{{project_inst_id}}/contexto/", {auth: "auth_membro", need: "project_inst_id", code: `${status(200, "Contexto abre")}\n${csrf}`});
add("20.7 · Salvar contexto", "/projetos/{{project_inst_id}}/contexto/", {
  auth: "auth_membro", need: "project_inst_id", method: "POST", fields: contextFields,
  code: redirect("Contexto salvo e retorno ao detalhe", 'pm.expect(path).to.eql("/projetos/" + pm.variables.get("project_inst_id") + "/");'),
});
add("20.8 · Projeto vinculado persistido", "/projetos/{{project_inst_id}}/", {
  auth: "auth_membro", need: "project_inst_id",
  code: persisted("titulo_inst", `
if (pm.environment.get("turma_nome")) pm.test("Turma vinculada aparece no detalhe", () => pm.expect(html).to.include(pm.environment.get("turma_nome")));`),
});

group("30 · Privacidade", "Cada negativa declara quem pede, onde e qual resposta a regra produz.");
add("30.1 · Tenant inexistente", "/entrar/", {
  base: "missing_tenant_base",
  code: `${status(404, "Subdomínio sem organização responde 404")}
pm.test("Sem queda para o ambiente global", () => pm.expect(pm.response.text()).to.include("Ambiente institucional não encontrado"));`,
});
add("30.2 · Projeto institucional no host global", "/projetos/{{project_inst_id}}/", {
  base: "global_base", auth: "auth_pessoal", need: "project_inst_id",
  code: `${status(404, "Projeto institucional não existe no escopo global")}
pm.test("Título não vazou", () => pm.expect(pm.response.text()).not.to.include(pm.variables.get("titulo_inst")));`,
});
add("30.3 · Formulário de login para conta sem afiliação", "/entrar/", {need: "project_inst_id", code: `${status(200, "Login do tenant A abre")}\n${csrf}`});
add("30.4 · Conta autenticada sem afiliação", "/entrar/", {
  need: "project_inst_id", method: "POST", fields: login("pessoal_username", "pessoal_password"),
  code: `${status(403, "Autenticação sem afiliação ativa recebe 403")}
pm.variables.set("auth_membro", false);`,
});
add("30.5 · Projeto institucional sem afiliação", "/projetos/{{project_inst_id}}/", {
  need: "project_inst_id",
  code: `${status(403, "Conta sem afiliação não abre o projeto")}
pm.test("Título não vazou", () => pm.expect(pm.response.text()).not.to.include(pm.variables.get("titulo_inst")));`,
});
add("30.6 · Formulário de login no tenant B", "/entrar/", {base: "tenant_b_base", gate: "allow_isolation", need: "project_inst_id", code: `${status(200, "Login do tenant B abre")}\n${csrf}`});
add("30.7 · Entrar como membro do tenant B", "/entrar/", {
  base: "tenant_b_base", gate: "allow_isolation", need: "project_inst_id", method: "POST", fields: login("membro_b_username", "membro_b_password"),
  code: `${redirect("Login do membro B conclui", 'pm.expect(path).to.not.match(/^\\/entrar\\//);')}
pm.variables.set("auth_b", pm.response.code === 302);`,
});
add("30.8 · Projeto do tenant A no tenant B", "/projetos/{{project_inst_id}}/", {
  base: "tenant_b_base", gate: "allow_isolation", auth: "auth_b", need: "project_inst_id",
  code: `${status(404, "Afiliado de B não encontra projeto de A")}
pm.test("Título não vazou", () => pm.expect(pm.response.text()).not.to.include(pm.variables.get("titulo_inst")));`,
});

function blockRequest(label, message) {
  pm.execution.setNextRequest(null);
  pm.test(label, () => pm.expect.fail(message));
  pm.execution.skipRequest();
}
function guardWrite(enabled) {
  if (pm.request.method === "GET") return true;
  if (!enabled("allow_writes")) {
    pm.execution.skipRequest();
    return false;
  }
  const target = pm.variables.replaceIn(pm.request.url.toString());
  const host = ((target.match(/^https?:\/\/([^/]+)/i) || [])[1] || "").toLowerCase();
  const approved = (pm.environment.get("approved_write_hosts") || "").toLowerCase().split(",").map(item => item.trim()).filter(Boolean);
  if (!host || !approved.includes(host)) {
    blockRequest("Host de escrita aprovado", "Escrita bloqueada: host não aprovado explicitamente.");
    return false;
  }
  return true;
}
function guard() {
  const enabled = name => pm.environment.get(name) === "true";
  if (pm.info.requestName.startsWith("00.1")) {
    for (const key of ["auth_pessoal", "auth_membro", "auth_b"]) pm.variables.set(key, false);
    for (const key of ["project_pessoal_id", "project_inst_id"]) pm.variables.set(key, "");
    const run = Date.now();
    pm.variables.set("titulo_pessoal", `QA-PM pessoal ${run}`);
    pm.variables.set("titulo_inst", `QA-PM institucional ${run}`);
  }
  guardWrite(enabled);
}
const guards = [blockRequest, guardWrite].map(fn => fn.toString()).join("\n");
const collection = {
  info: {
    _postman_id: id("collection"), name: "Palácio Mental · Jornadas do MVP",
    schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    description: "Jornadas HTTP do MVP contra formulários reais do Django. Escritas desligadas por padrão e limitadas a hosts aprovados. Leia README.md. Sem credenciais, cookies ou tokens neste arquivo.",
  },
  event: [script("prerequest", `${guards}\n(${guard.toString()})();`)],
  item: folders,
};
const defaults = {
  global_base: "https://palaciomental.com.br",
  tenant_a_base: "https://homolog-a.palaciomental.com.br",
  tenant_b_base: "https://homolog-b.palaciomental.com.br",
  missing_tenant_base: "https://qa-inexistente.palaciomental.com.br",
  allow_writes: "false", approved_write_hosts: "", allow_isolation: "false",
  pessoal_username: "", pessoal_password: "",
  membro_username: "", membro_password: "",
  membro_b_username: "", membro_b_password: "",
  turma_id: "", orientador_id: "", grupo_id: "", turma_nome: "",
};
const secrets = new Set(["pessoal_password", "membro_password", "membro_b_password"]);
const env = {
  id: id("environment"), name: "Palácio Mental · Seguro por padrão", _postman_variable_scope: "environment",
  values: Object.entries(defaults).map(([key, value]) => ({key, value, enabled: true, type: secrets.has(key) ? "secret" : "default"})),
};
writeFileSync(`${out}/palacio-mental.postman_collection.json`, JSON.stringify(collection, null, 2) + "\n");
writeFileSync(`${out}/palacio-mental.postman_environment.json`, JSON.stringify(env, null, 2) + "\n");
console.log(`${folders.length} pastas, ${folders.reduce((sum, f) => sum + f.item.length, 0)} requisições.`);
