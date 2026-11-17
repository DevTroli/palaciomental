package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.UnknownHostException;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class BoundedDnsResolverTest {
  @Test
  void naoAguardaIndefinidamenteUmaResolucaoLenta() {
    try (var resolver = new BoundedDnsResolver(Duration.ofMillis(20), hostname -> {
      try {
        Thread.sleep(5000);
      } catch (InterruptedException exc) {
        Thread.currentThread().interrupt();
      }
      throw new UnknownHostException();
    })) {
      assertThatThrownBy(() -> resolver.resolve("example.invalid"))
          .isInstanceOf(UnknownHostException.class);
    }
  }
}
