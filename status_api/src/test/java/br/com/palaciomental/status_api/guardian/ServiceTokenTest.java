package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class ServiceTokenTest {
  @Test
  void recusaTokensAusentesInvalidosOuMalformados() {
    var token = new ServiceToken("token-de-teste-local");
    assertThat(token.matches(null)).isFalse();
    assertThat(token.matches("Bearer ")).isFalse();
    assertThat(token.matches("Bearer incorreto")).isFalse();
    assertThat(token.matches("token-de-teste-local")).isFalse();
    assertThat(token.matches("Bearer " + "x".repeat(4096))).isFalse();
    assertThat(token.matches("Bearer token-de-teste-local")).isTrue();
    assertThatThrownBy(() -> new ServiceToken(" ")).isInstanceOf(IllegalArgumentException.class);
  }
}
