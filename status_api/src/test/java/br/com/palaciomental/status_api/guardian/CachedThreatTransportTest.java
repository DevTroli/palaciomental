package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class CachedThreatTransportTest {
  static class MutableClock extends Clock {
    Instant time = Instant.parse("2026-11-15T12:00:00Z");
    @Override public ZoneId getZone() { return ZoneOffset.UTC; }
    @Override public Clock withZone(ZoneId zone) { return this; }
    @Override public Instant instant() { return time; }
  }

  @Test
  void respostasVaziasSaoGuardadasPorPrefixoAteExpirar() throws Exception {
    var clock = new MutableClock();
    var calls = new AtomicInteger();
    var requests = new java.util.ArrayList<List<String>>();
    var transport = new CachedThreatTransport(prefixes -> {
      calls.incrementAndGet();
      requests.add(List.copyOf(prefixes));
      return new SafeBrowsingPrototype.Reply(List.of(), Duration.ofMinutes(5));
    }, clock);
    String a = Base64.getEncoder().encodeToString(new byte[]{1, 2, 3, 4});
    String b = Base64.getEncoder().encodeToString(new byte[]{5, 6, 7, 8});
    var first = transport.search(List.of(a));
    clock.time = clock.time.plusSeconds(60);
    var second = transport.search(List.of(a, b));
    assertThat(calls.get()).isEqualTo(2);
    assertThat(requests.get(1)).containsExactly(b);
    assertThat(second.receivedAt()).isEqualTo(first.receivedAt());
    clock.time = clock.time.plus(Duration.ofHours(24));
    transport.search(List.of(a));
    assertThat(calls.get()).isEqualTo(3);
  }

  @Test
  void respostaComCorrespondenciasNaoTemValidadeEstendida() throws Exception {
    var clock = new MutableClock();
    byte[] hash = new byte[32];
    String prefix = Base64.getEncoder().encodeToString(java.util.Arrays.copyOf(hash, 4));
    var match = new ThreatHashMatcher.Match(hash, List.of(new ThreatHashMatcher.Detail("MALWARE", List.of())));
    var transport = new CachedThreatTransport(prefixes ->
        new SafeBrowsingPrototype.Reply(List.of(match), Duration.ofMinutes(5)), clock);
    assertThat(transport.search(List.of(prefix)).cacheDuration()).isEqualTo(Duration.ofMinutes(5));
  }

  @Test
  void negativoAntigoNaoEnvelheceAmeacaRecente() throws Exception {
    var clock = new MutableClock();
    byte[] hash = new byte[32];
    hash[0] = 5;
    String negative = Base64.getEncoder().encodeToString(new byte[]{1, 2, 3, 4});
    String positive = Base64.getEncoder().encodeToString(java.util.Arrays.copyOf(hash, 4));
    var match = new ThreatHashMatcher.Match(hash, List.of(new ThreatHashMatcher.Detail("MALWARE", List.of())));
    var requests = new java.util.ArrayList<List<String>>();
    var transport = new CachedThreatTransport(prefixes -> {
      requests.add(List.copyOf(prefixes));
      return new SafeBrowsingPrototype.Reply(prefixes.contains(positive) ? List.of(match) : List.of(),
          Duration.ofMinutes(5));
    }, clock);
    transport.search(List.of(negative));
    clock.time = clock.time.plus(Duration.ofHours(1));
    var reply = transport.search(List.of(negative, positive));
    assertThat(requests).hasSize(3);
    assertThat(requests.get(2)).containsExactly(negative, positive);
    assertThat(reply.receivedAt()).isEqualTo(clock.instant());
    var result = ThreatHashMatcher.evaluate(List.of(hash), reply.matches(), reply.receivedAt(), reply.cacheDuration());
    assertThat(result.currentState(clock.instant())).isEqualTo(ThreatAssessment.State.THREAT);
    assertThat(result.expiresAt()).isEqualTo(clock.instant().plus(Duration.ofMinutes(5)));
    assertThat(result.currentState(result.expiresAt())).isEqualTo(ThreatAssessment.State.UNVERIFIED);
    transport.search(List.of(negative, positive));
    assertThat(requests).hasSize(3);
  }
}
