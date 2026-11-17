package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class ThreatAssessmentTest {
  private static final Instant CHECKED = Instant.parse("2026-11-15T12:00:00Z");

  @Test
  void ameacaExpiraNoPrazoDoProvedorOuEmTrintaMinutos() {
    var shortTtl = new ThreatAssessment(ThreatAssessment.State.THREAT, CHECKED, CHECKED.plusSeconds(60));
    assertThat(shortTtl.currentState(CHECKED.plusSeconds(59))).isEqualTo(ThreatAssessment.State.THREAT);
    assertThat(shortTtl.currentState(CHECKED.plusSeconds(60))).isEqualTo(ThreatAssessment.State.UNVERIFIED);
    var longTtl = new ThreatAssessment(ThreatAssessment.State.THREAT, CHECKED, CHECKED.plus(Duration.ofHours(2)));
    assertThat(longTtl.currentState(CHECKED.plusSeconds(1799))).isEqualTo(ThreatAssessment.State.THREAT);
    assertThat(longTtl.currentState(CHECKED.plusSeconds(1800))).isEqualTo(ThreatAssessment.State.UNVERIFIED);
  }

  @Test
  void ausenciaDeDeteccaoNaoSobreviveAoPrazo() {
    var result = new ThreatAssessment(ThreatAssessment.State.NO_MATCH, CHECKED, CHECKED.plusSeconds(60));
    assertThat(result.currentState(CHECKED)).isEqualTo(ThreatAssessment.State.NO_MATCH);
    assertThat(result.currentState(CHECKED.plusSeconds(60))).isEqualTo(ThreatAssessment.State.UNVERIFIED);
  }

  @Test
  void falhaOuHorarioInconsistenteNaoViramResultadoSeguro() {
    assertThat(ThreatAssessment.unverified().currentState(CHECKED)).isEqualTo(ThreatAssessment.State.UNVERIFIED);
    var result = new ThreatAssessment(ThreatAssessment.State.NO_MATCH, CHECKED, CHECKED.plusSeconds(60));
    assertThat(result.currentState(CHECKED.minusSeconds(1))).isEqualTo(ThreatAssessment.State.UNVERIFIED);
  }

  @Test
  void prazoInvalidoNaoCriaResultadoVerificado() {
    assertThatThrownBy(() -> new ThreatAssessment(ThreatAssessment.State.THREAT, CHECKED, CHECKED))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new ThreatAssessment(ThreatAssessment.State.NO_MATCH, null, null))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
