package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.List;
import org.junit.jupiter.api.Test;

class ThreatUrlHashesTest {
  private static String hash(String value) throws Exception {
    return Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-256")
        .digest(value.getBytes(StandardCharsets.UTF_8)));
  }

  @Test
  void geraExpressoesDocumentadasEEnvioSomenteDePrefixos() throws Exception {
    var candidates = ThreatUrlHashes.fromUrl("http://a.b.com/1/2.html?param=1").orElseThrow();
    var expected = List.of("a.b.com/1/2.html?param=1", "a.b.com/1/2.html", "a.b.com/", "a.b.com/1/",
        "b.com/1/2.html?param=1", "b.com/1/2.html", "b.com/", "b.com/1/");
    var actual = candidates.fullHashes().stream().map(Base64.getEncoder()::encodeToString).toList();
    for (String value : expected) assertThat(actual).contains(hash(value));
    assertThat(actual).hasSize(8);
    assertThat(candidates.prefixes()).allSatisfy(prefix ->
        assertThat(Base64.getDecoder().decode(prefix)).hasSize(4));
    assertThat(candidates.toString()).doesNotContain("a.b.com");
  }

  @Test
  void incluiDominioRegistravelMesmoComMuitosSubdominios() throws Exception {
    var candidates = ThreatUrlHashes.fromUrl("http://a.b.c.d.e.f.com/1.html").orElseThrow();
    var actual = candidates.fullHashes().stream().map(Base64.getEncoder()::encodeToString).toList();
    assertThat(actual).contains(hash("a.b.c.d.e.f.com/1.html"), hash("c.d.e.f.com/1.html"),
        hash("f.com/1.html"));
    assertThat(actual).doesNotContain(hash("b.c.d.e.f.com/1.html"));
  }

  @Test
  void normalizaCaixaDoDominioEBarrasEProtegeHashesDeMutacao() throws Exception {
    var candidates = ThreatUrlHashes.fromUrl("https://Example.COM//página?x=um+dois#fragmento").orElseThrow();
    var original = candidates.fullHashes();
    assertThat(original.stream().map(Base64.getEncoder()::encodeToString).toList())
        .contains(hash("example.com/p%C3%A1gina?x=um+dois"));
    original.getFirst()[0] ^= 1;
    assertThat(candidates.fullHashes().stream().map(Base64.getEncoder()::encodeToString).toList())
        .contains(hash("example.com/p%C3%A1gina?x=um+dois"));
  }

  @Test
  void decodificaEscapesRepetidosSemAlterarMaisOQueOEstandarPede() throws Exception {
    var candidates = ThreatUrlHashes.fromUrl("https://example.com/a%20b/%25%32%35?ref=%252F&x=um+dois").orElseThrow();
    var actual = candidates.fullHashes().stream().map(Base64.getEncoder()::encodeToString).toList();
    assertThat(actual).contains(hash("example.com/a%20b/%25?ref=/&x=um+dois"));
    var normalized = ThreatUrlHashes.fromUrl("https://example.com/a/%2e%2e/segredo").orElseThrow();
    assertThat(normalized.fullHashes().stream().map(Base64.getEncoder()::encodeToString).toList())
        .contains(hash("example.com/segredo"));
  }

  @Test
  void formatosAindaNaoSuportadosNaoRecebemFalsoResultado() throws Exception {
    for (String value : List.of("http://127.0.0.1/", "https://example.com:99999/",
        "https://user@example.com/", "file:///etc/passwd")) {
      assertThat(ThreatUrlHashes.fromUrl(value)).isEmpty();
    }
    assertThat(ThreatUrlHashes.fromUrl("https://example2.com/")).isPresent();
    assertThat(ThreatUrlHashes.fromUrl("https://xn--p1ai.com/")).isPresent();
    var unicode = ThreatUrlHashes.fromUrl("https://münchen.com/").orElseThrow();
    assertThat(unicode.fullHashes().stream().map(Base64.getEncoder()::encodeToString).toList())
        .contains(hash("xn--mnchen-3ya.com/"));
    assertThat(ThreatUrlHashes.fromUrl("https://user@münchen.com/")).isEmpty();
    assertThat(ThreatUrlHashes.fromUrl("https://example.com/a%3Fb")).isEmpty();
  }
}
