import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import {runInNewContext} from "node:vm";

const load = file => JSON.parse(readFileSync(`docs/testing/postman/${file}.postman_collection.json`, "utf8"));
const main = load("palacio-mental");
const collab = load("palacio-mental-colaboracao");
const all = c => c.item.flatMap(folder => folder.item);
const find = (c, prefix) => all(c).find(item => item.name.startsWith(prefix));
const text = (item, event) => item.event[event].script.exec.join("\n");

function skips(c, prefix, local = {}, env = {}) {
  let skipped = false;
  runInNewContext(text(find(c, prefix), 0), {pm: {variables: {get: key => local[key]}, environment: {get: key => env[key]}, execution: {skipRequest: () => { skipped = true; }}}});
  return skipped;
}
function guard(c, {method = "POST", name = "10.1", url = "{{global_base}}/x/", env = {}, local = {}} = {}) {
  const out = {skipped: false, next: undefined, failures: [], local};
  const pm = {
    request: {method, url: {toString: () => url}}, info: {requestName: name},
    variables: {get: key => local[key], set: (key, value) => { local[key] = value; }, replaceIn: value => value.replace(/\{\{([^}]+)\}\}/g, (_m, key) => env[key] || "")},
    environment: {get: key => env[key]},
    execution: {skipRequest: () => { out.skipped = true; }, setNextRequest: value => { out.next = value; }},
    test: (_label, fn) => { try { fn(); } catch (error) { out.failures.push(error.message); } },
    expect: {fail: message => { throw new Error(message); }},
  };
  runInNewContext(c.event[0].script.exec.join("\n"), {pm});
  return out;
}
const chai = value => {
  const to = {
    eql: expected => assert.deepEqual(value, expected), include: expected => assert.ok(String(value).includes(expected)),
    match: re => assert.match(String(value), re), be: {a: type => assert.equal(typeof value, type)},
    not: {match: re => assert.doesNotMatch(String(value), re), equal: expected => assert.notEqual(value, expected), include: expected => assert.ok(!String(value).includes(expected))},
  };
  return {to, not: {to: to.not}};
};
function run(c, prefix, {code = 200, headers = {}, body = "", local = {}, env = {}} = {}) {
  const out = {failures: [], next: undefined, local};
  const pm = {
    response: {code, headers: {get: key => headers[key]}, text: () => body, json: () => JSON.parse(body),
      to: {have: {status: expected => { if (code !== expected) throw new Error(`status ${code} != ${expected}`); }}}},
    variables: {get: key => local[key], set: (key, value) => { local[key] = value; }}, environment: {get: key => env[key]},
    execution: {setNextRequest: value => { out.next = value; }},
    test: (_label, fn) => { try { fn(); } catch (error) { out.failures.push(error.message); } },
    expect: Object.assign(chai, {fail: message => { throw new Error(message); }}),
  };
  runInNewContext(text(find(c, prefix), 1), {pm});
  return out;
}
const form = title => `<input value="${title}"><input name="csrfmiddlewaretoken" value="tok">`;

test("todo script é JavaScript válido e todo POST leva Origin e CSRF do próprio host", () => {
  for (const c of [main, collab]) {
    for (const item of all(c)) {
      for (const event of item.event) assert.doesNotThrow(() => new Function(event.script.exec.join("\n")), item.name);
      if (item.request.method !== "POST") continue;
      const host = item.request.url.match(/^\{\{(\w+)_base\}\}/)[1];
      const fields = Object.fromEntries(item.request.body.urlencoded.map(f => [f.key, f.value]));
      assert.equal(fields.csrfmiddlewaretoken, `{{csrf_${host}}}`, item.name);
      assert.deepEqual(item.request.header.map(h => h.key), ["Origin", "Referer"], item.name);
    }
  }
});
test("cada token usado por um POST é extraído por algum GET do mesmo host", () => {
  for (const c of [main, collab]) {
    const set = all(c).filter(i => i.request.method === "GET").map(i => text(i, 1)).join("\n");
    for (const item of all(c).filter(i => i.request.method === "POST")) {
      const name = item.request.body.urlencoded.find(f => f.key === "csrfmiddlewaretoken").value.slice(2, -2);
      assert.ok(set.includes(`pm.variables.set("${name}"`), `${item.name} usa ${name}`);
    }
  }
});
test("escrita só com allow_writes e host aprovado; início zera estado", () => {
  for (const c of [main, collab]) {
    assert.equal(guard(c).skipped, true);
    assert.deepEqual(guard(c).failures, []);
    assert.equal(guard(c, {method: "GET"}).skipped, false);
    const env = {allow_writes: "true", approved_write_hosts: "qa.example.com, b.example.com"};
    assert.equal(guard(c, {env, url: "https://b.example.com/x/"}).skipped, false);
    const blocked = guard(c, {env, url: "https://evil.example.com/x/"});
    assert.deepEqual([blocked.skipped, blocked.next, blocked.failures.length], [true, null, 1]);
    const local = {auth_pessoal: true, auth_autor: true, project_pessoal_id: "9", project_pub_id: "9"};
    guard(c, {method: "GET", local});
    assert.deepEqual([local.auth_pessoal ?? false, local.project_pub_id ?? ""].length, 2);
  }
  const local = {auth_pessoal: true, project_pessoal_id: "9", titulo_pessoal: "x"};
  guard(main, {method: "GET", local});
  assert.equal(local.auth_pessoal, false);
  assert.equal(local.project_pessoal_id, "");
  assert.match(local.titulo_pessoal, /^QA-PM-pessoal-\d+$/);
});
test("dependentes e opcionais são pulados quando a condição não existe", () => {
  assert.equal(skips(main, "10.4"), true);
  assert.equal(skips(main, "10.5", {auth_pessoal: true}), true);
  assert.equal(skips(main, "10.5", {auth_pessoal: true, project_pessoal_id: "1"}), false);
  for (const prefix of ["20.10", "20.11", "20.12", "20.13", "20.14"]) {
    const local = {auth_b: true, project_inst_id: "1"};
    assert.equal(skips(main, prefix, local), true, prefix);
    assert.equal(skips(main, prefix, local, {allow_isolation: "true"}), false, prefix);
  }
  assert.equal(skips(collab, "30.1", {project_pub_id: "1", auth_autor: true}), true);
  assert.equal(skips(collab, "30.1", {project_pub_id: "1", auth_autor: false}), false);
});
test("criação extrai o ID; falha leva ao encerramento da pasta; encerramento nunca salta para si", () => {
  const ok = run(main, "10.4", {code: 302, headers: {Location: "/projetos/42/contexto/"}});
  assert.deepEqual([ok.failures, ok.local.project_pessoal_id], [[], "42"]);
  assert.equal(run(main, "10.4", {code: 200}).next, "10.7 · Excluir projeto de teste");
  assert.equal(run(main, "20.5", {code: 200}).next, "20.15 · Excluir projeto de teste");
  assert.equal(run(collab, "20.5", {code: 403}).next, "40.1 · Formulário de login");
  for (const [c, prefix] of [[main, "10.7"], [main, "20.15"], [collab, "40.1"], [collab, "40.3"], [collab, "40.4"]]) {
    assert.equal(run(c, prefix, {code: 500}).next, null, prefix);
  }
  assert.equal(all(main).concat(all(collab)).filter(i => i.request.url.includes("/excluir/")).length, 3);
});
test("logins e negativas aceitam somente o resultado declarado", () => {
  assert.equal(run(main, "10.2", {code: 302, headers: {Location: "/projetos/"}}).local.auth_pessoal, true);
  assert.equal(run(main, "10.2", {code: 200}).local.auth_pessoal, false);
  assert.equal(run(main, "20.2", {code: 302, headers: {Location: "/gestao/"}}).local.auth_membro, false);
  const local = {titulo_inst: "QA-PM-inst-1"};
  for (const [prefix, status] of [["20.8", 404], ["20.12", 404], ["20.14", 403], ["20.4", 403], ["20.9", 404]]) {
    const body = prefix === "20.4" ? '{"detail":"x"}' : prefix === "20.9" ? "Ambiente institucional não encontrado" : "<p>nada</p>";
    assert.deepEqual(run(main, prefix, {code: status, body, local}).failures, [], prefix);
    assert.ok(run(main, prefix, {code: status === 404 ? 302 : 404, body, local}).failures.length > 0, prefix);
  }
  assert.ok(run(main, "20.8", {code: 404, body: "QA-PM-inst-1", local}).failures.length > 0);
});
test("persistência exige título e marco do contexto", () => {
  const local = {titulo_pessoal: "QA-PM-pessoal-1"};
  assert.deepEqual(run(main, "10.6", {body: "QA-PM-pessoal-1 Contexto atualizado", local}).failures, []);
  assert.ok(run(main, "10.6", {body: "QA-PM-pessoal-1", local}).failures.length > 0);
});
test("colaboração: regras de autor e colaborador, pedido localizado e decisão do modelo", () => {
  const post = prefix => Object.fromEntries(find(collab, prefix).request.body.urlencoded.map(f => [f.key, f.value]));
  assert.deepEqual([post("30.4").decision, post("10.5").visibility, post("10.5").seeking_collaborators], ["aceita", "publico", "on"]);
  for (const prefix of ["10.6", "10.7"]) assert.deepEqual(run(collab, prefix, {code: 403}).failures, []);
  assert.ok(run(collab, "20.3", {body: "outro", local: {titulo: "QA-PM-colab-1"}}).failures.length > 0);
  const env = {colab_username: "qa_colab"};
  const html = 'qa_colab QA-PM-comentario-1 Contexto atualizado <form action="/colaboracoes/7/decidir/"><input name="csrfmiddlewaretoken" value="tok">';
  const ok = run(collab, "30.3", {body: html, env, local: {comentario: "QA-PM-comentario-1"}});
  assert.deepEqual([ok.failures, ok.local.request_id], [[], "7"]);
  assert.equal(run(collab, "30.3", {body: "qa_colab", env, local: {comentario: "x"}}).next, "40.1 · Formulário de login");
  const done = {request_id: "7"};
  assert.deepEqual(run(collab, "30.5", {body: "qa_colab", env, local: done}).failures, []);
  assert.ok(run(collab, "30.5", {body: 'qa_colab /colaboracoes/7/decidir/', env, local: done}).failures.length > 0);
});
