package br.com.palaciomental.status_api;

import java.net.URI;
import java.net.HttpURLConnection;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

@Component
public class ServiceMonitoring {
  private record Journey(String id, String url, String marker) {}
  private final JdbcTemplate jdbc;
  private final TransactionTemplate transactions;
  private final boolean enabled;
  private final List<Journey> journeys;

  public ServiceMonitoring(JdbcTemplate jdbc, TransactionTemplate transactions, Environment environment,
      @Value("${monitor.enabled:false}") boolean enabled,
      @Value("${monitor.global-url:}") String global,
      @Value("${monitor.tenant-login-url:}") String tenant) {
    this.jdbc = jdbc;
    this.transactions = transactions;
    this.enabled = enabled && environment.acceptsProfiles(Profiles.of("production | prod"));
    String base = global.replaceAll("/+$", "");
    journeys = List.of(new Journey("inicio", base, "data-status-probe=\"inicio\""),
        new Journey("vitrine", base + "/projetos/", "data-status-probe=\"vitrine\""),
        new Journey("entrada", base + "/entrar/", "data-status-probe=\"entrada\""),
        new Journey("cadastro", base + "/cadastrar/", "data-status-probe=\"cadastro\""),
        new Journey("organizacao", tenant, "data-status-probe=\"organizacao\""));
  }

  @Scheduled(fixedRateString = "${monitor.interval-ms:300000}", initialDelay = 30000)
  public void collect() {
    if (!enabled) return;
    for (Journey journey : journeys) {
      if (!valid(journey.url())) continue;
      boolean success = probe(journey);
      transactions.executeWithoutResult(status -> record(journey.id(), success));
    }
  }

  private boolean valid(String address) {
    try {
      URI uri = URI.create(address);
      return "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost() != null
          && uri.getUserInfo() == null && uri.getFragment() == null;
    } catch (IllegalArgumentException e) { return false; }
  }

  private boolean probe(Journey journey) {
    HttpURLConnection connection = null;
    try {
      connection = (HttpURLConnection) URI.create(journey.url()).toURL().openConnection();
      connection.setConnectTimeout(4000);
      connection.setReadTimeout(8000);
      connection.setInstanceFollowRedirects(false);
      if (connection.getResponseCode() != 200) return false;
      try (var body = connection.getInputStream()) {
        return new String(body.readNBytes(262144), java.nio.charset.StandardCharsets.UTF_8).contains(journey.marker());
      }
    } catch (Exception e) { return false; }
    finally { if (connection != null) connection.disconnect(); }
  }

  void record(String journey, boolean successful) {
    // O lock impede que réplicas registrem duas verificações para o mesmo ciclo.
    jdbc.queryForObject("SELECT pg_advisory_xact_lock(hashtext(?)) IS NULL", Boolean.class, "status:" + journey);
    var previous = jdbc.query("SELECT successful, checked_at FROM guardiao.service_checks WHERE journey = ? ORDER BY checked_at DESC LIMIT 1",
        (rs, row) -> new Previous(rs.getBoolean(1), rs.getTimestamp(2).toInstant()), journey);
    Instant now = Instant.now();
    if (!previous.isEmpty() && previous.getFirst().at().isAfter(now.minusSeconds(240))) return;
    jdbc.update("INSERT INTO guardiao.service_checks (journey, checked_at, successful) VALUES (?, ?, ?)", journey, java.sql.Timestamp.from(now), successful);
    if (!previous.isEmpty() && consecutive(previous.getFirst().successful(), previous.getFirst().at(), successful, now)) {
      if (!successful) {
        jdbc.update("INSERT INTO guardiao.service_incidents (journey, started_at) VALUES (?, ?) ON CONFLICT (journey) WHERE recovered_at IS NULL DO NOTHING",
            journey, java.sql.Timestamp.from(previous.getFirst().at()));
      } else {
        jdbc.update("UPDATE guardiao.service_incidents SET recovered_at = ? WHERE journey = ? AND recovered_at IS NULL",
            java.sql.Timestamp.from(now), journey);
      }
    }
    jdbc.update("DELETE FROM guardiao.service_checks WHERE checked_at < ?", java.sql.Timestamp.from(now.minus(Duration.ofDays(31))));
  }

  private record Previous(boolean successful, Instant at) {}

  static boolean consecutive(boolean previous, Instant previousAt, boolean current, Instant now) {
    return previous == current && previousAt.isAfter(now.minusSeconds(600));
  }

  boolean enabled() { return enabled; }
}
