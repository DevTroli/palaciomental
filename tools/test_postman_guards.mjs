import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import {runInNewContext} from "node:vm";

const collection = JSON.parse(readFileSync("docs/testing/postman/palacio-mental.postman_collection.json", "utf8"));
const code = collection.event[0].script.exec.join("\n");

function simulate({method = "POST", name = "03.2 · Criar projeto privado", env = {}, local = {}} = {}) {
  const result = {skipped: false, next: undefined, failures: []};
  const variables = {
    get: key => local[key],
    set: (key, value) => { local[key] = value; },
    replaceIn: value => value.replace(/\{\{([^}]+)\}\}/g, (_match, key) => env[key] || ""),
  };
  const pm = {
    request: {method, url: {toString: () => "{{tenant_a_base}}/projetos/novo/"}},
    info: {requestName: name}, variables, environment: {get: key => env[key]},
    execution: {skipRequest: () => { result.skipped = true; }, setNextRequest: value => { result.next = value; }},
    test: (_label, fn) => { try { fn(); } catch (error) { result.failures.push(error.message); } },
    expect: {fail: message => { throw new Error(message); }},
  };
  runInNewContext(code, {pm});
  return result;
}
const approved = {allow_writes: "true", approved_write_host: "qa.example.com", tenant_a_base: "https://qa.example.com"};

test("padrão bloqueia POST sem criar falha artificial", () => {
  const result = simulate();
  assert.equal(result.skipped, true);
  assert.deepEqual(result.failures, []);
});
test("host divergente interrompe e não libera escrita", () => {
  const result = simulate({env: {...approved, approved_write_host: "outro.example.com"}});
  assert.equal(result.skipped, true);
  assert.equal(result.next, null);
  assert.equal(result.failures.length, 1);
});
test("host aprovado permite POST; upload ainda exige snapshot", () => {
  assert.equal(simulate({env: approved}).skipped, false);
  const options = {name: "02.3a · Upload", env: {...approved, allow_uploads: "true"}};
  assert.equal(simulate(options).skipped, true);
  assert.equal(simulate({...options, local: {identity_snapshot: "{}"}}).skipped, false);
});
test("branding desligado não exige snapshot para item que será pulado", () => {
  const result = simulate({name: "02.2 · Salvar tema", env: {...approved, allow_branding: "false"}});
  assert.equal(result.skipped, false);
  assert.deepEqual(result.failures, []);
});
test("convite inválido é bloqueado mesmo em GET", () => {
  const result = simulate({method: "GET", name: "05.2 · Abrir convite", env: {allow_invite_accept: "true", invite_path: "/incorreto/"}});
  assert.equal(result.skipped, true);
  assert.equal(result.next, null);
});
