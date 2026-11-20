import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import {runInNewContext} from "node:vm";

const collection = JSON.parse(readFileSync("docs/testing/postman/palacio-mental.postman_collection.json", "utf8"));
const code = collection.event[0].script.exec.join("\n");
const items = collection.item.flatMap(folder => folder.item);

function simulate({method = "POST", name = "10.4 · Criar projeto privado", url = "{{tenant_a_base}}/projetos/novo/", env = {}, local = {}} = {}) {
  const result = {skipped: false, next: undefined, failures: [], local};
  const variables = {
    get: key => local[key],
    set: (key, value) => { local[key] = value; },
    replaceIn: value => value.replace(/\{\{([^}]+)\}\}/g, (_match, key) => env[key] || ""),
  };
  const pm = {
    request: {method, url: {toString: () => url}},
    info: {requestName: name}, variables, environment: {get: key => env[key]},
    execution: {skipRequest: () => { result.skipped = true; }, setNextRequest: value => { result.next = value; }},
    test: (_label, fn) => { try { fn(); } catch (error) { result.failures.push(error.message); } },
    expect: {fail: message => { throw new Error(message); }},
  };
  runInNewContext(code, {pm});
  return result;
}
const approved = {allow_writes: "true", approved_write_hosts: "qa.example.com, outro.example.com", tenant_a_base: "https://qa.example.com"};

test("todo script da coleção é JavaScript válido", () => {
  assert.ok(items.length > 0);
  for (const item of items) {
    for (const event of item.event) assert.doesNotThrow(() => new Function(event.script.exec.join("\n")), item.name);
  }
});
test("padrão bloqueia POST sem criar falha artificial", () => {
  const result = simulate();
  assert.equal(result.skipped, true);
  assert.deepEqual(result.failures, []);
});
test("GET não depende de escrita liberada", () => {
  assert.equal(simulate({method: "GET"}).skipped, false);
});
test("host fora da lista interrompe a execução", () => {
  const result = simulate({env: {...approved, approved_write_hosts: "outro.example.com"}});
  assert.equal(result.skipped, true);
  assert.equal(result.next, null);
  assert.equal(result.failures.length, 1);
});
test("hosts da lista aprovada permitem POST", () => {
  assert.equal(simulate({env: approved}).skipped, false);
  const other = simulate({env: {...approved, tenant_a_base: "https://outro.example.com"}, url: "https://outro.example.com/x/"});
  assert.equal(other.skipped, false);
});
test("início da execução zera sessão, IDs e gera títulos distintos", () => {
  const local = {auth_membro: true, project_inst_id: "9"};
  simulate({method: "GET", name: "00.1 · Aplicação pronta", local});
  assert.equal(local.auth_membro, false);
  assert.equal(local.project_inst_id, "");
  assert.notEqual(local.titulo_pessoal, local.titulo_inst);
});
test("requisições dependentes são puladas sem sessão ou ID", () => {
  const protectedItems = items.filter(item => item.event[0].script.exec.join("").includes("skipRequest"));
  assert.ok(protectedItems.length >= 15);
  for (const item of protectedItems.filter(i => i.name.startsWith("10.5"))) {
    const pre = item.event[0].script.exec.join("\n");
    const state = {skipped: false};
    runInNewContext(pre, {pm: {variables: {get: () => undefined}, environment: {get: () => undefined}, execution: {skipRequest: () => { state.skipped = true; }}}});
    assert.equal(state.skipped, true);
  }
});
test("isolamento entre tenants só roda quando habilitado", () => {
  const gated = items.filter(item => item.name.startsWith("30.6") || item.name.startsWith("30.7") || item.name.startsWith("30.8"));
  assert.equal(gated.length, 3);
  for (const item of gated) assert.match(item.event[0].script.exec.join("\n"), /allow_isolation/);
});

function runTest(name, {code = 200, headers = {}, body = "", local = {}, env = {}} = {}) {
  const item = items.find(entry => entry.name.startsWith(name));
  const result = {failures: [], tests: 0, next: undefined, local};
  const pm = {
    response: {
      code, headers: {get: key => headers[key]}, text: () => body, json: () => JSON.parse(body),
      to: {have: {status: expected => { if (code !== expected) throw new Error(`status ${code} != ${expected}`); }}},
    },
    variables: {get: key => local[key], set: (key, value) => { local[key] = value; }},
    environment: {get: key => env[key]},
    execution: {setNextRequest: value => { result.next = value; }},
    test: (_label, fn) => { result.tests += 1; try { fn(); } catch (error) { result.failures.push(error.message); } },
    expect: Object.assign(value => chai(value), {fail: message => { throw new Error(message); }}),
  };
  runInNewContext(item.event[1].script.exec.join("\n"), {pm});
  return result;
}
function chai(value) {
  const api = {
    to: {
      eql: expected => assert.deepEqual(value, expected), include: expected => assert.ok(String(value).includes(expected)),
      match: re => assert.match(String(value), re), be: {a: type => assert.equal(typeof value, type)},
      not: {match: re => assert.doesNotMatch(String(value), re), equal: expected => assert.notEqual(value, expected), include: expected => assert.ok(!String(value).includes(expected))},
    },
  };
  api.not = {to: api.to.not};
  return api;
}
test("criação extrai o ID do destino de contexto", () => {
  const ok = runTest("10.4", {code: 302, headers: {Location: "/projetos/42/contexto/"}});
  assert.deepEqual(ok.failures, []);
  assert.equal(ok.local.project_pessoal_id, "42");
  const reopened = runTest("10.4", {code: 200, body: "<form>erro</form>"});
  assert.ok(reopened.failures.length > 0);
  assert.equal(reopened.next, null);
});
test("login pessoal exige redirecionamento para a lista de projetos", () => {
  assert.equal(runTest("10.2", {code: 302, headers: {Location: "/projetos/"}}).local.auth_pessoal, true);
  assert.equal(runTest("10.2", {code: 200}).local.auth_pessoal, false);
});
test("login de membro rejeita destino de gestão", () => {
  assert.equal(runTest("20.2", {code: 302, headers: {Location: "/"}}).local.auth_membro, true);
  assert.equal(runTest("20.2", {code: 302, headers: {Location: "/gestao/"}}).local.auth_membro, false);
});
test("negativas aceitam somente o status declarado", () => {
  const html = "<p>nada</p>";
  assert.deepEqual(runTest("30.8", {code: 404, body: html, local: {titulo_inst: "QA-PM institucional 1"}}).failures, []);
  assert.ok(runTest("30.8", {code: 302, body: html, local: {titulo_inst: "QA-PM institucional 1"}}).failures.length > 0);
  assert.ok(runTest("30.5", {code: 404, body: html, local: {titulo_inst: "x"}}).failures.length > 0);
});
test("releitura exige título e marco automático", () => {
  const body = "<h1>QA-PM pessoal 1</h1><li>Contexto atualizado</li>";
  assert.deepEqual(runTest("10.7", {body, local: {titulo_pessoal: "QA-PM pessoal 1"}}).failures, []);
  assert.ok(runTest("10.7", {body: "<h1>QA-PM pessoal 1</h1>", local: {titulo_pessoal: "QA-PM pessoal 1"}}).failures.length > 0);
});
