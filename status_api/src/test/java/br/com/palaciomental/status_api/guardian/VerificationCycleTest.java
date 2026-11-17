package br.com.palaciomental.status_api.guardian;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.net.URI;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class VerificationCycleTest {
  @Test
  void retriesTransientFailuresOnlyAndStopsAfterSuccess() throws Exception {
    AtomicInteger attempts = new AtomicInteger();
    var cycle = new VerificationCycle(uri -> attempts.incrementAndGet() < 3
        ? new HttpLinkProbe.Result(LinkStatus.SEM_RESPOSTA, true)
        : new HttpLinkProbe.Result(LinkStatus.ACESSIVEL, false));
    assertEquals(LinkStatus.ACESSIVEL, cycle.verify(URI.create("https://example.com/")).status());
    assertEquals(3, attempts.get());
  }

  @Test
  void definitiveFailureIsNotRetried() throws Exception {
    AtomicInteger attempts = new AtomicInteger();
    var cycle = new VerificationCycle(uri -> {
      attempts.incrementAndGet();
      return new HttpLinkProbe.Result(LinkStatus.QUEBRADO, false);
    });
    assertEquals(LinkStatus.QUEBRADO, cycle.verify(URI.create("https://example.com/")).status());
    assertEquals(1, attempts.get());
  }
}
