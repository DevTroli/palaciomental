package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;

class ThreatServiceTest {
  @Test
  void endpointSemChaveRetornaNaoVerificadoERecusaLoteExcessivo() {
    var controller = new GuardiaoController(new JdbcTemplate(), new TransactionTemplate(), new ThreatService(""));
    var response = controller.threats(new GuardiaoController.ThreatRequest(List.of("https://example.com/")));
    assertThat(response.getStatusCode().value()).isEqualTo(200);
    assertThat(response.getBody().getFirst().state()).isEqualTo("UNVERIFIED");
    assertThat(controller.threats(new GuardiaoController.ThreatRequest(java.util.Collections.nCopies(7, "https://example.com")))
        .getStatusCode().value()).isEqualTo(400);
  }
}
