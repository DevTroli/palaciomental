package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

class IncidentInboxControllerTest {
  @Test
  void disabledMonitoringDoesNotDeliverOrAcknowledgeOldAlerts() {
    var jdbc = mock(JdbcTemplate.class);
    var monitor = mock(ServiceMonitoring.class);
    var controller = new IncidentInboxController(jdbc, monitor);
    assertThat(controller.pending()).isEmpty();
    assertThat(controller.confirm(1).getStatusCode().value()).isEqualTo(503);
    assertThat(controller.reject(1).getStatusCode().value()).isEqualTo(503);
    assertThat(controller.failure(1).getStatusCode().value()).isEqualTo(503);
    verifyNoInteractions(jdbc);
  }
}
