package br.com.palaciomental.status_api.guardian;

import java.time.Duration;
import java.time.Instant;
import java.util.Objects;

/** Resultado de reputação, independente da disponibilidade HTTP do link. */
public record ThreatAssessment(State state, Instant checkedAt, Instant expiresAt) {
  public enum State { THREAT, NO_MATCH, UNVERIFIED }

  private static final Duration MAX_THREAT_AGE = Duration.ofMinutes(30);

  public ThreatAssessment {
    Objects.requireNonNull(state, "Estado obrigatório");
    if (state == State.UNVERIFIED) {
      if (checkedAt != null || expiresAt != null) throw new IllegalArgumentException("Estado não verificado não tem prazo");
    } else if (checkedAt == null || expiresAt == null || !expiresAt.isAfter(checkedAt)) {
      throw new IllegalArgumentException("Resultado verificado exige prazo válido");
    }
  }

  public static ThreatAssessment unverified() {
    return new ThreatAssessment(State.UNVERIFIED, null, null);
  }

  /** Resultado vencido ou com relógio inconsistente nunca autoriza afirmar uma classificação. */
  public State currentState(Instant now) {
    Objects.requireNonNull(now, "Horário obrigatório");
    if (state == State.UNVERIFIED || now.isBefore(checkedAt) || !now.isBefore(expiresAt)
        || (state == State.THREAT && Duration.between(checkedAt, now).compareTo(MAX_THREAT_AGE) >= 0)) {
      return State.UNVERIFIED;
    }
    return state;
  }
}
