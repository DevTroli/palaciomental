package br.com.palaciomental.status_api;

import io.swagger.v3.oas.annotations.Hidden;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@Hidden
@RestController
public class TenantProbeResults {
  record Journey(String key, String name) {
    String id(Object organizationId) {
      return "sondagem:" + organizationId + ":" + key;
    }
  }

  static final List<Journey> JOURNEYS = List.of(
      new Journey("login", "Login de membro"),
      new Journey("projetos", "Consulta de projetos"),
      new Journey("programas_e_turmas", "Consulta de programas e turmas"));

  public record Result(String origin, Boolean login, Boolean projetos, Boolean programas_e_turmas) {}

  private final JdbcTemplate jdbc;
  private final ServiceMonitoring monitor;
  private final String hostname;

  public TenantProbeResults(JdbcTemplate jdbc, ServiceMonitoring monitor,
      @Value("${STATUS_TENANT_PROBE_HOST:}") String hostname) {
    this.jdbc = jdbc;
    this.monitor = monitor;
    this.hostname = hostname;
  }

  @Transactional
  @PostMapping("/v1/guardiao/sondagens")
  public ResponseEntity<Void> publish(@RequestBody Result result) {
    if (!monitor.enabled() || hostname.isBlank()) return ResponseEntity.notFound().build();
    if (!("https://" + hostname).equals(result.origin()) || result.login() == null
        || result.projetos() == null || result.programas_e_turmas() == null
        || (!result.login() && (result.projetos() || result.programas_e_turmas()))) {
      return ResponseEntity.badRequest().build();
    }
    var ids = jdbc.queryForList("SELECT organization_id FROM guardiao.monitored_tenants "
        + "WHERE hostname = ? AND synced_at >= now() - interval '10 minutes'", java.util.UUID.class, hostname);
    if (ids.isEmpty()) return ResponseEntity.notFound().build();

    var outcomes = List.of(result.login(), result.projetos(), result.programas_e_turmas());
    var now = Timestamp.from(Instant.now());
    for (int i = 0; i < JOURNEYS.size(); i++) {
      record(JOURNEYS.get(i).id(ids.getFirst()), outcomes.get(i), now);
    }
    return ResponseEntity.noContent().build();
  }

  private void record(String id, boolean success, Timestamp now) {
    jdbc.queryForObject("SELECT pg_advisory_xact_lock(hashtext(?)) IS NULL", Boolean.class, id);
    jdbc.update("INSERT INTO guardiao.service_journeys (journey, started_at) VALUES (?, ?) "
        + "ON CONFLICT (journey) DO NOTHING", id, now);
    jdbc.update("INSERT INTO guardiao.service_checks (journey, checked_at, successful) "
        + "SELECT ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM guardiao.service_checks WHERE journey = ? "
        + "AND checked_at >= date_bin(interval '5 minutes', CAST(? AS timestamptz), timestamptz '2000-01-01'))",
        id, now, success, id, now);
  }
}
