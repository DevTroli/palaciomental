package br.com.palaciomental.status_api;

import java.time.Instant;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;

@RestController
@RequestMapping("/v1")
public class StatusController {

  private final JdbcTemplate jdbcTemplate;
  private final RestTemplate restTemplate = new RestTemplate();

  public StatusController(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @GetMapping("/status")
  public Map<String, Object> getStatus() {
    Map<String, Object> database = checkDatabase();
    Map<String, Object> django = checkDjango();

    boolean allOk = "operacional".equals(database.get("status")) && "operacional".equals(django.get("status"));

    return Map.of(
        "service",
        "palacio-mental-status",
        "checked_at",
        Instant.now().toString(),
        "status",
        allOk ? "operacional" : "degradado",
        "dependencies",
        Map.of("database", database, "django_app", django));
  }

  private Map<String, Object> checkDatabase() {
    long start = System.currentTimeMillis();
    try {
      Map<String, Object> row = jdbcTemplate.queryForMap(
          """
                  SELECT version() AS version,
                         (SELECT setting FROM pg_settings WHERE name = 'max_connections') AS max_connections,
                         (SELECT count(*) FROM pg_stat_activity) AS used_connections
              """);
      return Map.of(
          "status",
          "operacional",
          "response_time_ms",
          System.currentTimeMillis() - start,
          "details",
          row);
    } catch (Exception e) {
      return Map.of(
          "status", "indisponivel", "response_time_ms", System.currentTimeMillis() - start);
    }
  }

  private Map<String, Object> checkDjango() {
    long start = System.currentTimeMillis();
    try {
      var response = restTemplate.getForEntity("http://django:8000/saude", String.class);
      return Map.of(
          "status",
          response.getStatusCode().is2xxSuccessful() ? "operacional" : "degradado",
          "response_time_ms",
          System.currentTimeMillis() - start);
    } catch (Exception e) {
      return Map.of(
          "status", "indisponivel", "response_time_ms", System.currentTimeMillis() - start);
    }
  }
}
