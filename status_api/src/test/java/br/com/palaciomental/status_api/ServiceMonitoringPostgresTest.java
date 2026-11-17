package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.spy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;

@EnabledIfEnvironmentVariable(named = "STATUS_TEST_DATABASE_URL", matches = ".+")
class ServiceMonitoringPostgresTest {
  @Test
  void recordsFailureAndRecoveryAcrossMonitorInstances() {
    var source = new DriverManagerDataSource(System.getenv("STATUS_TEST_DATABASE_URL"), "gc05", "gc05-temporary");
    var jdbc = new JdbcTemplate(source);
    var transactions = new TransactionTemplate(new DataSourceTransactionManager(source));
    var environment = mock(Environment.class);
    when(environment.acceptsProfiles(org.mockito.ArgumentMatchers.any(Profiles.class))).thenReturn(true);
    var monitor = new ServiceMonitoring(jdbc, transactions, environment, true, "");
    clearTestData(jdbc);

    transactions.executeWithoutResult(s -> monitor.record("inicio", false));
    ageLastCheck(jdbc);
    transactions.executeWithoutResult(s -> monitor.record("inicio", false));
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.service_incidents WHERE journey = 'inicio' AND recovered_at IS NULL", Integer.class)).isEqualTo(1);

    ageLastCheck(jdbc);
    transactions.executeWithoutResult(s -> monitor.record("inicio", true));
    ageLastCheck(jdbc);
    var restarted = new ServiceMonitoring(jdbc, transactions, environment, true, "");
    transactions.executeWithoutResult(s -> restarted.record("inicio", true));
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.service_incidents WHERE journey = 'inicio' AND recovered_at IS NOT NULL", Integer.class)).isEqualTo(1);
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.service_checks WHERE journey = 'inicio'", Integer.class)).isEqualTo(4);
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_events e JOIN guardiao.service_incidents i ON i.id = e.incident_id WHERE i.journey = 'inicio'", Integer.class)).isEqualTo(2);
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id JOIN guardiao.service_incidents i ON i.id = e.incident_id WHERE i.journey = 'inicio' AND d.channel = 'discord'", Integer.class)).isEqualTo(2);

    long incidentId = jdbc.queryForObject("SELECT id FROM guardiao.service_incidents WHERE journey = 'inicio'", Long.class);
    transactions.executeWithoutResult(s -> IncidentAlertEvents.enqueue(jdbc, incidentId, "opened", java.time.Instant.now()));
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_events WHERE incident_id = ?", Integer.class, incidentId)).isEqualTo(2);

    var dispatcher = spy(new IncidentAlertDispatcher(jdbc, transactions, monitor, "", "", "", ""));
    doReturn(IncidentAlertDispatcher.Outcome.RETRY).when(dispatcher).send(eq("discord"), any());
    dispatcher.process("discord");
    jdbc.update("UPDATE guardiao.incident_alert_deliveries SET next_attempt_at = now() - interval '1 minute' WHERE attempts = 1");
    dispatcher.process("discord");
    jdbc.update("UPDATE guardiao.incident_alert_deliveries SET next_attempt_at = now() - interval '1 minute' WHERE attempts = 2");
    dispatcher.process("discord");
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_deliveries WHERE channel = 'discord' AND status = 'failed' AND attempts = 3", Integer.class)).isEqualTo(1);
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id WHERE e.incident_id = ? AND d.channel = 'email' AND d.status = 'pending'", Integer.class, incidentId)).isEqualTo(1);
    doReturn(IncidentAlertDispatcher.Outcome.SENT).when(dispatcher).send(eq("email"), any());
    dispatcher.process("email");
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id WHERE e.incident_id = ? AND d.channel = 'email' AND d.status = 'sent'", Integer.class, incidentId)).isEqualTo(1);
    transactions.executeWithoutResult(s -> IncidentAlertEvents.enqueue(jdbc, incidentId, "extended", java.time.Instant.now()));
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id WHERE e.incident_id = ? AND d.channel = 'email'", Integer.class, incidentId)).isEqualTo(1);
  }

  @Test
  void escalatesOnlyAfterContinuousFailureAndKeepsChannelsSeparate() {
    var source = new DriverManagerDataSource(System.getenv("STATUS_TEST_DATABASE_URL"), "gc05", "gc05-temporary");
    var jdbc = new JdbcTemplate(source);
    var transactions = new TransactionTemplate(new DataSourceTransactionManager(source));
    var environment = mock(Environment.class);
    when(environment.acceptsProfiles(org.mockito.ArgumentMatchers.any(Profiles.class))).thenReturn(true);
    var monitor = new ServiceMonitoring(jdbc, transactions, environment, true, "");
    clearTestData(jdbc);
    var now = java.time.Instant.now().truncatedTo(java.time.temporal.ChronoUnit.MICROS);
    jdbc.update("INSERT INTO guardiao.service_incidents (journey, started_at) VALUES ('vitrine', ?)", java.sql.Timestamp.from(now.minusSeconds(3900)));
    for (int minutes = 0; minutes <= 10; minutes += 5) addFailure(jdbc, now.minusSeconds(minutes * 60L));
    transactions.executeWithoutResult(s -> monitor.queueEscalations("vitrine", now));
    assertThat(countEvents(jdbc, "public")).isZero();
    var publicStatus = new PublicStatusController(jdbc, monitor);
    assertThat((java.util.List<?>) publicStatus.status().getBody().get("incidentes")).isEmpty();

    addFailure(jdbc, now.minusSeconds(15 * 60L));
    transactions.executeWithoutResult(s -> monitor.queueEscalations("vitrine", now));
    assertThat(countEvents(jdbc, "public")).isEqualTo(1);
    assertThat((java.util.List<?>) publicStatus.status().getBody().get("incidentes")).hasSize(1);
    assertThat(countEvents(jdbc, "severe")).isZero();
    for (int minutes = 20; minutes <= 60; minutes += 5) addFailure(jdbc, now.minusSeconds(minutes * 60L));
    jdbc.update("UPDATE guardiao.service_checks SET successful = true WHERE journey = 'vitrine' AND checked_at = ?", java.sql.Timestamp.from(now.minusSeconds(1800)));
    transactions.executeWithoutResult(s -> monitor.queueEscalations("vitrine", now));
    assertThat(countEvents(jdbc, "severe")).isZero();
    jdbc.update("UPDATE guardiao.service_checks SET successful = false WHERE journey = 'vitrine' AND checked_at = ?", java.sql.Timestamp.from(now.minusSeconds(1800)));
    transactions.executeWithoutResult(s -> monitor.queueEscalations("vitrine", now));
    assertThat(countEvents(jdbc, "severe")).isZero();

    addFailure(jdbc, now.minusSeconds(65 * 60L));
    transactions.executeWithoutResult(s -> monitor.queueEscalations("vitrine", now));
    transactions.executeWithoutResult(s -> monitor.queueEscalations("vitrine", now));
    assertThat(countEvents(jdbc, "severe")).isEqualTo(1);
    assertThat(countEvents(jdbc, "extended")).isEqualTo(1);
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id JOIN guardiao.service_incidents i ON i.id = e.incident_id WHERE i.journey = 'vitrine' AND d.channel IN ('inbox', 'email')", Integer.class)).isEqualTo(2);

    // O aviso continua disponível se a aplicação retornar após a recuperação.
    jdbc.update("UPDATE guardiao.service_incidents SET recovered_at = ? WHERE journey = 'vitrine' AND recovered_at IS NULL", java.sql.Timestamp.from(now));
    var inbox = new IncidentInboxController(jdbc, monitor);
    var pending = inbox.pending().stream().filter(alert -> alert.journey().equals("vitrine")).toList();
    assertThat(pending).hasSize(1);
    assertThat(pending.getFirst().recoveredAt()).isNotNull();
    long eventId = pending.getFirst().id();
    inbox.confirm(eventId);
    inbox.confirm(eventId);
    assertThat(inbox.pending().stream().filter(alert -> alert.id() == eventId)).isEmpty();
    assertThat(jdbc.queryForObject("SELECT status FROM guardiao.incident_alert_deliveries WHERE event_id = ? AND channel = 'inbox'", String.class, eventId)).isEqualTo("sent");

    long oldIncident = jdbc.queryForObject("INSERT INTO guardiao.service_incidents (journey, started_at, tenant_host) VALUES ('organizacao', ?, 'example.org') RETURNING id", Long.class, java.sql.Timestamp.from(now.minusSeconds(100000)));
    transactions.executeWithoutResult(s -> IncidentAlertEvents.enqueue(jdbc, oldIncident, "severe", now.minusSeconds(90000)));
    assertThat(inbox.pending().stream().filter(alert -> alert.journey().equals("organizacao"))).isEmpty();
    new IncidentAlertDispatcher(jdbc, transactions, monitor, "", "", "", "").dispatch();
    assertThat(jdbc.queryForObject("SELECT d.status FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id WHERE e.incident_id = ? AND d.channel = 'inbox'", String.class, oldIncident)).isEqualTo("expired");

    long failingIncident = jdbc.queryForObject("INSERT INTO guardiao.service_incidents (journey, started_at) VALUES ('cadastro', ?) RETURNING id", Long.class, java.sql.Timestamp.from(now));
    transactions.executeWithoutResult(s -> IncidentAlertEvents.enqueue(jdbc, failingIncident, "severe", now));
    long failingEvent = jdbc.queryForObject("SELECT id FROM guardiao.incident_alert_events WHERE incident_id = ?", Long.class, failingIncident);
    inbox.failure(failingEvent);
    inbox.failure(failingEvent); // A próxima tentativa ainda não está liberada.
    assertThat(jdbc.queryForObject("SELECT attempts FROM guardiao.incident_alert_deliveries WHERE event_id = ? AND channel = 'inbox'", Integer.class, failingEvent)).isEqualTo(1);
    for (int attempt = 0; attempt < 2; attempt++) {
      jdbc.update("UPDATE guardiao.incident_alert_deliveries SET next_attempt_at = now() - interval '1 minute' WHERE event_id = ? AND channel = 'inbox'", failingEvent);
      inbox.failure(failingEvent);
    }
    assertThat(jdbc.queryForObject("SELECT status FROM guardiao.incident_alert_deliveries WHERE event_id = ? AND channel = 'inbox'", String.class, failingEvent)).isEqualTo("failed");
  }

  @Test
  void discordFailureFallsBackToEmailWithoutContactingRealProviders() throws Exception {
    var source = new DriverManagerDataSource(System.getenv("STATUS_TEST_DATABASE_URL"), "gc05", "gc05-temporary");
    var jdbc = new JdbcTemplate(source);
    var transactions = new TransactionTemplate(new DataSourceTransactionManager(source));
    var environment = mock(Environment.class);
    when(environment.acceptsProfiles(org.mockito.ArgumentMatchers.any(Profiles.class))).thenReturn(true);
    var monitor = new ServiceMonitoring(jdbc, transactions, environment, true, "");
    clearTestData(jdbc);
    long incidentId = jdbc.queryForObject("INSERT INTO guardiao.service_incidents (journey, started_at) VALUES ('inicio', now()) RETURNING id", Long.class);
    transactions.executeWithoutResult(s -> IncidentAlertEvents.enqueue(jdbc, incidentId, "opened", java.time.Instant.now()));

    var dispatcher = spy(new IncidentAlertDispatcher(jdbc, transactions, monitor,
        "https://discord.com/api/webhooks/123/fake-token", "fake-key", "from@example.com", "to@example.com"));
    var discord = mock(java.net.HttpURLConnection.class);
    var email = mock(java.net.HttpURLConnection.class);
    when(discord.getOutputStream()).thenAnswer(invocation -> new java.io.ByteArrayOutputStream());
    when(discord.getResponseCode()).thenReturn(429);
    when(email.getOutputStream()).thenAnswer(invocation -> new java.io.ByteArrayOutputStream());
    when(email.getResponseCode()).thenReturn(200);
    org.mockito.Mockito.doAnswer(invocation -> ((java.net.URI) invocation.getArgument(0)).getHost().equals("discord.com") ? discord : email)
        .when(dispatcher).openConnection(any());

    for (int attempt = 0; attempt < 3; attempt++) {
      dispatcher.process("discord");
      jdbc.update("UPDATE guardiao.incident_alert_deliveries SET next_attempt_at = now() - interval '1 minute' WHERE channel = 'discord'");
    }
    dispatcher.process("email");
    assertThat(jdbc.queryForObject("SELECT status FROM guardiao.incident_alert_deliveries WHERE channel = 'discord'", String.class)).isEqualTo("failed");
    assertThat(jdbc.queryForObject("SELECT status FROM guardiao.incident_alert_deliveries WHERE channel = 'email'", String.class)).isEqualTo("sent");
    org.mockito.Mockito.verify(email).setRequestProperty(eq("Idempotency-Key"), org.mockito.ArgumentMatchers.startsWith("pm-incident/"));
  }

  private static void addFailure(JdbcTemplate jdbc, java.time.Instant at) {
    jdbc.update("INSERT INTO guardiao.service_checks (journey, checked_at, successful) VALUES ('vitrine', ?, false)", java.sql.Timestamp.from(at));
  }

  private static int countEvents(JdbcTemplate jdbc, String type) {
    return jdbc.queryForObject("SELECT count(*) FROM guardiao.incident_alert_events e JOIN guardiao.service_incidents i ON i.id = e.incident_id WHERE i.journey = 'vitrine' AND e.event_type = ?", Integer.class, type);
  }

  private static void clearTestData(JdbcTemplate jdbc) {
    jdbc.update("DELETE FROM guardiao.incident_alert_events WHERE incident_id IN (SELECT id FROM guardiao.service_incidents WHERE journey IN ('inicio', 'vitrine', 'organizacao', 'cadastro'))");
    jdbc.update("DELETE FROM guardiao.service_incidents WHERE journey IN ('inicio', 'vitrine', 'organizacao', 'cadastro')");
    jdbc.update("DELETE FROM guardiao.service_checks WHERE journey IN ('inicio', 'vitrine', 'organizacao', 'cadastro')");
  }

  private static void ageLastCheck(JdbcTemplate jdbc) {
    jdbc.update("UPDATE guardiao.service_checks SET checked_at = checked_at - interval '5 minutes' WHERE journey = 'inicio'");
  }
}
