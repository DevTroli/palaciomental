package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class LinkClassificationTest {
  @Test
  void classificaRespostasSemConfundirAusenciaDeRespostaComSucesso() {
    assertThat(LinkClassification.fromHttp(200, false)).isEqualTo(LinkStatus.ACESSIVEL);
    assertThat(LinkClassification.fromHttp(302, true)).isEqualTo(LinkStatus.REDIRECIONADO);
    assertThat(LinkClassification.fromHttp(401, false)).isEqualTo(LinkStatus.REQUER_LOGIN);
    assertThat(LinkClassification.fromHttp(403, false)).isEqualTo(LinkStatus.REQUER_LOGIN);
    assertThat(LinkClassification.fromHttp(404, false)).isEqualTo(LinkStatus.QUEBRADO);
    assertThat(LinkClassification.fromHttp(410, false)).isEqualTo(LinkStatus.QUEBRADO);
    assertThat(LinkClassification.fromHttp(429, false)).isEqualTo(LinkStatus.SEM_RESPOSTA);
    assertThat(LinkClassification.fromHttp(503, false)).isEqualTo(LinkStatus.SEM_RESPOSTA);
    assertThatThrownBy(() -> LinkClassification.fromHttp(302, false))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void soErrosTemporariosDevemSerRetentados() {
    assertThat(LinkClassification.isTransient(429)).isTrue();
    assertThat(LinkClassification.isTransient(503)).isTrue();
    assertThat(LinkClassification.isTransient(404)).isFalse();
  }
}
