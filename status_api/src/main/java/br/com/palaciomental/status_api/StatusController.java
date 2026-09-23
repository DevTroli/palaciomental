package br.com.palaciomental.status_api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;

@Tag(name = "Health Check", description = "Endpoints de verificação de saúde do sistema")
@RestController
@RequestMapping("/v1")
public class StatusController {

  private final JdbcTemplate jdbcTemplate;
  private final RestTemplate restTemplate = new RestTemplate();

  @Value("${django.app.url}")
  private String djangoAppUrl;

  public StatusController(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Operation(
      summary = "Readiness probe",
      description = "Verifica saúde do banco de dados e da aplicação Django")
  @GetMapping("/status")
  public Map<String, Object> getStatus() {
    Map<String, Object> database = checkDatabase();
    Map<String, Object> django = checkDjango();

    boolean allOk =
        "operacional".equals(database.get("status")) && "operacional".equals(django.get("status"));

    return Map.of(
        "service",
        "palacio-mental-status",
        "checked_at",
        Instant.now().toString(),
        "status",
        allOk ? "operacional" : "degradado",
        "deployment",
        deploymentInfo(),
        "dependencies",
        Map.of("database", database, "django_app", django));
  }

  private Map<String, String> deploymentInfo() {
    Map<String, String> info = new LinkedHashMap<>();
    putIfPresent(info, "commit", System.getenv("RAILWAY_GIT_COMMIT_SHA"));
    putIfPresent(info, "author", System.getenv("RAILWAY_GIT_AUTHOR"));
    putIfPresent(info, "branch", System.getenv("RAILWAY_GIT_BRANCH"));
    putIfPresent(info, "service", System.getenv("RAILWAY_SERVICE_NAME"));
    putIfPresent(info, "environment", System.getenv("RAILWAY_ENVIRONMENT_NAME"));
    return info;
  }

  private void putIfPresent(Map<String, String> info, String key, String value) {
    if (value != null && !value.isBlank()) {
      info.put(key, value);
    }
  }

  private Map<String, Object> checkDatabase() {
    long start = System.currentTimeMillis();
    try {
      Map<String, Object> row =
          jdbcTemplate.queryForMap(
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
      var response = restTemplate.getForEntity(djangoAppUrl + "/saude", Map.class);
      Map<String, Object> result = new LinkedHashMap<>();
      result.put("status", response.getStatusCode().is2xxSuccessful() ? "operacional" : "degradado");
      result.put("response_time_ms", System.currentTimeMillis() - start);
      if (response.getBody() != null && response.getBody().get("deployment") instanceof Map<?, ?> deployment) {
        result.put("deployment", deployment);
      }
      return result;
    } catch (Exception e) {
      return Map.of(
          "status", "indisponivel", "response_time_ms", System.currentTimeMillis() - start);
    }
  }

  @Operation(summary = "Liveness probe", description = "Verifica se a aplicação está rodando")
  @GetMapping("/ping")
  public String ping() {
    return "pong";
  }
}
