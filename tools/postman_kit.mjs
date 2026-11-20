// Helpers dos geradores. Nenhuma chamada HTTP ocorre na geração.
import {createHash} from "node:crypto";
import {mkdirSync, writeFileSync} from "node:fs";
export const OUT = "docs/testing/postman";
const script = (listen, code) => ({listen, script: {type: "text/javascript", exec: code.split("\n")}});
export const status = (code, label) => `pm.test(${JSON.stringify(label)}, () => pm.response.to.have.status(${code}));`;
const where = 'const path = (pm.response.headers.get("Location") || "").replace(/^https?:\\/\\/[^/]+/, "");';
export const redirect = (label, check = "") => `${where}\npm.test(${JSON.stringify(label)}, () => { pm.expect(pm.response.code).to.eql(302); ${check} });\nif (pm.response.code !== 302) pm.execution.setNextRequest(__FAIL__);`;
export const csrf = `const match = pm.response.text().match(/name=["']csrfmiddlewaretoken["'][^>]*value=["']([^"']+)/);\npm.test("CSRF presente", () => pm.expect(match).not.to.equal(null));\nif (!match) pm.execution.setNextRequest(__FAIL__); else pm.variables.set("__CSRF__", match[1]);`;
export const login = (user, pass) => ({csrfmiddlewaretoken: "{{__CSRF__}}", username: `{{${user}}}`, password: `{{${pass}}}`});
export const form = (fields = {}) => ({csrfmiddlewaretoken: "{{__CSRF__}}", ...fields});
export const projectCreated = variable => `${redirect("Projeto criado", 'pm.expect(path).to.match(/^\\/projetos\\/\\d+\\/contexto\\/$/);')}\nconst created = path.match(/^\\/projetos\\/(\\d+)\\/contexto\\/$/);\nif (pm.response.code === 302 && created) pm.variables.set("${variable}", created[1]); else pm.execution.setNextRequest(__FAIL__);`;
export const detailPath = variable => `"/projetos/" + pm.variables.get("${variable}") + "/"`;
export const contextFields = (extra = {}) => form({category: "QA-PM", tags: "qa", visibility: "privado", "links-TOTAL_FORMS": "0", "links-INITIAL_FORMS": "0", "links-MIN_NUM_FORMS": "0", "links-MAX_NUM_FORMS": "1000", ...extra});
export const deleteStep = variable => ({method: "POST", need: variable, fields: form(), code: redirect("Exclusão redireciona ao perfil", 'pm.expect(path).to.match(/^\\/perfil\\//);')});

// Executada dentro do pre-request de cada item, após os requisitos do cenário.
function requestGuard(cfg) {
  const local = key => pm.variables.get(key);
  const enabled = key => pm.environment.get(key) === "true";
  const skip = () => { pm.execution.skipRequest(); return false; };
  if (cfg.personal && !enabled("allow_personal")) return skip();
  if (cfg.gate && !enabled(cfg.gate)) return skip();
  if (cfg.skipWhen && local(cfg.skipWhen) === true) return skip();
  if (cfg.auth && local(cfg.auth) !== true) return skip();
  if (cfg.need && !local(cfg.need)) return skip();
  if (pm.request.method === "GET") return true;
  if (!enabled("allow_writes")) return skip();
  const target = pm.variables.replaceIn(pm.request.url.toString());
  const match = target.match(/^https:\/\/([^/@?#]+)(?:\/|$)/i);
  const approved = (pm.environment.get("approved_write_hosts") || "").toLowerCase().split(",").map(s => s.trim()).filter(Boolean);
  if (!match || !approved.includes(match[1].toLowerCase())) {
    pm.test("Host HTTPS de escrita aprovado", () => pm.expect.fail("Escrita bloqueada: destino não aprovado."));
    pm.execution.setNextRequest(null);
    return skip();
  }
  // Não enviar um projeto vinculado com os campos obrigatórios vazios.
  if (cfg.linked && (!pm.environment.get("turma_id") || !pm.environment.get("orientador_id"))) {
    pm.test("Preparação institucional", () => pm.expect.fail("Preencha turma_id e orientador_id; o membro precisa participar da turma."));
    pm.execution.setNextRequest(null);
    return skip();
  }
  return true;
}

// A prova lê o formulário salvo, sem depender de um marco visível no detalhe.
function assertContext() {
  pm.test("Contexto abre", () => pm.response.to.have.status(200));
  const html = pm.response.text();
  for (const [name, expected] of [["category", "QA-PM"], ["tags", "qa"]]) {
    const inputs = html.match(/<input\b[^>]*>/gi) || [];
    const input = inputs.find(tag => new RegExp('\\bname=["\\\']' + name + '["\\\']').test(tag));
    const value = input && input.match(/\bvalue=["']([^"']*)["']/i);
    pm.test(name + " persistido", () => pm.expect(value && value[1]).to.eql(expected));
  }
}

export class Builder {
  constructor(namespace, name, description) {
    Object.assign(this, {namespace, name, description, folders: [], fail: "null"});
  }
  id(name) {
    const h = createHash("sha256").update(`${this.namespace}:${name}`).digest("hex");
    return `${h.slice(0,8)}-${h.slice(8,12)}-4${h.slice(13,16)}-a${h.slice(17,20)}-${h.slice(20,32)}`;
  }
  group(name, description, fail = null) {
    this.folder = {name, description, item: []}; this.folders.push(this.folder); this.fail = JSON.stringify(fail);
  }
  add(name, path, {method = "GET", fields, code = "", gate = "", auth = "", need = "", skipWhen = "", base = "tenant_a_base", fail} = {}) {
    const main = this.namespace === "palacio-mental";
    const personal = main && name.startsWith("10.");
    const linked = main && name.startsWith("20.5 ");
    if (main && (name.startsWith("10.6 ") || name.startsWith("20.7 "))) {
      path += "contexto/";
      code = `(${assertContext.toString()})();\n${csrf}`;
    }
    const target = fail === undefined ? this.fail : JSON.stringify(fail);
    const fill = text => text.replaceAll("__CSRF__", `csrf_${base.replace("_base", "")}`).replaceAll("__FAIL__", target);
    const cfg = {personal, linked, gate, auth, need, skipWhen};
    const pre = `(${requestGuard.toString()})(${JSON.stringify(cfg)});`;
    this.folder.item.push({id: this.id(name), name,
      request: {method, url: `{{${base}}}${path}`,
        header: method === "POST" ? [{key: "Origin", value: `{{${base}}}`}, {key: "Referer", value: `{{${base}}}/`}] : [],
        ...(fields ? {body: {mode: "urlencoded", urlencoded: Object.entries(fields).map(([key, value]) => ({key, value: fill(value), type: "text"}))}} : {})},
      protocolProfileBehavior: {followRedirects: false}, event: [script("prerequest", pre), script("test", fill(code))]});
  }
  write(file, defaults, secrets, reset) {
    const main = this.namespace === "palacio-mental";
    if (main) {
      defaults = {...defaults, tenant_a_base: "https://camppg.palaciomental.com.br", allow_personal: "false"};
      this.folders.sort((a, b) => Number(b.name.startsWith("20")) - Number(a.name.startsWith("20")));
    }
    // Inicializar apenas uma vez por execução, inclusive ao rodar uma pasta isolada.
    const init = cfg => {
      if (pm.variables.get("pm_run_namespace") === cfg.namespace) return;
      pm.variables.set("pm_run_namespace", cfg.namespace);
      for (const key of cfg.flags) pm.variables.set(key, false);
      for (const key of cfg.ids) pm.variables.set(key, "");
      const run = Date.now();
      for (const [key, label] of Object.entries(cfg.titles)) pm.variables.set(key, `QA-PM-${label}-${run}`);
    };
    const source = `(${init.toString()})(${JSON.stringify({...reset, namespace: this.namespace})});`;
    mkdirSync(OUT, {recursive: true});
    const collection = {info: {_postman_id: this.id("collection"), name: this.name, schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json", description: this.description}, event: [script("prerequest", source)], item: this.folders};
    const env = {id: this.id("environment"), name: `${this.name} · Seguro por padrão`, _postman_variable_scope: "environment", values: Object.entries(defaults).map(([key, value]) => ({key, value, enabled: true, type: secrets.includes(key) ? "secret" : "default"}))};
    writeFileSync(`${OUT}/${file}.postman_collection.json`, JSON.stringify(collection, null, 2) + "\n");
    writeFileSync(`${OUT}/${file}.postman_environment.json`, JSON.stringify(env, null, 2) + "\n");
    console.log(`${file}: ${this.folders.length} pastas, ${this.folders.reduce((n, f) => n + f.item.length, 0)} requisições.`);
  }
}
