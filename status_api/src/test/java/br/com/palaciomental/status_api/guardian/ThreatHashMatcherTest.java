package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class ThreatHashMatcherTest {
  private static final Instant NOW = Instant.parse("2026-11-15T12:00:00Z");
  private static final Duration TTL = Duration.ofMinutes(10);
  private final byte[] candidate = new byte[32];

  @Test
  void colisaoDePrefixoNaoDeveBloquear() {
    var different = candidate.clone();
    different[31] = 1;
    var match = new ThreatHashMatcher.Match(different,
        List.of(new ThreatHashMatcher.Detail("MALWARE", List.of())));
    assertThat(ThreatHashMatcher.evaluate(List.of(candidate), List.of(match), NOW, TTL).state())
        .isEqualTo(ThreatAssessment.State.NO_MATCH);
  }

  @Test
  void hashCompletoComAmeacaConhecidaEhReconhecido() {
    var match = new ThreatHashMatcher.Match(candidate.clone(),
        List.of(new ThreatHashMatcher.Detail("SOCIAL_ENGINEERING", List.of())));
    assertThat(ThreatHashMatcher.evaluate(List.of(candidate), List.of(match), NOW, TTL).state())
        .isEqualTo(ThreatAssessment.State.THREAT);
  }

  @Test
  void atributosNaoAplicaveisOuDesconhecidosNaoCausamBloqueio() {
    for (String attribute : List.of("CANARY", "FRAME_ONLY", "FUTURO")) {
      var match = new ThreatHashMatcher.Match(candidate,
          List.of(new ThreatHashMatcher.Detail("MALWARE", List.of(attribute))));
      assertThat(ThreatHashMatcher.evaluate(List.of(candidate), List.of(match), NOW, TTL).state())
          .isEqualTo(ThreatAssessment.State.UNVERIFIED);
    }
  }

  @Test
  void falhasOuRespostaMalformadaNaoSignificamAusenciaDeAmeaca() {
    assertThat(ThreatHashMatcher.evaluate(List.of(candidate), null, NOW, TTL).state())
        .isEqualTo(ThreatAssessment.State.UNVERIFIED);
    assertThat(ThreatHashMatcher.evaluate(List.of(candidate), List.of(), NOW, Duration.ZERO).state())
        .isEqualTo(ThreatAssessment.State.UNVERIFIED);
    assertThat(ThreatHashMatcher.evaluate(List.of(new byte[4]), List.of(), NOW, TTL).state())
        .isEqualTo(ThreatAssessment.State.UNVERIFIED);
  }
}
