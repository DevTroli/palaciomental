package br.com.palaciomental.status_api;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;

/** Deve ser chamado na mesma transação da alteração do incidente. */
final class IncidentAlertEvents {
  private IncidentAlertEvents() {}

  static void enqueue(JdbcTemplate jdbc, long incidentId, String type, Instant now) {
    List<Long> created = jdbc.query(
        "INSERT INTO guardiao.incident_alert_events (incident_id, event_type, created_at) VALUES (?, ?, ?) "
            + "ON CONFLICT (incident_id, event_type) DO NOTHING RETURNING id",
        (rs, row) -> rs.getLong(1), incidentId, type, Timestamp.from(now));
    if (created.isEmpty()) return;
    if (type.equals("public")) return;
    for (String channel : type.equals("severe") ? List.of("inbox") : type.equals("extended") ? List.of("discord", "email") : List.of("discord")) {
      if (channel.equals("email")) {
        enqueueEmailFallback(jdbc, created.getFirst(), now);
        continue;
      }
      jdbc.update("INSERT INTO guardiao.incident_alert_deliveries (event_id, channel, next_attempt_at) VALUES (?, ?, ?)",
          created.getFirst(), channel, Timestamp.from(now));
    }
  }

  static void enqueueEmailFallback(JdbcTemplate jdbc, long eventId, Instant now) {
    Long incidentId = jdbc.queryForObject("SELECT incident_id FROM guardiao.incident_alert_events WHERE id = ?", Long.class, eventId);
    jdbc.queryForObject("SELECT pg_advisory_xact_lock(hashtext(?)) IS NULL", Boolean.class, "alert-email:" + incidentId);
    jdbc.update("INSERT INTO guardiao.incident_alert_deliveries (event_id, channel, next_attempt_at) "
        + "SELECT current_event.id, 'email', ? FROM guardiao.incident_alert_events current_event "
        + "WHERE current_event.id = ? AND (current_event.event_type = 'recovered' OR NOT EXISTS ("
        + "SELECT 1 FROM guardiao.incident_alert_deliveries other_delivery "
        + "JOIN guardiao.incident_alert_events other_event ON other_event.id = other_delivery.event_id "
        + "WHERE other_event.incident_id = current_event.incident_id AND other_event.event_type IN ('opened', 'extended') "
        + "AND other_delivery.channel = 'email' AND other_delivery.status IN ('pending', 'sent'))) "
        + "ON CONFLICT (event_id, channel) DO NOTHING", Timestamp.from(now), eventId);
  }
}
