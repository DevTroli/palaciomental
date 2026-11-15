package br.com.palaciomental.status_api.guardian;

import java.security.MessageDigest;
import java.time.Duration;
import java.time.DateTimeException;
import java.time.Instant;
import java.util.List;
import java.util.Set;

/** Compara hashes completos; prefixos iguais, isoladamente, não comprovam ameaça. */
public final class ThreatHashMatcher {
  public record Detail(String threatType, List<String> attributes) {}
  public record Match(byte[] fullHash, List<Detail> details) {}

  private static final Set<String> SUPPORTED = Set.of("MALWARE", "SOCIAL_ENGINEERING");

  private ThreatHashMatcher() {}

  public static ThreatAssessment evaluate(List<byte[]> candidates, List<Match> matches,
      Instant checkedAt, Duration cacheDuration) {
    if (candidates == null || candidates.isEmpty() || matches == null || checkedAt == null
        || cacheDuration == null || cacheDuration.isZero() || cacheDuration.isNegative()
        || candidates.stream().anyMatch(hash -> hash == null || hash.length != 32)) {
      return ThreatAssessment.unverified();
    }
    final Instant expiresAt;
    try {
      expiresAt = checkedAt.plus(cacheDuration);
    } catch (DateTimeException | ArithmeticException exc) {
      return ThreatAssessment.unverified();
    }
    boolean unknown = false;
    for (Match match : matches) {
      if (match == null || match.fullHash() == null || match.fullHash().length != 32 || match.details() == null) {
        return ThreatAssessment.unverified();
      }
      if (candidates.stream().noneMatch(hash -> MessageDigest.isEqual(hash, match.fullHash()))) continue;
      if (match.details().isEmpty()) unknown = true;
      for (Detail detail : match.details()) {
        if (detail == null || detail.threatType() == null || detail.attributes() == null) {
          unknown = true;
          continue;
        }
        // Atributos desconhecidos, CANARY e FRAME_ONLY não autorizam bloqueio.
        if (!detail.attributes().isEmpty() || !SUPPORTED.contains(detail.threatType())) {
          unknown = true;
          continue;
        }
        return new ThreatAssessment(ThreatAssessment.State.THREAT, checkedAt, expiresAt);
      }
    }
    return unknown ? ThreatAssessment.unverified()
        : new ThreatAssessment(ThreatAssessment.State.NO_MATCH, checkedAt, expiresAt);
  }
}
