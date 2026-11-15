package br.com.palaciomental.status_api.guardian;

import java.time.Clock;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/** Desligado sem chave; somente prefixos de hash são enviados ao provedor. */
@Service
public class ThreatService {
  private final SafeBrowsingPrototype checker;

  public ThreatService(@Value("${guardiao.safe-browsing-key:}") String key) {
    checker = key.isBlank() ? null : new SafeBrowsingPrototype(
        new CachedThreatTransport(new GoogleSafeBrowsingTransport(key), Clock.systemUTC()));
  }

  public ThreatAssessment check(String url) {
    if (checker == null) return ThreatAssessment.unverified();
    Instant now = Instant.now();
    ThreatAssessment result = checker.assess(url, now);
    return result.currentState(Instant.now()) == ThreatAssessment.State.UNVERIFIED
        ? ThreatAssessment.unverified() : result;
  }
}
