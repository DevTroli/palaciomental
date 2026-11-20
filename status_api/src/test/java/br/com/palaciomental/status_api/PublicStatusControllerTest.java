package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.util.Map;
import java.util.List;
import java.time.Instant;
import java.sql.ResultSet;
import java.sql.Timestamp;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

class PublicStatusControllerTest {
  @Test
  void firstDayStartsAtFirstRealCheckInsteadOfMidnight() {
    Instant first = Instant.parse("2026-11-17T11:00:00Z");
    Instant now = first.plusSeconds(1800);
    var history = PublicStatusController.history(List.of(new PublicStatusController.Check(first, true),
        new PublicStatusController.Check(first.plusSeconds(900), true),
        new PublicStatusController.Check(now, true)), first, now);
    assertThat(history).hasSize(1);
    assertThat(history.getFirst()).containsEntry("data", "2026-11-17")
        .containsEntry("esperadas", 3).containsEntry("coletas", 3).containsEntry("estado", "funcionando");
  }

  @Test
  void missingDaysAfterMonitoringStartsRemainVisible() {
    Instant first = Instant.parse("2026-11-15T11:00:00Z");
    var history = PublicStatusController.history(List.of(new PublicStatusController.Check(first, true)),
        first, Instant.parse("2026-11-17T11:00:00Z"));
    assertThat(history).hasSize(3);
    assertThat(history.get(1)).containsEntry("data", "2026-11-16").containsEntry("estado", "sem_coleta");
    assertThat(PublicStatusController.history(List.of(), null, Instant.now())).isEmpty();
  }

  @Test
  void monitoringStartRemainsAvailableAfterSamplesExpire() {
    Instant startedAt = Instant.parse("2026-10-01T11:00:00Z");
    var jdbc = mock(JdbcTemplate.class);
    when(jdbc.queryForObject(anyString(), eq(Timestamp.class), any(), any())).thenReturn(Timestamp.from(startedAt));

    var controller = new PublicStatusController(jdbc, mock(ServiceMonitoring.class));
    Instant persistedStart = controller.firstMonitoringStart("inicio", List.of());
    var history = PublicStatusController.history(List.of(), persistedStart, Instant.parse("2026-11-17T11:00:00Z"));

    assertThat(history).hasSize(30);
    assertThat(history.getFirst()).containsEntry("data", "2026-10-19").containsEntry("estado", "sem_coleta");
  }

  @Test
  void currentHealthIncludesEveryTenantAcrossTimeBinBoundaries() {
    Instant now = Instant.parse("2026-01-01T12:05:02Z");
    var checks = List.of(new PublicStatusController.Check(now.minusSeconds(3), false),
        new PublicStatusController.Check(now.minusSeconds(1), true));
    assertThat(PublicStatusController.currentTenantState(checks, now)).isEqualTo("falha");
  }

  @Test
  void missingOrStaleTenantChecksCannotReportHealthy() {
    Instant now = Instant.parse("2026-01-01T12:05:02Z");
    var healthy = new PublicStatusController.Check(now.minusSeconds(1), true);
    assertThat(PublicStatusController.currentTenantState(List.of(healthy,
        new PublicStatusController.Check(null, false)), now)).isEqualTo("sem_coleta");
    assertThat(PublicStatusController.currentTenantState(List.of(healthy,
        new PublicStatusController.Check(now.minusSeconds(1801), true)), now)).isEqualTo("sem_coleta");
    assertThat(PublicStatusController.currentTenantState(List.of(healthy), now)).isEqualTo("funcionando");
  }

  @Test
  void disabledMonitoringDoesNotExposeStoredData() {
    var jdbc = mock(JdbcTemplate.class);
    var monitor = mock(ServiceMonitoring.class);
    var controller = new PublicStatusController(jdbc, monitor);

    var response = controller.status();
    assertThat(response.getBody()).isEqualTo(Map.of("disponivel", false));
    assertThat(response.getHeaders().getCacheControl()).contains("no-store");
    verifyNoInteractions(jdbc);
  }

  @Test
  void databaseFailureReportsUnavailable() {
    var jdbc = mock(JdbcTemplate.class);
    var monitor = mock(ServiceMonitoring.class);
    when(monitor.enabled()).thenReturn(true);
    when(jdbc.query(anyString(), org.mockito.ArgumentMatchers.<RowMapper<Object>>any(), any(), any(), any()))
        .thenThrow(new DataAccessResourceFailureException("offline"));

    assertThat(new PublicStatusController(jdbc, monitor).status().getBody()).isEqualTo(Map.of("disponivel", false));
  }

  @Test
  void missingChecksAreNeverReportedAsSuccess() {
    var jdbc = mock(JdbcTemplate.class);
    var monitor = mock(ServiceMonitoring.class);
    when(monitor.enabled()).thenReturn(true);
    when(jdbc.query(anyString(), org.mockito.ArgumentMatchers.<RowMapper<Object>>any(), any(), any(), any()))
        .thenReturn(List.of());

    var body = new PublicStatusController(jdbc, monitor).status().getBody();
    assertThat(body).isNotNull();
    var journeys = (List<?>) body.get("jornadas");
    assertThat(journeys).hasSize(5);
    for (Object value : journeys) {
      var journey = (Map<?, ?>) value;
      assertThat(journey.get("estado")).isEqualTo("sem_coleta");
      assertThat(journey.keySet()).isEqualTo(java.util.Set.of("nome", "estado", "ultima_verificacao", "dias"));
      for (Object day : (List<?>) journey.get("dias")) {
        assertThat(((Map<?, ?>) day).get("estado")).isEqualTo("sem_coleta");
      }
    }
  }

  @Test
  void oldFailureRemainsInHistoryButIsNotCurrent() {
    var jdbc = mock(JdbcTemplate.class);
    var monitor = mock(ServiceMonitoring.class);
    when(monitor.enabled()).thenReturn(true);
    when(jdbc.query(anyString(), org.mockito.ArgumentMatchers.<RowMapper<Object>>any(), any(), any(), any()))
        .thenAnswer(invocation -> {
          if (((String) invocation.getArgument(0)).contains("service_incidents")) return List.of();
          RowMapper<?> mapper = invocation.getArgument(1);
          var row = mock(ResultSet.class);
          when(row.getTimestamp(1)).thenReturn(Timestamp.from(Instant.now().minusSeconds(3600)));
          when(row.getBoolean(2)).thenReturn(false);
          return List.of(mapper.mapRow(row, 0));
        });

    var body = new PublicStatusController(jdbc, monitor).status().getBody();
    assertThat(body).isNotNull();
    var journey = (Map<?, ?>) ((List<?>) body.get("jornadas")).getFirst();
    assertThat(journey.get("estado")).isEqualTo("sem_coleta");
    assertThat((List<?>) journey.get("dias")).anySatisfy(day ->
        assertThat(((Map<?, ?>) day).get("estado")).isEqualTo("falha"));
  }
}
