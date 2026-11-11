package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class VerificationCyclePolicyTest {
  @Test
  void limitaTentativasSemConfundiLasComCiclos() {
    assertThat(VerificationCyclePolicy.shouldRetry(1, true)).isTrue();
    assertThat(VerificationCyclePolicy.shouldRetry(2, true)).isTrue();
    assertThat(VerificationCyclePolicy.shouldRetry(3, true)).isFalse();
    assertThat(VerificationCyclePolicy.shouldRetry(1, false)).isFalse();
    assertThatThrownBy(() -> VerificationCyclePolicy.shouldRetry(0, true))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void confirmaDepoisDeTresCiclosComFalhaEReiniciaNaRecuperacao() {
    int failures = 0;
    for (int i = 0; i < 3; i++) {
      failures = VerificationCyclePolicy.consecutiveFailures(failures, LinkStatus.SEM_RESPOSTA);
      assertThat(VerificationCyclePolicy.isConfirmedFailure(failures)).isEqualTo(i == 2);
    }
    assertThat(VerificationCyclePolicy.consecutiveFailures(failures, LinkStatus.ACESSIVEL)).isZero();
  }

  @Test
  void agendaSomenteApos48HorasComJitterLimitado() {
    Instant now = Instant.parse("2026-01-01T00:00:00Z");
    assertThat(VerificationCyclePolicy.nextCycleAt(now, Duration.ofMinutes(30)))
        .isEqualTo(now.plus(Duration.ofHours(48)).plus(Duration.ofMinutes(30)));
    assertThatThrownBy(() -> VerificationCyclePolicy.nextCycleAt(now, Duration.ofHours(3)))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
