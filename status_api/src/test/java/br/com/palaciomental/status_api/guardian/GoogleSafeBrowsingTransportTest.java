package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import org.junit.jupiter.api.Test;

class GoogleSafeBrowsingTransportTest {
  private static byte[] bytes(String value) { return value.getBytes(StandardCharsets.UTF_8); }

  @Test
  void interpretaRespostaVaziaEValidade() throws Exception {
    var reply = GoogleSafeBrowsingTransport.parse(bytes("{\"cacheDuration\":\"300.5s\"}"));
    assertThat(reply.matches()).isEmpty();
    assertThat(reply.cacheDuration()).isEqualTo(Duration.ofMillis(300500));
  }

  @Test
  void interpretaAmeacaSemAtributos() throws Exception {
    String hash = Base64.getEncoder().encodeToString(new byte[32]);
    var reply = GoogleSafeBrowsingTransport.parse(bytes("""
        {"cacheDuration":"60s","fullHashes":[{"fullHash":"%s","fullHashDetails":[{"threatType":"MALWARE"}]}]}
        """.formatted(hash)));
    assertThat(reply.matches()).hasSize(1);
    assertThat(reply.matches().getFirst().details().getFirst().threatType()).isEqualTo("MALWARE");
    assertThat(reply.matches().getFirst().details().getFirst().attributes()).isEmpty();
  }

  @Test
  void rejeitaRespostaMalformadaSemTratarComoSegura() {
    for (String json : new String[]{"{}", "{\"cacheDuration\":\"0s\"}",
        "{\"cacheDuration\":\"10s\",\"fullHashes\":{}}", "não é json"}) {
      assertThatThrownBy(() -> GoogleSafeBrowsingTransport.parse(bytes(json))).isInstanceOf(java.io.IOException.class);
    }
  }
}
