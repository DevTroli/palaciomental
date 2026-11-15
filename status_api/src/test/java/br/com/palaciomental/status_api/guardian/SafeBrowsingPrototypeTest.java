package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;

class SafeBrowsingPrototypeTest {
  private static final Instant NOW = Instant.parse("2026-11-15T12:00:00Z");

  @Test
  void enviaSomentePrefixosEReconheceHashCompletoNaRespostaSimulada() {
    var hashes = ThreatUrlHashes.fromUrl("https://example.com/documento").orElseThrow();
    var service = new SafeBrowsingPrototype(prefixes -> {
      assertThat(prefixes).allSatisfy(prefix -> assertThat(Base64.getDecoder().decode(prefix)).hasSize(4));
      var match = new ThreatHashMatcher.Match(hashes.fullHashes().getFirst(),
          List.of(new ThreatHashMatcher.Detail("SOCIAL_ENGINEERING", List.of())));
      return new SafeBrowsingPrototype.Reply(List.of(match), Duration.ofMinutes(5));
    });
    assertThat(service.assess("https://example.com/documento", NOW).state())
        .isEqualTo(ThreatAssessment.State.THREAT);
  }

  @Test
  void semCorrespondenciaNaoSignificaQueLinkEhSeguro() {
    var service = new SafeBrowsingPrototype(prefixes -> new SafeBrowsingPrototype.Reply(List.of(), Duration.ofMinutes(5)));
    assertThat(service.assess("https://example.com/", NOW).state()).isEqualTo(ThreatAssessment.State.NO_MATCH);
  }

  @Test
  void aceitaRespostaRecebidaDepoisDoInicioDaConsulta() {
    var service = new SafeBrowsingPrototype(prefixes ->
        new SafeBrowsingPrototype.Reply(List.of(), Duration.ofMinutes(5), NOW.plusSeconds(1)));
    var result = service.assess("https://example.com/", NOW);
    assertThat(result.state()).isEqualTo(ThreatAssessment.State.NO_MATCH);
    assertThat(result.currentState(NOW.plusSeconds(1))).isEqualTo(ThreatAssessment.State.NO_MATCH);
  }

  @Test
  void indisponibilidadeEUrlNaoSuportadaPermanecemNaoVerificadas() {
    var called = new AtomicBoolean();
    var service = new SafeBrowsingPrototype(prefixes -> { called.set(true); throw new IOException("indisponível"); });
    assertThat(service.assess("https://example.com/a%3Fb", NOW).state()).isEqualTo(ThreatAssessment.State.UNVERIFIED);
    assertThat(called).isFalse();
    assertThat(service.assess("https://example.com/", NOW).state()).isEqualTo(ThreatAssessment.State.UNVERIFIED);
    assertThat(called).isTrue();
  }
}
