// Geração determinística. Execute: node tools/build_postman_collaboration.mjs
import {Builder, status, redirect, csrf, login, form, projectCreated, detailPath, contextFields, deleteStep} from "./postman_kit.mjs";

const b = new Builder("palacio-mental-colaboracao", "Palácio Mental · Colaboração pública",
  "Descoberta, comentário, relevância e colaboração entre duas contas pessoais. Cria um projeto público de teste e o remove ao final. Leia README.md.");
const add = b.add.bind(b);
const G = "global_base";
const ID = "project_pub_id";
const login2 = (prefix, user, pass, ok, skipWhen = "", need = ID) => {
  add(`${prefix}.1 · Formulário de login`, "/entrar/", {base: G, skipWhen, need, code: `${status(200, "Login abre")}\n${csrf}`});
  add(`${prefix}.2 · Entrar`, "/entrar/", {base: G, skipWhen, need, method: "POST", fields: login(user, pass),
    code: `${redirect("Login redireciona para a lista de projetos", 'pm.expect(path).to.eql("/projetos/");')}\nconst ok = pm.response.code === 302 && path === "/projetos/";\n${ok}`});
};
const asAuthor = `pm.variables.set("auth_autor", ok); if (ok) pm.variables.set("auth_colab", false);`;

b.group("10 · Publicação", "Autor publica projeto público buscando colaboradores; não comenta nem vota no próprio projeto.", "40.1 · Formulário de login");
login2("10", "autor_username", "autor_password", asAuthor, "", "");
add("10.3 · Formulário de projeto", "/projetos/novo/", {base: G, auth: "auth_autor", code: `${status(200, "Formulário abre")}\n${csrf}`});
add("10.4 · Criar projeto", "/projetos/novo/", {
  base: G, auth: "auth_autor", method: "POST",
  fields: form({title: "{{titulo}}", direction: "Verificar descoberta e colaboração.", status: "ideia", visibility: "privado"}),
  code: projectCreated(ID),
});
add("10.5 · Publicar buscando colaboradores", `/projetos/{{${ID}}}/contexto/`, {
  base: G, auth: "auth_autor", need: ID, method: "POST",
  fields: contextFields({visibility: "publico", seeking_collaborators: "on", collaboration_description: "Projeto de teste."}),
  code: redirect("Contexto salvo e retorno ao detalhe", `pm.expect(path).to.eql(${detailPath(ID)});`),
});
add("10.6 · Autor não comenta o próprio projeto", `/projetos/{{${ID}}}/comentarios/`, {
  base: G, auth: "auth_autor", need: ID, method: "POST", fields: form({content: "Comentário do autor"}),
  code: status(403, "Autor recebe 403 ao comentar o próprio projeto"),
});
add("10.7 · Autor não vota no próprio projeto", `/projetos/{{${ID}}}/relevancia/`, {
  base: G, auth: "auth_autor", need: ID, method: "POST", fields: form(),
  code: status(403, "Autor recebe 403 ao reconhecer o próprio projeto"),
});

b.group("20 · Colaborador", "Outra conta descobre o projeto, comenta, reconhece a relevância e pede para colaborar.", "40.1 · Formulário de login");
login2("20", "colab_username", "colab_password", `pm.variables.set("auth_colab", ok); if (ok) pm.variables.set("auth_autor", false);`);
add("20.3 · Descobrir na lista pública", "/projetos/?q={{titulo}}", {
  base: G, auth: "auth_colab", need: ID,
  code: `${status(200, "Lista pública abre")}
pm.test("Projeto público aparece na busca", () => pm.expect(pm.response.text()).to.include(pm.variables.get("titulo")));`,
});
add("20.4 · Abrir o projeto", `/projetos/{{${ID}}}/`, {
  base: G, auth: "auth_colab", need: ID,
  code: `${status(200, "Detalhe abre")}
pm.test("Título presente", () => pm.expect(pm.response.text()).to.include(pm.variables.get("titulo")));
${csrf}`,
});
const back = label => redirect(label, `pm.expect(path).to.eql(${detailPath(ID)});`);
add("20.5 · Comentar", `/projetos/{{${ID}}}/comentarios/`, {base: G, auth: "auth_colab", need: ID, method: "POST", fields: form({content: "{{comentario}}"}), code: back("Comentário aceito")});
add("20.6 · Reconhecer relevância", `/projetos/{{${ID}}}/relevancia/`, {base: G, auth: "auth_colab", need: ID, method: "POST", fields: form(), code: back("Relevância aceita")});
add("20.7 · Pedir para colaborar", `/projetos/{{${ID}}}/colaboracao/`, {base: G, auth: "auth_colab", need: ID, method: "POST", fields: form({message: "Posso ajudar com testes."}), code: back("Pedido aceito")});

b.group("30 · Decisão do autor", "Autor vê o pedido pendente e o comentário, aceita, e o colaborador passa a integrar o projeto.", "40.1 · Formulário de login");
login2("30", "autor_username", "autor_password", asAuthor, "auth_autor");
add("30.3 · Ver pedido pendente", `/projetos/{{${ID}}}/`, {
  base: G, auth: "auth_autor", need: ID,
  code: `${status(200, "Detalhe do autor abre")}
const html = pm.response.text();
pm.test("Contexto persistido", () => pm.expect(html).to.include("Contexto atualizado"));
pm.test("Comentário do colaborador aparece", () => pm.expect(html).to.include(pm.variables.get("comentario")));
pm.test("Pedido do colaborador aparece", () => pm.expect(html).to.include(pm.environment.get("colab_username")));
const request = html.match(/\\/colaboracoes\\/(\\d+)\\/decidir\\//);
pm.test("Decisão disponível para o autor", () => pm.expect(request).not.to.equal(null));
if (request) pm.variables.set("request_id", request[1]); else pm.execution.setNextRequest(__FAIL__);
${csrf}`,
});
add("30.4 · Aceitar o pedido", "/colaboracoes/{{request_id}}/decidir/", {base: G, auth: "auth_autor", need: "request_id", method: "POST", fields: form({decision: "aceita"}), code: back("Decisão registrada")});
add("30.5 · Colaborador integrado", `/projetos/{{${ID}}}/`, {
  base: G, auth: "auth_autor", need: "request_id",
  code: `${status(200, "Detalhe abre")}
const html = pm.response.text();
pm.test("Colaborador aparece no projeto", () => pm.expect(html).to.include(pm.environment.get("colab_username")));
pm.test("Pedido deixou de estar pendente", () => pm.expect(html).not.to.include("/colaboracoes/" + pm.variables.get("request_id") + "/decidir/"));`,
});

b.group("40 · Encerramento", "Remove o projeto público desta execução. Também roda quando a jornada falha antes.");
add("40.1 · Formulário de login", "/entrar/", {base: G, need: ID, skipWhen: "auth_autor", code: `${status(200, "Login abre")}\n${csrf}`});
add("40.2 · Entrar", "/entrar/", {base: G, need: ID, skipWhen: "auth_autor", method: "POST", fields: login("autor_username", "autor_password"),
  code: `${redirect("Login redireciona para a lista de projetos", 'pm.expect(path).to.eql("/projetos/");')}\npm.variables.set("auth_autor", pm.response.code === 302);`});
add("40.3 · Formulário de edição", `/projetos/{{${ID}}}/editar/`, {base: G, auth: "auth_autor", need: ID, code: `${status(200, "Edição abre")}\n${csrf}`});
add("40.4 · Excluir projeto de teste", `/projetos/{{${ID}}}/excluir/`, {base: G, auth: "auth_autor", ...deleteStep(ID)});

b.write("palacio-mental-colaboracao", {
  global_base: "https://palaciomental.com.br", allow_writes: "false", approved_write_hosts: "",
  autor_username: "", autor_password: "", colab_username: "", colab_password: "",
}, ["autor_password", "colab_password"], {
  first: "10.1", flags: ["auth_autor", "auth_colab"], ids: [ID, "request_id"],
  titles: {titulo: "colab", comentario: "comentario"},
});
