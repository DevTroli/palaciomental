// node tools/build_postman_collaboration.mjs
import {Builder, status, redirect, csrf, login, form, projectCreated, detailPath, contextFields, deleteStep} from "./postman_kit.mjs";

const b = new Builder("palacio-mental-colaboracao", "CAMPPG - Colaboração",
  "Jornada institucional com dois alunos afiliados: publicação, comentário, relevância, pedido, aceite e limpeza. Leia README-colaboracao.md.");
const add = (name, path, options = {}) => b.add(name, path, {base: "tenant_a_base", ...options});
const ID = "project_pub_id";
const detail = `/projetos/{{${ID}}}/`;
const cleanup = "40.1 · Formulário de login";
const ok = label => status(200, label);
const back = label => redirect(label, `pm.expect(path).to.eql(${detailPath(ID)});`);
const loginPair = (prefix, user, pass, role, {first = false, skip = false} = {}) => {
  const opts = {need: first ? "" : ID, skipWhen: skip ? "auth_autor" : ""};
  add(`${prefix}.1 · Formulário de login`, "/entrar/", {...opts, code: `${ok("Login abre")}\n${csrf}`});
  add(`${prefix}.2 · Entrar`, "/entrar/", {...opts, method: "POST", fields: login(user, pass), code: `${redirect("Login conclui no destino esperado", `pm.expect(path).to.eql(${JSON.stringify("/")});`)}
const authenticated = pm.response.code === 302 && path === ${JSON.stringify("/")};
pm.variables.set("auth_autor", authenticated && ${role === "autor"});
pm.variables.set("auth_colab", authenticated && ${role === "colab"});
if (!authenticated) pm.execution.setNextRequest(__FAIL__);`});
};

b.group("10 · Publicação", "Autor publica conteúdo sintético; autor não comenta nem vota no próprio projeto.", cleanup);
loginPair("10", "autor_username", "autor_password", "autor", {first: true});
add("10.3 · Formulário de projeto", "/projetos/novo/", {auth: "auth_autor", code: `${ok("Formulário abre")}\n${csrf}`});
add("10.4 · Criar projeto", "/projetos/novo/", {auth: "auth_autor", method: "POST", fields: form({title: "{{titulo}}", direction: "Jornada de colaboração entre alunos do CAMPPG.", status: "ideia", visibility: "privado", tipo_projeto: "autonomo"}), code: projectCreated(ID)});
add("10.5 · Publicar buscando colaboradores", `${detail}contexto/`, {auth: "auth_autor", need: ID, method: "POST", fields: contextFields({visibility: "publico", seeking_collaborators: "on", collaboration_description: "Projeto institucional de teste, aberto somente durante a execução."}), code: back("Publicação aceita")});
for (const [number, endpoint, fields, label] of [
  ["6", "comentarios", {content: "Comentário proibido do autor"}, "Autor não comenta o próprio projeto"],
  ["7", "relevancia", {}, "Autor não vota no próprio projeto"],
]) add(`10.${number} · ${label}`, `${detail}${endpoint}/`, {auth: "auth_autor", need: ID, method: "POST", fields: form(fields), code: status(403, label)});

b.group("20 · Colaborador", "Outra conta encontra o projeto, comenta, vota e solicita colaboração.", cleanup);
loginPair("20", "colab_username", "colab_password", "colab");
add("20.3 · Descobrir na lista pública", "/projetos/?q={{titulo}}", {auth: "auth_colab", need: ID, code: `${ok("Busca abre")}
pm.test("Projeto encontrado", () => pm.expect(pm.response.text()).to.include(pm.variables.get("titulo")));`});
add("20.4 · Abrir o projeto", detail, {auth: "auth_colab", need: ID, code: `${ok("Detalhe abre")}
const html = pm.response.text();
pm.test("Projeto correto", () => pm.expect(html).to.include(pm.variables.get("titulo")));
const count = html.match(/class=["'][^"']*relevance-count[^"']*["'][^>]*>\\s*(\\d+)/);
pm.test("Contador disponível e projeto novo sem votos", () => pm.expect(count && Number(count[1])).to.eql(0));
if (count) pm.variables.set("vote_before", Number(count[1])); else pm.execution.setNextRequest(__FAIL__);
${csrf}`});
for (const [number, name, endpoint, fields] of [
  ["5", "Comentar", "comentarios", {content: "{{comentario}}"}],
  ["6", "Reconhecer relevância", "relevancia", {}],
  ["7", "Pedir para colaborar", "colaboracao", {message: "{{pedido}}"}],
]) add(`20.${number} · ${name}`, `${detail}${endpoint}/`, {auth: "auth_colab", need: ID, method: "POST", fields: form(fields), code: back(name)});

b.group("30 · Decisão do autor", "Releitura comprova comentário, incremento do voto e pedido exato; aceite deve aparecer na equipe.", cleanup);
loginPair("30", "autor_username", "autor_password", "autor", {skip: true});
add("30.3 · Ver pedido pendente", detail, {auth: "auth_autor", need: ID, code: `${ok("Detalhe do autor abre")}
const html = pm.response.text();
pm.test("Comentário persistido", () => pm.expect(html).to.include(pm.variables.get("comentario")));
const count = html.match(/class=["'][^"']*relevance-count[^"']*["'][^>]*>\\s*(\\d+)/);
pm.test("Voto incrementou o contador", () => pm.expect(count && Number(count[1])).to.eql(Number(pm.variables.get("vote_before")) + 1));
const requests = html.match(/<div\\b[^>]*class=["'][^"']*request-item[^"']*["'][^>]*>[\\s\\S]*?<\\/form>/gi) || [];
const own = requests.find(block => block.includes(pm.variables.get("pedido")) && block.includes("@" + pm.environment.get("colab_username")));
const requestMatch = own && own.match(/\\/colaboracoes\\/(\\d+)\\/decidir\\//);
pm.test("Pedido pertence ao colaborador desta execução", () => pm.expect(Boolean(requestMatch)).to.eql(true));
if (requestMatch) pm.variables.set("request_id", requestMatch[1]); else pm.execution.setNextRequest(__FAIL__);
${csrf}`});
add("30.4 · Aceitar o pedido", "/colaboracoes/{{request_id}}/decidir/", {auth: "auth_autor", need: "request_id", method: "POST", fields: form({decision: "aceita"}), code: back("Aceite registrado")});
add("30.5 · Colaborador integrado", detail, {auth: "auth_autor", need: "request_id", code: `${ok("Detalhe abre")}
const html = pm.response.text();
const cards = html.match(/<section\\b[^>]*>[\\s\\S]*?<\\/section>/gi) || [];
const team = cards.find(section => /<span[^>]*>\\s*Equipe\\s*<\\/span>/.test(section)) || "";
const members = team.match(/<p\\b[^>]*class=["'][^"']*team-member[^"']*["'][^>]*>[\\s\\S]*?<\\/p>/gi) || [];
const display = pm.environment.get("colab_display_name") || pm.environment.get("colab_username");
pm.test("Colaborador presente na equipe, não só nos comentários", () => pm.expect(members.some(member => member.includes(display) && member.includes("Colaborador"))).to.eql(true));
pm.test("Pedido aceito deixou de estar pendente", () => pm.expect(html).not.to.include("/colaboracoes/" + pm.variables.get("request_id") + "/decidir/"));`});

b.group("40 · Encerramento", "Tenta excluir somente o ID criado nesta execução; falha ou interrupção pode deixar resíduos.");
loginPair("40", "autor_username", "autor_password", "autor", {skip: true});
add("40.3 · Formulário de edição", `${detail}editar/`, {auth: "auth_autor", need: ID, code: `${ok("Edição abre")}
const input = (pm.response.text().match(/<input\\b[^>]*>/gi) || []).find(tag => /\\bname=["']title["']/.test(tag));
const title = input && input.match(/\\bvalue=["']([^"']*)["']/);
const owned = pm.response.code === 200 && Boolean(title) && title[1] === pm.variables.get("titulo");
pm.test("Título do projeto desta execução confirmado", () => pm.expect(owned).to.eql(true));
pm.variables.set("delete_pub_ok", owned ? "1" : "");
if (!owned) pm.execution.setNextRequest(null);
${csrf}`});
add("40.4 · Excluir projeto de teste", `${detail}excluir/`, {auth: "auth_autor", ...deleteStep(ID), need: "delete_pub_ok"});

b.write("palacio-mental-colaboracao", {
  tenant_a_base: "https://camppg.palaciomental.com.br", allow_writes: "false", approved_write_hosts: "",
  autor_username: "", autor_password: "", colab_username: "", colab_password: "", colab_display_name: "",
}, ["autor_password", "colab_password"], {
  flags: ["auth_autor", "auth_colab"], ids: [ID, "request_id", "delete_pub_ok", "vote_before"],
  titles: {titulo: "colab", comentario: "comentario", pedido: "pedido"},
}, "CAMP-PG · Colaboração");
