// Utilitários compartilhados pelos geradores das coleções do Postman.
import {createHash} from "node:crypto";
import {mkdirSync, writeFileSync} from "node:fs";

export const OUT = "docs/testing/postman";
const script = (listen, code) => ({listen, script: {type: "text/javascript", exec: code.split("\n")}});

// __CSRF__ vira csrf_<host> (um token por sessão/host); __FAIL__ vira o destino em caso de falha.
export const status = (code, label) => `pm.test("${label}", () => pm.response.to.have.status(${code}));`;
const where = 'const path = (pm.response.headers.get("Location") || "").replace(/^https?:\\/\\/[^/]+/, "");';
export const redirect = (label, check = "") => `${where}
pm.test("${label}", () => { pm.expect(pm.response.code).to.eql(302); ${check} });
if (pm.response.code !== 302) pm.execution.setNextRequest(__FAIL__);`;
export const csrf = `const match = pm.response.text().match(/name=["']csrfmiddlewaretoken["'][^>]*value=["']([^"']+)/);
pm.test("CSRF presente", () => pm.expect(match).not.to.equal(null));
if (!match) pm.execution.setNextRequest(__FAIL__); else pm.variables.set("__CSRF__", match[1]);`;
export const login = (user, pass) => ({csrfmiddlewaretoken: "{{__CSRF__}}", username: `{{${user}}}`, password: `{{${pass}}}`});
export const form = (fields = {}) => ({csrfmiddlewaretoken: "{{__CSRF__}}", ...fields});
export const projectCreated = variable => `${redirect("Projeto criado e destino de contexto correto", 'pm.expect(path).to.match(/^\\/projetos\\/\\d+\\/contexto\\/$/);')}
const created = path.match(/^\\/projetos\\/(\\d+)\\/contexto\\/$/);
if (created) pm.variables.set("${variable}", created[1]);`;
export const detailPath = variable => `"/projetos/" + pm.variables.get("${variable}") + "/"`;
export const contextFields = (extra = {}) => form({
  category: "QA-PM", tags: "qa", visibility: "privado",
  "links-TOTAL_FORMS": "0", "links-INITIAL_FORMS": "0", "links-MIN_NUM_FORMS": "0", "links-MAX_NUM_FORMS": "1000", ...extra,
});
export const deleteStep = variable => ({
  method: "POST", need: variable, fields: form(),
  code: redirect("Exclusão redireciona ao perfil", 'pm.expect(path).to.match(/^\\/perfil\\//);'),
});

function blockRequest(label, message) {
  pm.execution.setNextRequest(null);
  pm.test(label, () => pm.expect.fail(message));
  pm.execution.skipRequest();
}
function guardWrite(enabled) {
  if (pm.request.method === "GET") return true;
  if (!enabled("allow_writes")) { pm.execution.skipRequest(); return false; }
  const target = pm.variables.replaceIn(pm.request.url.toString());
  const host = ((target.match(/^https?:\/\/([^/]+)/i) || [])[1] || "").toLowerCase();
  const approved = (pm.environment.get("approved_write_hosts") || "").toLowerCase().split(",").map(item => item.trim()).filter(Boolean);
  if (!host || !approved.includes(host)) {
    blockRequest("Host de escrita aprovado", "Escrita bloqueada: host não aprovado explicitamente.");
    return false;
  }
  return true;
}

export class Builder {
  constructor(namespace, name, description) {
    this.namespace = namespace; this.name = name; this.description = description;
    this.folders = []; this.fail = "null";
  }
  id(name) {
    const h = createHash("sha256").update(`${this.namespace}:${name}`).digest("hex");
    return `${h.slice(0,8)}-${h.slice(8,12)}-4${h.slice(13,16)}-a${h.slice(17,20)}-${h.slice(20,32)}`;
  }
  group(name, description, fail = null) {
    this.folder = {name, description, item: []};
    this.folders.push(this.folder);
    this.fail = JSON.stringify(fail);
  }
  // fail: destino em caso de falha (padrão: o da pasta; null encerra). auth: sessão exigida; need: variável exigida; gate: flag do environment; skipWhen: pula se a sessão já existe.
  add(name, path, {method = "GET", fields, code = "", gate = "", auth = "", need = "", skipWhen = "", base = "tenant_a_base", fail} = {}) {
    const target = fail === undefined ? this.fail : JSON.stringify(fail);
    const fill = text => text.replaceAll("__CSRF__", `csrf_${base.replace("_base", "")}`).replaceAll("__FAIL__", target);
    const pre = [
      gate ? `if (pm.environment.get("${gate}") !== "true") pm.execution.skipRequest();` : "",
      skipWhen ? `if (pm.variables.get("${skipWhen}") === true) pm.execution.skipRequest();` : "",
      auth ? `if (pm.variables.get("${auth}") !== true) pm.execution.skipRequest();` : "",
      need ? `if (!pm.variables.get("${need}")) pm.execution.skipRequest();` : "",
    ].filter(Boolean).join("\n");
    this.folder.item.push({
      id: this.id(name), name,
      request: {
        method, url: `{{${base}}}${path}`,
        header: method === "POST" ? [{key: "Origin", value: `{{${base}}}`}, {key: "Referer", value: `{{${base}}}/`}] : [],
        ...(fields ? {body: {mode: "urlencoded", urlencoded: Object.entries(fields).map(([key, value]) => ({key, value: fill(value), type: "text"}))}} : {}),
      },
      protocolProfileBehavior: {followRedirects: false},
      event: [script("prerequest", pre), script("test", fill(code))],
    });
  }
  // reset: {first, flags, ids, titles: {variável: sufixo}} executado antes da primeira requisição.
  write(file, defaults, secrets, reset) {
    const guard = () => {
      const cfg = __CFG__;
      if (pm.info.requestName.startsWith(cfg.first)) {
        for (const key of cfg.flags) pm.variables.set(key, false);
        for (const key of cfg.ids) pm.variables.set(key, "");
        const run = Date.now();
        for (const [key, label] of Object.entries(cfg.titles)) pm.variables.set(key, `QA-PM-${label}-${run}`);
      }
      guardWrite(name => pm.environment.get(name) === "true");
    };
    const source = `${blockRequest}\n${guardWrite}\n(${guard.toString().replace("__CFG__", JSON.stringify(reset))})();`;
    mkdirSync(OUT, {recursive: true});
    const collection = {
      info: {_postman_id: this.id("collection"), name: this.name, schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json", description: this.description},
      event: [script("prerequest", source)],
      item: this.folders,
    };
    const env = {
      id: this.id("environment"), name: `${this.name} · Seguro por padrão`, _postman_variable_scope: "environment",
      values: Object.entries(defaults).map(([key, value]) => ({key, value, enabled: true, type: secrets.includes(key) ? "secret" : "default"})),
    };
    writeFileSync(`${OUT}/${file}.postman_collection.json`, JSON.stringify(collection, null, 2) + "\n");
    writeFileSync(`${OUT}/${file}.postman_environment.json`, JSON.stringify(env, null, 2) + "\n");
    console.log(`${file}: ${this.folders.length} pastas, ${this.folders.reduce((sum, f) => sum + f.item.length, 0)} requisições.`);
  }
}
