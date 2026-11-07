// Extrai somente campos conhecidos. Não executa HTML nem faz double-decode.
export function readIdentity(html) {
  const decode = value => value.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos);/gi, (entity, key) => {
    if (key[0] === "#") {
      const number = key[1].toLowerCase() === "x" ? parseInt(key.slice(2), 16) : parseInt(key.slice(1), 10);
      return number <= 0x10ffff ? String.fromCodePoint(number) : entity;
    }
    return {amp: "&", lt: "<", gt: ">", quot: '"', apos: "'"}[key.toLowerCase()];
  });
  const names = [
    "nome_exibicao", "cor_primaria", "cor_destaque", "cor_fundo",
    "theme_primary", "theme_secondary", "theme_accent", "theme_background", "theme_surface",
  ];
  const inputs = html.match(/<input\b[^>]*>/gi) || [];
  const result = {};
  for (const name of names) {
    const input = inputs.find(tag => tag.match(/\sname=(["'])(.*?)\1/i)?.[2] === name);
    if (!input) throw new Error(`Campo de identidade ausente: ${name}`);
    result[name] = decode(input.match(/\svalue=(["'])(.*?)\1/i)?.[2] || "");
  }
  const textarea = html.match(/<textarea\b(?=[^>]*\sname=["']apresentacao["'])[^>]*>([\s\S]*?)<\/textarea>/i);
  if (!textarea) throw new Error("Campo de apresentação ausente.");
  result.apresentacao = decode(textarea[1].replace(/^\r?\n/, ""));
  return result;
}
