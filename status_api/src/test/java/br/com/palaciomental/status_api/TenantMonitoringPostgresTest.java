package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

@EnabledIfEnvironmentVariable(named = "STATUS_TEST_DATABASE_URL", matches = ".+")
class TenantMonitoringPostgresTest {
  private JdbcTemplate jdbc() {
    return new JdbcTemplate(new DriverManagerDataSource(System.getenv("STATUS_TEST_DATABASE_URL"), "gc05", "gc05-temporary"));
  }

  @Test
  void latestTenantFailureSurvivesHistoricalTimeBinBoundary() {
    var jdbc = jdbc();
    UUID failed = UUID.randomUUID();
    UUID healthy = UUID.randomUUID();
    Instant boundary = Instant.ofEpochSecond(Instant.now().getEpochSecond() / 300 * 300);
    try {
      for (UUID id : List.of(failed, healthy)) {
        jdbc.update("INSERT INTO guardiao.monitored_tenants(organization_id, hostname) VALUES (?, ?)", id, id + ".example.org");
      }
      jdbc.update("INSERT INTO guardiao.service_checks VALUES (?, ?, false)", "organizacao:" + failed, java.sql.Timestamp.from(boundary.minusSeconds(1)));
      jdbc.update("INSERT INTO guardiao.service_checks VALUES (?, ?, true)", "organizacao:" + healthy, java.sql.Timestamp.from(boundary.plusSeconds(1)));
      var monitoring = mock(ServiceMonitoring.class);
      when(monitoring.enabled()).thenReturn(true);
      var body = new PublicStatusController(jdbc, monitoring).status().getBody();
      assertThat(body).isNotNull();
      var journeys = (List<?>) body.get("jornadas");
      assertThat(journeys).anySatisfy(value -> {
        var journey = (Map<?, ?>) value;
        assertThat(journey.get("nome")).isEqualTo("Entrada da organização");
        assertThat(journey.get("estado")).isEqualTo("falha");
      });
    } finally {
      for (UUID id : List.of(failed, healthy)) {
        jdbc.update("DELETE FROM guardiao.service_checks WHERE journey = ?", "organizacao:" + id);
        jdbc.update("DELETE FROM guardiao.monitored_tenants WHERE organization_id = ?", id);
      }
    }
  }

  @Test
  void publicOrganizationStatusIsolatesChecksAndIncidents() {
    var jdbc = jdbc();
    UUID first = UUID.randomUUID();
    UUID second = UUID.randomUUID();
    var monitor = mock(ServiceMonitoring.class);
    when(monitor.enabled()).thenReturn(true);
    var controller = new PublicStatusController(jdbc, monitor);
    try {
      for (UUID id : List.of(first, second)) {
        jdbc.update("INSERT INTO guardiao.monitored_tenants(organization_id, hostname, slug, display_name) VALUES (?, ?, ?, ?)",
            id, id + ".example.org", id.toString(), "Organização " + id);
        jdbc.update("INSERT INTO guardiao.service_checks VALUES (?, now(), ?)",
            "organizacao:" + id, id.equals(second));
      }
      long incident = jdbc.queryForObject("INSERT INTO guardiao.service_incidents(journey, started_at) VALUES (?, now()) RETURNING id",
          Long.class, "organizacao:" + first);
      IncidentAlertEvents.enqueue(jdbc, incident, "public", Instant.now());

      var failed = controller.organizationStatus(first.toString()).getBody();
      var healthy = controller.organizationStatus(second.toString()).getBody();
      assertThat((List<?>) failed.get("incidentes")).hasSize(1);
      assertThat((List<?>) healthy.get("incidentes")).isEmpty();
      assertThat(((Map<?, ?>) ((List<?>) failed.get("jornadas")).getFirst()).get("estado")).isEqualTo("falha");
      assertThat(((Map<?, ?>) ((List<?>) healthy.get("jornadas")).getFirst()).get("estado")).isEqualTo("funcionando");
      jdbc.update("UPDATE guardiao.service_checks SET successful = true WHERE journey = ?", "organizacao:" + first);
      jdbc.update("UPDATE guardiao.service_incidents SET recovered_at = now() WHERE id = ?", incident);
      var recovered = controller.organizationStatus(first.toString()).getBody();
      var recoveredIncident = (Map<?, ?>) ((List<?>) recovered.get("incidentes")).getFirst();
      assertThat(recoveredIncident.get("fim")).isInstanceOfSatisfying(String.class, end -> assertThat(end).isNotBlank());

      jdbc.update("DELETE FROM guardiao.service_checks WHERE journey = ?", "organizacao:" + second);
      var missing = controller.organizationStatus(second.toString()).getBody();
      assertThat(((Map<?, ?>) ((List<?>) missing.get("jornadas")).getFirst()).get("estado")).isEqualTo("sem_coleta");

      jdbc.update("UPDATE guardiao.monitored_tenants SET synced_at = now() - interval '11 minutes' WHERE organization_id = ?", first);
      assertThat(controller.organizationStatus(first.toString()).getStatusCode().value()).isEqualTo(404);
    } finally {
      jdbc.update("DELETE FROM guardiao.incident_alert_events WHERE incident_id IN (SELECT id FROM guardiao.service_incidents WHERE journey = ?)",
          "organizacao:" + first);
      jdbc.update("DELETE FROM guardiao.service_incidents WHERE journey = ?", "organizacao:" + first);
      for (UUID id : List.of(first, second)) {
        jdbc.update("DELETE FROM guardiao.service_checks WHERE journey = ?", "organizacao:" + id);
        jdbc.update("DELETE FROM guardiao.monitored_tenants WHERE organization_id = ?", id);
      }
    }
  }

  @Test
  void rejectingTenantSpecificAlertActuallyRemovesItFromTheQueue() {
    var jdbc = jdbc();
    long incident = jdbc.queryForObject("INSERT INTO guardiao.service_incidents(journey, started_at, tenant_host) VALUES (?, now(), 'removed.example.org') RETURNING id",
        Long.class, "organizacao:" + UUID.randomUUID());
    try {
      IncidentAlertEvents.enqueue(jdbc, incident, "severe", Instant.now());
      long event = jdbc.queryForObject("SELECT id FROM guardiao.incident_alert_events WHERE incident_id = ?", Long.class, incident);
      var monitoring = mock(ServiceMonitoring.class);
      when(monitoring.enabled()).thenReturn(true);
      var inbox = new IncidentInboxController(jdbc, monitoring);
      assertThat(inbox.reject(event).getStatusCode().value()).isEqualTo(204);
      assertThat(jdbc.queryForObject("SELECT status FROM guardiao.incident_alert_deliveries WHERE event_id = ? AND channel = 'inbox'", String.class, event)).isEqualTo("failed");
      assertThat(inbox.pending()).noneMatch(alert -> alert.id() == event);
    } finally {
      jdbc.update("DELETE FROM guardiao.incident_alert_events WHERE incident_id = ?", incident);
      jdbc.update("DELETE FROM guardiao.service_incidents WHERE id = ?", incident);
    }
  }
}
