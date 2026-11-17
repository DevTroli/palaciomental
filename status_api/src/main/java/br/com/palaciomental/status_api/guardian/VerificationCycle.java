package br.com.palaciomental.status_api.guardian;

import java.net.URI;
import java.util.Locale;
import java.util.concurrent.Semaphore;

/** Limita o trabalho simultâneo e mantém as tentativas dentro do mesmo ciclo. */
public final class VerificationCycle {
  @FunctionalInterface
  public interface Probe {
    HttpLinkProbe.Result check(URI uri);
  }

  private final Semaphore global = new Semaphore(8, true);
  private final Semaphore[] domains = new Semaphore[64];
  private final Probe probe;

  public VerificationCycle(Probe probe) {
    this.probe = java.util.Objects.requireNonNull(probe);
    for (int i = 0; i < domains.length; i++) {
      domains[i] = new Semaphore(1, true);
    }
  }

  public HttpLinkProbe.Result verify(URI uri) throws InterruptedException {
    if (uri == null || uri.getHost() == null) {
      throw new IllegalArgumentException("Destino inválido");
    }
    String host = uri.getHost().toLowerCase(Locale.ROOT);
    Semaphore domain = domains[Math.floorMod(host.hashCode(), domains.length)];
    domain.acquire();
    try {
      global.acquire();
      try {
        HttpLinkProbe.Result result;
        int attempts = 0;
        do {
          attempts++;
          result = probe.check(uri);
        } while (VerificationCyclePolicy.shouldRetry(attempts, result.transientFailure()));
        return result;
      } finally {
        global.release();
      }
    } finally {
      domain.release();
    }
  }
}
