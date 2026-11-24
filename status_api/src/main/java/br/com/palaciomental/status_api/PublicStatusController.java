package br.com.palaciomental.status_api;

import io.swagger.v3.oas.annotations.Hidden;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@Hidden
@RestController
public class PublicStatusController {
  private static final ZoneId DISPLAY_ZONE = ZoneId.of("America/Sao_Paulo");
  private static final Map<String, String> NAMES = Map.of(
      "inicio", "Página inicial", "vitrine", "Vitrine de projetos", "entrada", "Entrada", "cadastro", "Cadastro", "organizacao", "Entrada da organização");
  private final JdbcTemplate jdbc;
  private final ServiceMonitoring monitor;

  public PublicStatusController(JdbcTemplate jdbc, ServiceMonitoring monitor) {
    this.jdbc = jdbc;
    this.monitor = monitor;
  }

  @GetMapping({"/v1/status/publico", "/v1/status-publico"})
  public ResponseEntity<Map<String, Object>> status() {
    if (!monitor.enabled() && !monitor.localPreview()) return response(Map.of("disponivel", false));
    try {
      Instant now = Instant.now();
      LocalDate today = LocalDate.now(DISPLAY_ZONE);
      var start = today.minusDays(29).atStartOfDay(DISPLAY_ZONE).toInstant();
      var journeys = new ArrayList<Map<String, Object>>();
      for (String id : List.of("inicio", "vitrine", "entrada", "cadastro", "organizacao")) {
        var checks = jdbc.query("SELECT max(checked_at), bool_and(successful) FROM guardiao.service_checks "
                + "WHERE (journey = ? OR (? = 'organizacao' AND journey LIKE 'organizacao:%')) AND checked_at >= ? "
                + "GROUP BY date_bin(interval '15 minutes', checked_at, timestamptz '2000-01-01') ORDER BY max(checked_at) DESC",
            (rs, row) -> new Check(rs.getTimestamp(1).toInstant(), rs.getBoolean(2)), id, id, java.sql.Timestamp.from(start));
        var days = history(checks, firstMonitoringStart(id, checks), now);
        Check latest = id.equals("organizacao") ? (checks.isEmpty() ? null : checks.getFirst()) : latestCheck(id);
        String state = currentState(id, latest, now);
        journeys.add(Map.of("nome", NAMES.get(id), "estado", state, "ultima_verificacao", latest == null ? "" : latest.at().toString(), "dias", days));
      }
      var incidents = jdbc.query("SELECT i.journey, i.started_at, i.recovered_at FROM guardiao.service_incidents i "
              + "WHERE i.retired_at IS NULL AND EXISTS (SELECT 1 FROM guardiao.incident_alert_events e WHERE e.incident_id = i.id AND e.event_type = 'public') "
              + "AND (i.started_at >= ? OR i.recovered_at IS NULL OR i.recovered_at >= ?) ORDER BY i.started_at DESC LIMIT 100",
          (rs, row) -> Map.of("jornada", journeyName(rs.getString(1)), "inicio", rs.getTimestamp(2).toInstant().toString(),
              "fim", rs.getTimestamp(3) == null ? "" : rs.getTimestamp(3).toInstant().toString()), java.sql.Timestamp.from(start), java.sql.Timestamp.from(start));
      return response(Map.of("disponivel", true, "jornadas", journeys, "incidentes", incidents));
    } catch (DataAccessException e) {
      return response(Map.of("disponivel", false));
    }
  }

  @GetMapping("/v1/status/org/{slug}")
  public ResponseEntity<Map<String, Object>> organizationStatus(@PathVariable String slug) {
    if (slug.length() > 80 || !slug.matches("[A-Za-z0-9_-]+")) {
      return ResponseEntity.notFound().build();
    }
    if (!monitor.enabled() && !monitor.localPreview()) return response(Map.of("disponivel", false));
    try {
      var organizations = jdbc.query("SELECT organization_id, display_name, primary_color, accent_color FROM guardiao.monitored_tenants "
              + "WHERE slug = ? AND display_name IS NOT NULL AND synced_at >= now() - interval '10 minutes'",
          (rs, row) -> new Organization(rs.getObject(1, java.util.UUID.class), rs.getString(2), rs.getString(3), rs.getString(4)), slug);
      if (organizations.isEmpty()) return ResponseEntity.notFound().build();
      Organization organization = organizations.getFirst();
      Instant now = Instant.now();
      LocalDate today = LocalDate.now(DISPLAY_ZONE);
      var start = today.minusDays(29).atStartOfDay(DISPLAY_ZONE).toInstant();
      String journeyId = "organizacao:" + organization.id();
      var journeys = new ArrayList<Map<String, Object>>();
      journeys.add(tenantJourney(journeyId, "Página de entrada", start, now, true));
      for (var probe : TenantProbeResults.JOURNEYS) {
        var journey = tenantJourney(probe.id(organization.id()), probe.name(), start, now, false);
        if (journey != null) journeys.add(journey);
      }
      var incidents = jdbc.query("SELECT i.journey, i.started_at, i.recovered_at FROM guardiao.service_incidents i "
              + "WHERE (i.journey = ? OR i.journey LIKE ?) AND i.retired_at IS NULL "
              + "AND EXISTS (SELECT 1 FROM guardiao.incident_alert_events e "
              + "WHERE e.incident_id = i.id AND e.event_type = 'public') "
              + "AND (i.started_at >= ? OR i.recovered_at IS NULL OR i.recovered_at >= ?) "
              + "ORDER BY i.started_at DESC LIMIT 100",
          (rs, row) -> Map.of("jornada", journeyName(rs.getString(1)), "inicio", rs.getTimestamp(2).toInstant().toString(),
              "fim", rs.getTimestamp(3) == null ? "" : rs.getTimestamp(3).toInstant().toString()),
          journeyId, "sondagem:" + organization.id() + ":%", java.sql.Timestamp.from(start), java.sql.Timestamp.from(start));
      return response(Map.of("disponivel", true, "organizacao", organization.name(), "slug", slug,
          "jornadas", journeys, "incidentes", incidents,
          "cores", Map.of("principal", colorOrEmpty(organization.primary()), "destaque", colorOrEmpty(organization.accent()))));
    } catch (DataAccessException e) {
      return response(Map.of("disponivel", false));
    }
  }

  private Map<String, Object> tenantJourney(String id, String name, Instant start, Instant now, boolean required) {
    var checks = checks(id, start);
    Instant first = firstMonitoringStart(id, checks);
    if (!required && first == null) return null;
    Check latest = latestCheck(id);
    return Map.of("nome", name, "estado", currentState(id, latest, now),
        "ultima_verificacao", latest == null ? "" : latest.at().toString(), "dias", history(checks, first, now));
  }

  private List<Check> checks(String journey, Instant start) {
    return jdbc.query("SELECT max(checked_at), bool_and(successful) FROM guardiao.service_checks "
            + "WHERE journey = ? AND checked_at >= ? "
            + "GROUP BY date_bin(interval '15 minutes', checked_at, timestamptz '2000-01-01') "
            + "ORDER BY max(checked_at) DESC",
        (rs, row) -> new Check(rs.getTimestamp(1).toInstant(), rs.getBoolean(2)), journey,
        java.sql.Timestamp.from(start));
  }

  private Check latestCheck(String journey) {
    var checks = jdbc.query("SELECT checked_at, successful FROM guardiao.service_checks "
            + "WHERE journey = ? ORDER BY checked_at DESC LIMIT 1",
        (rs, row) -> new Check(rs.getTimestamp(1).toInstant(), rs.getBoolean(2)), journey);
    return checks.isEmpty() ? null : checks.getFirst();
  }

  private static String colorOrEmpty(String value) { return value == null ? "" : value; }

  private static String journeyName(String id) {
    if (id.startsWith("organizacao:")) return NAMES.get("organizacao");
    if (id.startsWith("sondagem:")) {
      int separator = id.lastIndexOf(':');
      String key = id.substring(separator + 1);
      return TenantProbeResults.JOURNEYS.stream().filter(journey -> journey.key().equals(key))
          .map(TenantProbeResults.Journey::name).findFirst().orElse("Jornada institucional");
    }
    return NAMES.getOrDefault(id, "Serviço");
  }

  private record Organization(java.util.UUID id, String name, String primary, String accent) {}

  private ResponseEntity<Map<String, Object>> response(Map<String, Object> body) {
    return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(body);
  }

  private String tenantHealth(Instant now) {
    var latest = jdbc.query("SELECT c.checked_at, c.successful FROM guardiao.monitored_tenants t "
            + "LEFT JOIN LATERAL (SELECT checked_at, successful FROM guardiao.service_checks "
            + "WHERE journey = 'organizacao:' || t.organization_id::text ORDER BY checked_at DESC LIMIT 1) c ON true "
            + "WHERE t.synced_at >= now() - interval '10 minutes'",
        (rs, row) -> new Check(rs.getTimestamp(1) == null ? null : rs.getTimestamp(1).toInstant(), rs.getBoolean(2)));
    return currentTenantState(latest, now);
  }

  private String currentState(String journey, Check latest, Instant now) {
    if (journey.equals("organizacao")) return tenantHealth(now);
    if (latest == null || latest.at().isBefore(now.minusSeconds(1800))) return "sem_coleta";
    return latest.ok() ? "funcionando" : "falha";
  }

  static String currentTenantState(List<Check> latest, Instant now) {
    if (latest.stream().anyMatch(c -> c.at() != null && !c.at().isBefore(now.minusSeconds(1800)) && !c.ok())) return "falha";
    if (latest.isEmpty() || latest.stream().anyMatch(c -> c.at() == null || c.at().isBefore(now.minusSeconds(1800)))) return "sem_coleta";
    return "funcionando";
  }

  record Check(Instant at, boolean ok) {}
  Instant firstMonitoringStart(String journey, List<Check> checks) {
    java.sql.Timestamp startedAt = jdbc.queryForObject("SELECT min(started_at) FROM guardiao.service_journeys WHERE journey = ? "
        + "OR (? = 'organizacao' AND journey LIKE 'organizacao:%')", java.sql.Timestamp.class, journey, journey);
    if (startedAt != null) return startedAt.toInstant();
    return checks.isEmpty() ? null : checks.getLast().at();
  }

  static List<Map<String, Object>> history(List<Check> checks, Instant first, Instant now) {
    if (first == null) return List.of();
    LocalDate today = now.atZone(DISPLAY_ZONE).toLocalDate();
    LocalDate beginning = first.atZone(DISPLAY_ZONE).toLocalDate();
    if (beginning.isBefore(today.minusDays(29))) beginning = today.minusDays(29);
    var days = new ArrayList<Map<String, Object>>();
    for (LocalDate date = beginning; !date.isAfter(today); date = date.plusDays(1)) {
      days.add(historyDay(checks, first, now, date));
    }
    return days;
  }

  private static Map<String, Object> historyDay(List<Check> checks, Instant first, Instant now, LocalDate date) {
    Instant start = date.atStartOfDay(DISPLAY_ZONE).toInstant();
    Instant end = date.plusDays(1).atStartOfDay(DISPLAY_ZONE).toInstant();
    if (first.isAfter(start)) start = first;
    boolean currentDay = now.isBefore(end);
    if (currentDay) end = now;
    int expected = (int) ((Duration.between(start, end).getSeconds() + (currentDay ? 0 : -1)) / 900) + 1;
    var dayChecks = checks.stream().filter(c -> c.at().atZone(DISPLAY_ZONE).toLocalDate().equals(date)).toList();
    String state = dayChecks.isEmpty() ? "sem_coleta"
        : dayChecks.stream().anyMatch(c -> !c.ok()) ? "falha"
        : dayChecks.size() < expected ? "parcial" : "funcionando";
    return Map.of("data", date.toString(), "coletas", dayChecks.size(), "esperadas", expected, "estado", state);
  }
}
