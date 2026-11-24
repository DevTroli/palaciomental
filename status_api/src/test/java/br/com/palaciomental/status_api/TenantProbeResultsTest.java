package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

class TenantProbeResultsTest {
  private static final UUID ORGANIZATION = UUID.randomUUID();

  @Test
  void failedLoginDoesNotCreateDependentFailures() {
    var jdbc = mock(JdbcTemplate.class);
    var monitor = mock(ServiceMonitoring.class);
    when(monitor.enabled()).thenReturn(true);
    when(jdbc.queryForList(any(String.class), eq(UUID.class), eq("camppg.example.org")))
        .thenReturn(List.of(ORGANIZATION));
    var controller = new TenantProbeResults(jdbc, monitor, "camppg.example.org");

    var response = controller.publish(new TenantProbeResults.Result("https://camppg.example.org", false, false, false));

    assertThat(response.getStatusCode().value()).isEqualTo(204);
    verify(monitor).enabled();
    verify(monitor).record("sondagem:" + ORGANIZATION + ":login", false);
    verifyNoMoreInteractions(monitor);
  }

  @Test
  void authenticatedChecksUseIncidentAwareMonitoring() {
    var jdbc = mock(JdbcTemplate.class);
    var monitor = mock(ServiceMonitoring.class);
    when(monitor.enabled()).thenReturn(true);
    when(jdbc.queryForList(any(String.class), eq(UUID.class), eq("camppg.example.org")))
        .thenReturn(List.of(ORGANIZATION));
    var controller = new TenantProbeResults(jdbc, monitor, "camppg.example.org");

    var response = controller.publish(new TenantProbeResults.Result("https://camppg.example.org", true, false, true));

    assertThat(response.getStatusCode().value()).isEqualTo(204);
    verify(monitor).record("sondagem:" + ORGANIZATION + ":login", true);
    verify(monitor).record("sondagem:" + ORGANIZATION + ":projetos", false);
    verify(monitor).record("sondagem:" + ORGANIZATION + ":programas_e_turmas", true);
  }
}
