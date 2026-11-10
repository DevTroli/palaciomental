import assert from "node:assert/strict";
import test from "node:test";
import {readIdentity} from "./postman_identity.mjs";

const fields = {
  nome_exibicao: "Faculdade &amp; Pesquisa &quot;A&quot; &#x27;B&#x27;",
  cor_primaria: "azul", cor_destaque: "verde", cor_fundo: "creme",
  theme_primary: "#315A76", theme_secondary: "#6E4AA3", theme_accent: "#5C9F63",
  theme_background: "#F3ECDF", theme_surface: "#FFFFFF",
};
const html = Object.entries(fields).map(([name, value]) => `<input value="${value}" id="id_${name}" type="text" name="${name}">`).join("") +
  '<textarea rows="3" name="apresentacao">\nPesquisa &amp; contexto\n&lt;texto&gt; &amp;lt;literal&amp;gt; &#227;</textarea>';

test("preserva campos e decodifica escape Django uma única vez", () => {
  const result = readIdentity(html);
  assert.equal(result.nome_exibicao, 'Faculdade & Pesquisa "A" \'B\'');
  assert.equal(result.apresentacao, "Pesquisa & contexto\n<texto> &lt;literal&gt; ã");
  for (const key of Object.keys(fields).filter(key => key !== "nome_exibicao")) assert.equal(result[key], fields[key]);
});
test("preserva apresentação vazia e valores vazios de input", () => {
  const result = readIdentity(html.replace('value="azul"', "").replace(/<textarea[\s\S]*?<\/textarea>/, '<textarea name="apresentacao"></textarea>'));
  assert.equal(result.cor_primaria, "");
  assert.equal(result.apresentacao, "");
});
test("interrompe snapshot incompleto em vez de inventar defaults", () => {
  assert.throws(() => readIdentity(html.replace('name="cor_fundo"', 'name="outro"')), /Campo de identidade ausente/);
  assert.throws(() => readIdentity(html.replace(/<textarea[\s\S]*?<\/textarea>/, "")), /Campo de apresentação ausente/);
});
