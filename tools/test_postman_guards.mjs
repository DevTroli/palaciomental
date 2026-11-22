import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import {runInNewContext} from "node:vm";

const main = JSON.parse(readFileSync("docs/testing/postman/palacio-mental.postman_collection.json", "utf8"));
const collab = JSON.parse(readFileSync("docs/testing/postman/palacio-mental-colaboracao.postman_collection.json", "utf8"));
const institutional = JSON.parse(readFileSync("docs/testing/postman/palacio-mental-institucional.postman_collection.json", "utf8"));
const items = c => c.item.flatMap(f => f.item);
const find = prefix => items(main).find(i => i.name.startsWith(prefix + " "));
function guard(prefix, {env = {}, local = {}, method = "POST", url = "https://camppg.palaciomental.com.br/x/"} = {}) {
  const out = {skipped: false, next: undefined, failures: []};
  const pm = {request: {method, url: {toString: () => url}}, variables: {get: key => local[key], replaceIn: s => s}, environment: {get: key => env[key]}, execution: {skipRequest: () => {out.skipped = true;}, setNextRequest: n => {out.next = n;}}, test: (_label, fn) => {try {fn();} catch (e) {out.failures.push(e.message);}}, expect: {fail: msg => {throw new Error(msg);}}};
  runInNewContext(find(prefix).event[0].script.exec.join("\n"), {pm}); return out;
}
const approved = {allow_writes: "true", approved_write_hosts: "camppg.palaciomental.com.br"};
test("todos os scripts compilam; tenant é primeiro e contexto é relido", () => {
  assert.match(main.item[0].name, /^20/);
  for (const c of [main, collab, institutional]) for (const item of items(c)) for (const event of item.event) new Function(event.script.exec.join("\n"));
  assert.match(find("20.7").request.url, /\/contexto\/$/);
  assert.match(find("10.6").request.url, /\/contexto\/$/);
});
test("tenant B desligado é pulado antes da validação de host", () => {
  const out = guard("20.11", {env: approved, local: {project_inst_id: "1"}, url: "https://homolog-b.palaciomental.com.br/entrar/"});
  assert.equal(out.skipped, true); assert.deepEqual(out.failures, []); assert.equal(out.next, undefined);
});
test("público é opcional e escrita não autorizada continua bloqueada", () => {
  assert.equal(guard("10.2", {env: approved}).skipped, true);
  const bad = guard("20.2", {env: approved, url: "https://outro.example/entrar/"});
  assert.equal(bad.skipped, true); assert.equal(bad.next, null); assert.equal(bad.failures.length, 1);
  assert.equal(guard("20.2", {env: approved}).skipped, false);
  assert.equal(guard("20.2").skipped, true);
});
test("turma e orientador ausentes impedem POST de projeto vinculado", () => {
  const local = {auth_membro: true};
  assert.equal(guard("20.5", {env: approved, local}).failures.length, 1);
  assert.equal(guard("20.5", {env: {...approved, turma_id: "uuid", orientador_id: "1"}, local}).skipped, false);
});
test("sessão e ID continuam obrigatórios antes do POST", () => {
  assert.equal(guard("20.6", {env: approved}).skipped, true);
  assert.equal(guard("20.6", {env: approved, local: {auth_membro: true, project_inst_id: "1"}}).skipped, false);
});
test("persistência verifica category e tags por nome e valor, independente da ordem dos atributos", () => {
  for (const [body, errors] of [[`<input value="QA-PM" name="category"><input name="tags" value="qa"><input name="csrfmiddlewaretoken" value="tok">`, 0], [`<input name="category" value="outra"><input name="tags" value="qa"><input name="csrfmiddlewaretoken" value="tok">`, 1]]) {
    let failures = 0;
    const pm = {response: {text: () => body, to: {have: {status: n => assert.equal(n, 200)}}}, variables: {set: () => {}}, execution: {setNextRequest: () => {}}, test: (_name, fn) => {try {fn();} catch {failures++;}}, expect: value => ({to: {eql: expected => assert.equal(value, expected)}, not: {to: {equal: expected => assert.notEqual(value, expected)}}})};
    runInNewContext(find("20.7").event[1].script.exec.join("\n"), {pm}); assert.equal(failures, errors);
  }
});
