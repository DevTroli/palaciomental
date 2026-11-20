package br.com.palaciomental.status_api.guardian;

import java.time.Duration;
import java.time.Instant;

/** Uma tentativa pertence a um ciclo; três ciclos distintos confirmam a falha. */
public final class VerificationCyclePolicy {
  public static final int MAX_ATTEMPTS_PER_CYCLE = 3;
  public static final int FAILED_CYCLES_TO_CONFIRM = 3;
  public static final Duration CYCLE_INTERVAL = Duration.ofHours(72);
  public static final Duration MAX_JITTER = Duration.ofHours(2);

  private VerificationCyclePolicy() {}

  public static boolean shouldRetry(int attempts, boolean transientFailure) {
    if (attempts < 1 || attempts > MAX_ATTEMPTS_PER_CYCLE) {
      throw new IllegalArgumentException("Número de tentativas inválido");
    }
    return transientFailure && attempts < MAX_ATTEMPTS_PER_CYCLE;
  }

  public static int consecutiveFailures(int previous, LinkStatus status) {
    if (previous < 0) {
      throw new IllegalArgumentException("Contagem de ciclos inválida");
    }
    return switch (status) {
      case QUEBRADO, SEM_RESPOSTA -> previous >= FAILED_CYCLES_TO_CONFIRM
          ? FAILED_CYCLES_TO_CONFIRM : previous + 1;
      case ACESSIVEL, REDIRECIONADO, REQUER_LOGIN -> 0;
    };
  }

  public static boolean isConfirmedFailure(int consecutiveFailures) {
    return consecutiveFailures >= FAILED_CYCLES_TO_CONFIRM;
  }

  public static Instant nextCycleAt(Instant completedAt, Duration jitter) {
    if (jitter.isNegative() || jitter.compareTo(MAX_JITTER) > 0) {
      throw new IllegalArgumentException("Jitter fora do intervalo permitido");
    }
    return completedAt.plus(CYCLE_INTERVAL).plus(jitter);
  }
}
