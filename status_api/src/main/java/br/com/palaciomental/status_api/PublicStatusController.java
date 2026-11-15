package br.com.palaciomental.status_api;

import io.swagger.v3.oas.annotations.Hidden;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@Hidden
@RestController
public class PublicStatusController {
  private static final Map<String, String> NAMES = Map.of(
      "inicio", "Página inicial", "vitrine", "Vitrine de projetos", "entrada", "Entrada", "cadastro", "Cadastro", "organizacao", "Entrada da organização");
  private final JdbcTemplate jdbc;
  private final ServiceMonitoring monitor;

  public PublicStatusController(JdbcTemplate jdbc, ServiceMonitoring monitor) {
    this.jdbc = jdbc;
    this.monitor = monitor;
  }

  @GetMapping("/v1/status-publico")
  public ResponseEntity<Map<String, Object>> status() {
    if (!monitor.enabled()) return response(Map.of("disponivel", false));
    try {
      Instant now = Instant.now();
      LocalDate today = LocalDate.now(ZoneOffset.UTC);
      var start = today.minusDays(29).atStartOfDay().toInstant(ZoneOffset.UTC);
      var journeys = new ArrayList<Map<String, Object>>();
      for (String id : List.of("inicio", "vitrine", "entrada", "cadastro", "organizacao")) {
        var checks = jdbc.query("SELECT checked_at, successful FROM guardiao.service_checks WHERE journey = ? AND checked_at >= ? ORDER BY checked_at DESC",
            (rs, row) -> new Check(rs.getTimestamp(1).toInstant(), rs.getBoolean(2)), id, java.sql.Timestamp.from(start));
        var days = new ArrayList<Map<String, Object>>();
        for (int offset = 29; offset >= 0; offset--) {
          LocalDate date = today.minusDays(offset);
          var dayChecks = checks.stream().filter(c -> c.at().atZone(ZoneOffset.UTC).toLocalDate().equals(date)).toList();
          int expected = date.equals(today) ? (int) (DurationSeconds.sinceMidnight(now) / 300) + 1 : 288;
          String dayState = dayChecks.isEmpty() ? "sem_coleta"
              : dayChecks.stream().anyMatch(c -> !c.ok()) ? "falha"
              : dayChecks.size() < expected ? "parcial" : "funcionando";
          days.add(Map.of("data", date.toString(), "coletas", dayChecks.size(), "esperadas", expected, "estado", dayState));
        }
        Check latest = checks.isEmpty() ? null : checks.getFirst();
        String state = latest == null || latest.at().isBefore(now.minusSeconds(600)) ? "sem_coleta" : latest.ok() ? "funcionando" : "falha";
        journeys.add(Map.of("nome", NAMES.get(id), "estado", state, "ultima_verificacao", latest == null ? "" : latest.at().toString(), "dias", days));
      }
      var incidents = jdbc.query("SELECT journey, started_at, recovered_at FROM guardiao.service_incidents WHERE started_at >= ? OR recovered_at IS NULL OR recovered_at >= ? ORDER BY started_at DESC LIMIT 100",
          (rs, row) -> Map.of("jornada", NAMES.getOrDefault(rs.getString(1), "Serviço"), "inicio", rs.getTimestamp(2).toInstant().toString(),
              "fim", rs.getTimestamp(3) == null ? "" : rs.getTimestamp(3).toInstant().toString()), java.sql.Timestamp.from(start), java.sql.Timestamp.from(start));
      return response(Map.of("disponivel", true, "jornadas", journeys, "incidentes", incidents));
    } catch (DataAccessException e) {
      return response(Map.of("disponivel", false));
    }
  }

  private ResponseEntity<Map<String, Object>> response(Map<String, Object> body) {
    return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(body);
  }

  private record Check(Instant at, boolean ok) {}
  private static final class DurationSeconds {
    static long sinceMidnight(Instant now) { return now.getEpochSecond() % 86400; }
  }
}
