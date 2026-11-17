package br.com.palaciomental.status_api.guardian;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Objects;

/** Simulação isolada: não é registrada no Spring e não executa chamadas por conta própria. */
public final class SafeBrowsingPrototype {
  public record Reply(List<ThreatHashMatcher.Match> matches, Duration cacheDuration, Instant receivedAt) {
    public Reply(List<ThreatHashMatcher.Match> matches, Duration cacheDuration) {
      this(matches, cacheDuration, null);
    }
  }

  @FunctionalInterface
  public interface Transport {
    Reply search(List<String> fourBytePrefixes) throws IOException;
  }

  private final Transport transport;

  public SafeBrowsingPrototype(Transport transport) {
    this.transport = Objects.requireNonNull(transport);
  }

  public ThreatAssessment assess(String url, Instant checkedAt) {
    if (checkedAt == null) return ThreatAssessment.unverified();
    var candidates = ThreatUrlHashes.fromUrl(url);
    if (candidates.isEmpty()) return ThreatAssessment.unverified();
    try {
      // A interface do transporte recebe apenas prefixos, nunca a URL ou hashes completos.
      Reply reply = transport.search(candidates.get().prefixes());
      if (reply == null) return ThreatAssessment.unverified();
      Instant receivedAt = reply.receivedAt() == null ? checkedAt : reply.receivedAt();
      return ThreatHashMatcher.evaluate(candidates.get().fullHashes(), reply.matches(),
          receivedAt, reply.cacheDuration());
    } catch (IOException ex) {
      return ThreatAssessment.unverified();
    }
  }
}
