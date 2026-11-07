// Geração determinística. Execute: node tools/build_postman_collection.mjs
import {createHash} from "node:crypto";
import {mkdirSync, writeFileSync} from "node:fs";
import {readIdentity} from "./postman_identity.mjs";

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
function add(name, path, {method = "GET", fields, files, code = "", gate = "", auth = true, project = false, base = "tenant_a_base", description = ""} = {}) {
  const pre = [
    gate ? `if (pm.environment.get("${gate}") !== "true") pm.execution.skipRequest();` : "",
    auth ? 'if (pm.variables.get("auth_ready") !== true) pm.execution.skipRequest();' : "",
    project ? 'if (!pm.variables.get("project_id")) pm.execution.skipRequest();' : "",
  ].filter(Boolean).join("\n");
  folder.item.push({
    id: id(name), name,
    description: description || name,
    request: {
      method, url: `{{${base}}}${path}`,
      description: description || name,
      header: method === "POST" ? [
        {key: "Origin", value: `{{${base}}}`},
        {key: "Referer", value: `{{${base}}}/`},
      ] : [],
      ...(fields ? {body: files
        ? {mode: "formdata", formdata: [
          ...Object.entries(fields).map(([key, value]) => ({key, value, type: "text"})),
          ...Object.entries(files).map(([key, src]) => ({key, src, type: "file"})),
        ]}
        : {mode: "urlencoded", urlencoded: Object.entries(fields).map(([key, value]) => ({key, value, type: "text"}))}} : {}),
    },
    protocolProfileBehavior: {followRedirects: false},
    event: [script("prerequest", pre), script("test", code)],
  });
}
const ok = 'pm.test("HTTP 200", () => pm.response.to.have.status(200));';
const redirect = 'pm.test("Redireciona após POST válido", () => pm.response.to.have.status(302)); if (pm.response.code !== 302) pm.execution.setNextRequest(null);';
const csrf = `const match = pm.response.text().match(/name=["']csrfmiddlewaretoken["'][^>]*value=["']([^"']+)/);
pm.test("CSRF presente", () => pm.expect(match).not.to.equal(null));
if (!match) pm.execution.setNextRequest(null); else pm.variables.set("csrf", match[1]);`;
const token = "{{csrf}}";
const captureIdentity = `
pm.variables.unset("identity_snapshot");
const identity = (${readIdentity.toString()})(pm.response.text());
pm.variables.set("identity_snapshot", JSON.stringify(identity));
for (const [key, value] of Object.entries(identity)) pm.variables.set("identity_" + key, value);
pm.test("Snapshot de identidade completo", () => pm.expect(Object.keys(identity)).to.have.lengthOf(10));`;
const preserved = Object.fromEntries(["nome_exibicao", "apresentacao", "cor_primaria", "cor_destaque", "cor_fundo"].map(key => [key, "{{identity_" + key + "}}"]));

group("01 · Sessão e entrada", "Execute a coleção inteira no Runner/Newman, em ordem. A senha fica no environment local e não é exportada neste repositório.");
add("01.1 · Login institucional e CSRF", "/entrar/", {
  auth: false, code: `${ok}\n${csrf}`,
});
add("01.2 · Autenticar gestor de teste", "/entrar/", {
  auth: false, method: "POST",
  fields: {csrfmiddlewaretoken: token, username: "{{username}}", password: "{{password}}", next: "/"},
  code: `${redirect}\npm.variables.set("auth_ready", pm.response.code === 302);`,
});
add("01.3 · Home autenticada e marca", "/", {
  code: `${ok}\npm.test("Home institucional, não vitrine global", () => pm.expect(pm.response.text()).to.include('id="tenant-home-title"'));`,
});
add("01.4 · Projetos deste host", "/projetos/", {code: ok});

group("02 · Gestão e identidade", "Requer conta ativa Proprietário/Gestor. GETs não alteram dados. O POST opcional sobrescreve nome/apresentação/cores: use somente tenant descartável.");
add("02.1 · Identidade e novo CSRF", "/gestao/identidade/", {code: `${ok}\n${csrf}\n${captureIdentity}\npm.test("Cinco campos de tema", () => { for (const role of ["primary","secondary","accent","background","surface"]) pm.expect(pm.response.text()).to.include('data-theme-color="'+role+'"'); });`});
add("02.2 · Salvar tema opcional", "/gestao/identidade/", {
  method: "POST", gate: "allow_branding",
  fields: {
    ...preserved, csrfmiddlewaretoken: token, nome_exibicao: "{{branding_name}}", apresentacao: "Ambiente de homologação descartável.",
    theme_primary: "#315A76", theme_secondary: "#6E4AA3", theme_accent: "#5C9F63",
    theme_background: "#F3ECDF", theme_surface: "#FFFFFF",
  },
  code: redirect,
});
add("02.3 · Releitura de identidade", "/gestao/identidade/", {
  code: `${ok}\n${csrf}\n${captureIdentity}\nif (pm.environment.get("allow_branding") === "true") pm.test("Cor salva", () => pm.expect(pm.response.text()).to.include("#315A76"));`,
});
add("02.3a · Upload de logo e capa opcional", "/gestao/identidade/", {
  gate: "allow_uploads", method: "POST",
  fields: {csrfmiddlewaretoken: token, ...preserved},
  files: {logo: `${out}/fixtures/logo.png`, capa: `${out}/fixtures/cover.png`},
  code: redirect,
  description: "Substitui somente logo/capa no tenant descartável, preservando nome, apresentação, cores legadas e tema lidos no GET anterior. Requer allow_uploads e allow_writes explícitos. Arquivos relativos à raiz do repositório. Não restaura imagens anteriores.",
});
add("02.3b · URLs e rótulos de mídia", "/gestao/identidade/", {
  gate: "allow_uploads",
  code: `${ok}\n${csrf}
const html = pm.response.text();
pm.test("Upload preservou os demais campos de identidade", () => pm.expect((${readIdentity.toString()})(html)).to.deep.equal(JSON.parse(pm.variables.get("identity_snapshot"))));
pm.test("Logo e capa vinculadas", () => { pm.expect(html).to.include("/branding/logo/"); pm.expect(html).to.include("/branding/cover/"); pm.expect(html).to.include("Ver imagem atual"); });
const logo = html.match(/href=["']([^"']+\\/branding\\/logo\\/[^"']+)/);
const cover = html.match(/id=["']cover-preview["'][^>]*src=["']([^"']+)/);
const absolute = value => /^https?:\\/\\//.test(value) ? value : pm.environment.get("tenant_a_base") + value;
if (logo) pm.variables.set("media_logo_url", absolute(logo[1]));
if (cover) pm.variables.set("media_cover_url", absolute(cover[1]));`,
});
for (const kind of ["logo", "cover"]) {
  add(`02.3c · Buscar imagem ${kind} opcional`, "", {
    gate: "allow_media_fetch", base: `media_${kind}_url`,
    code: `${ok}\npm.test("Resposta é imagem", () => pm.expect(pm.response.headers.get("Content-Type")).to.match(/^image\\//));`,
    description: "Requer allow_media_fetch e upload anterior na mesma execução. GET da URL pública real, não prova persistência após redeploy. No Gunicorn local sem servidor de mídia, deixe desativado.",
  });
}
add("02.4 · Membros e convites", "/gestao/membros/", {code: `${ok}\n${csrf}`});
add("02.5 · Enviar convite opcional", "/gestao/membros/", {
  method: "POST", gate: "allow_email",
  fields: {csrfmiddlewaretoken: token, acao: "convidar", email: "{{invite_email}}", papel: "membro"},
  code: redirect,
  description: "Requer conta Gestor, allow_email=true, allow_writes=true, host aprovado e destinatário controlado. Proprietário só convida Gestor, portanto não use Proprietário neste envio de Membro. 302 não prova entrega. Consulte a caixa real e os eventos do provedor; o token não é exposto pelo dashboard.",
});
add("02.6 · Programas", "/gestao/programas/", {code: ok});

group("03 · Projeto autônomo e contexto progressivo", "Dependências: GET formulário → POST básico → ID do Location → GET contexto → POST contexto → detalhe. Cria um projeto privado novo por execução. Não exclui automaticamente.");
add("03.1 · Formulário de projeto", "/projetos/novo/", {code: `${ok}\n${csrf}`});
add("03.2 · Criar projeto privado", "/projetos/novo/", {
  method: "POST",
  fields: {csrfmiddlewaretoken: token, title: "{{project_title}}", direction: "Validar continuidade do fluxo institucional com dados descartáveis.", status: "ideia", visibility: "privado", tipo_projeto: "autonomo"},
  code: `${redirect}\nconst target = pm.response.headers.get("Location") || ""; const m = target.match(/\\/projetos\\/(\\d+)\\/contexto\\/$/); pm.test("ID e destino de contexto válidos", () => pm.expect(m).not.to.equal(null)); if (!m) pm.execution.setNextRequest(null); else pm.variables.set("project_id", m[1]);`,
});
add("03.3 · Abrir contexto sem 4xx", "/projetos/{{project_id}}/contexto/", {project: true, code: `${ok}\n${csrf}`});
add("03.4 · Salvar contexto", "/projetos/{{project_id}}/contexto/", {
  project: true, method: "POST",
  fields: {csrfmiddlewaretoken: token, category: "Homologação", tags: "postman,qa", visibility: "privado", "links-TOTAL_FORMS": "0", "links-INITIAL_FORMS": "0", "links-MIN_NUM_FORMS": "0", "links-MAX_NUM_FORMS": "1000"},
  code: redirect,
});
add("03.5 · Detalhe do próprio projeto", "/projetos/{{project_id}}/", {
  project: true, code: `${ok}\n${csrf}\npm.test("Projeto correto", () => pm.expect(pm.response.text()).to.include(pm.variables.get("project_title")));`,
});
add("03.6 · Adicionar comentário", "/projetos/{{project_id}}/comentarios/", {
  project: true, method: "POST", fields: {csrfmiddlewaretoken: token, content: "Contexto de teste Postman: comentário persistido."}, code: redirect,
});
add("03.7 · Registrar marco", "/projetos/{{project_id}}/marcos/", {
  project: true, method: "POST", fields: {csrfmiddlewaretoken: token, title: "Marco de homologação Postman", description: "Fluxo preservado.", milestone_type: "avanco"}, code: redirect,
});
add("03.8 · Releitura do histórico", "/projetos/{{project_id}}/", {
  project: true, code: `${ok}\npm.test("Comentário e marco persistiram", () => { pm.expect(pm.response.text()).to.include("Contexto de teste Postman"); pm.expect(pm.response.text()).to.include("Marco de homologação Postman"); });`,
});

group("04 · Bordas e isolamento HTTP", "Não substitui testes de política SQL. No tenant B, registre se a requisição está autenticada: redirect pode representar ausência de sessão/afiliação, não prova de RLS.");
add("04.1 · Mesmo ID em tenant B", "/projetos/{{project_id}}/", {
  project: true, base: "tenant_b_base",
  code: 'pm.test("Sem acesso por outro host", () => pm.expect([302,403,404]).to.include(pm.response.code)); pm.test("Título privado não vazou", () => pm.expect(pm.response.text()).not.to.include(pm.variables.get("project_title")));',
});
add("04.2 · Mesmo ID no global", "/projetos/{{project_id}}/", {
  project: true, base: "global_base",
  code: 'pm.test("Projeto institucional ausente no global", () => pm.expect([302,403,404]).to.include(pm.response.code));',
});
add("04.3 · CSRF inválido tratado", "/gestao/identidade/", {
  method: "POST", fields: {nome_exibicao: "NÃO DEVE SALVAR"},
  code: 'pm.test("CSRF rejeitado", () => pm.response.to.have.status(403)); pm.test("Sem traceback Django", () => pm.expect(pm.response.text()).not.to.include("Traceback"));',
});
add("04.4 · Recuperar página após bloqueio", "/gestao/identidade/", {code: `${ok}\n${csrf}`});

group("05 · Entrada por convite — execução opcional", "Fronteira manual: obtenha um convite fresco em caixa controlada ou fixture local. Informe invite_path apenas no environment privado. Saída do gestor → cadastro de conta inédita → tela de aceite → aceite explícito. Não cria convites fictícios nem tenta adivinhar tokens.");
const invitationGate = "allow_invite_accept";
add("05.1 · Sair do gestor", "/sair/", {method: "POST", gate: invitationGate, fields: {csrfmiddlewaretoken: token}, code: `${redirect}\npm.variables.set("auth_ready", false);`});
add("05.2 · Abrir convite anônimo", "{{invite_path}}", {
  auth: false, gate: invitationGate, code: `${ok}\n${csrf}\npm.test("Referrer não vaza token", () => pm.expect(pm.response.headers.get("Referrer-Policy")).to.eql("strict-origin"));`,
});
add("05.3 · Cadastro mínimo por convite", "{{invite_path}}", {
  auth: false, gate: invitationGate, method: "POST",
  fields: {csrfmiddlewaretoken: token, action: "register", username: "{{new_username}}", password1: "{{new_password}}", password2: "{{new_password}}"},
  code: redirect,
});
add("05.4 · Tela de aceite e CSRF renovado", "{{invite_path}}", {auth: false, gate: invitationGate, code: `${ok}\n${csrf}`});
add("05.5 · Aceitar explicitamente", "{{invite_path}}", {
  auth: false, gate: invitationGate, method: "POST", fields: {csrfmiddlewaretoken: token, action: "accept"},
  code: `${redirect}\nif (pm.response.code === 302) pm.variables.set("auth_ready", true);`,
});
add("05.6 · Entrada após afiliação", "/projetos/", {gate: invitationGate, code: ok});
add("05.7 · Não reutilizar convite aceito", "{{invite_path}}", {
  gate: invitationGate,
  code: 'pm.test("Convite consumido rejeitado", () => pm.expect([400,403,404,410]).to.include(pm.response.code));',
});
add("05.8 · Membro não altera identidade por POST direto", "/gestao/identidade/", {
  gate: invitationGate, method: "POST",
  fields: {csrfmiddlewaretoken: token, nome_exibicao: "NÃO DEVE SALVAR"},
  code: 'pm.test("Membro sem permissão de gestão", () => pm.response.to.have.status(403));',
  description: "Use convite novo de papel membro. Para convite de Gestor, esta asserção não se aplica: não execute esta pasta com papel diferente.",
});

function blockRequest(label, message) {
  pm.execution.setNextRequest(null);
  pm.test(label, () => pm.expect.fail(message));
  pm.execution.skipRequest();
}
function guardIdentity(enabled) {
  const identityWrite = (pm.info.requestName.startsWith("02.2") && enabled("allow_branding")) ||
    (pm.info.requestName.startsWith("02.3a") && enabled("allow_uploads"));
  if (enabled("allow_writes") && identityWrite && !pm.variables.get("identity_snapshot")) {
    blockRequest("Upload exige snapshot prévio", "Identidade anterior não foi lida.");
    return false;
  }
  return true;
}
function guardMedia() {
  if (pm.info.requestName.startsWith("02.3c") && !pm.variables.get(pm.request.url.toString().includes("cover") ? "media_cover_url" : "media_logo_url")) {
    pm.execution.skipRequest();
    return false;
  }
  return true;
}
function guardWrite(enabled) {
  if (pm.request.method === "GET") return true;
  if (!enabled("allow_writes")) {
    pm.execution.skipRequest();
    return false;
  }
  const target = pm.variables.replaceIn(pm.request.url.toString());
  const host = (target.match(/^https?:\/\/([^/]+)/i) || [])[1];
  const approved = pm.environment.get("approved_write_host");
  if (!host || !approved || host.toLowerCase() !== approved.toLowerCase()) {
    blockRequest("Host de escrita aprovado", "Escrita bloqueada: host não aprovado explicitamente.");
    return false;
  }
  return true;
}
function guardInvitation(enabled) {
  if (pm.info.requestName.startsWith("05.") && enabled("allow_invite_accept")) {
    const path = pm.environment.get("invite_path") || "";
    if (!/^\/convites\/organizacao\/[A-Za-z0-9_-]+\/aceitar\/$/.test(path)) {
      blockRequest("Caminho de convite válido", "Convite opcional exige caminho válido de organização.");
      return false;
    }
  }
  return true;
}
function guard() {
  const enabled = name => pm.environment.get(name) === "true";
  if (pm.info.requestName === "01.1 · Login institucional e CSRF") {
    pm.variables.set("auth_ready", false);
    pm.variables.set("project_id", "");
    pm.variables.set("project_title", `TESTE-POSTMAN ${Date.now()}`);
  }
  if (!guardWrite(enabled)) return;
  if (!guardIdentity(enabled)) return;
  if (!guardMedia()) return;
  guardInvitation(enabled);
}
const guards = [blockRequest, guardIdentity, guardMedia, guardWrite, guardInvitation].map(fn => fn.toString()).join("\n");
const collection = {
  info: {_postman_id: id("collection"), name: "Palácio Mental · Homologação institucional", schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json", description: "Formulários reais Django; execução ordenada, CSRF, host e mutações protegidos. Leia README.md. Não há credenciais, cookies ou tokens reais neste arquivo."},
  event: [script("prerequest", `${guards}\n(${guard.toString()})();`)],
  item: folders,
};
const defaults = {
  tenant_a_base: "https://homolog-a.palaciomental.com.br",
  tenant_b_base: "https://homolog-b.palaciomental.com.br",
  global_base: "https://palaciomental.com.br",
  allow_writes: "false", approved_write_host: "", allow_branding: "false", branding_name: "TESTE-POSTMAN",
  allow_email: "false", invite_email: "", allow_invite_accept: "false", allow_uploads: "false", allow_media_fetch: "false",
  username: "", password: "", invite_path: "", new_username: "", new_password: "",
};
const env = {
  id: id("environment"), name: "Palácio Mental · Seguro por padrão", _postman_variable_scope: "environment",
  values: Object.entries(defaults).map(([key, value]) => ({key, value, enabled: true, type: ["password", "new_password", "invite_path"].includes(key) ? "secret" : "default"})),
};
writeFileSync(`${out}/palacio-mental.postman_collection.json`, JSON.stringify(collection, null, 2) + "\n");
writeFileSync(`${out}/palacio-mental.postman_environment.json`, JSON.stringify(env, null, 2) + "\n");
console.log(`${folders.length} pastas, ${folders.reduce((sum, f) => sum + f.item.length, 0)} requisições.`);
