package br.com.palaciomental.status_api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.time.Instant;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Tag(name = "Alertas", description = "Entregue avisos graves à caixa de entrada.")
@SecurityRequirement(name = "serviceToken")
public class IncidentInboxController {
  private final JdbcTemplate jdbc;
  private final ServiceMonitoring monitoring;

  public IncidentInboxController(JdbcTemplate jdbc, ServiceMonitoring monitoring) {
    this.jdbc = jdbc;
    this.monitoring = monitoring;
  }

  public record Alert(long id, String journey, String tenantHost, Instant startedAt, Instant recoveredAt, Instant createdAt) {}

  @GetMapping("/v1/guardiao/alertas/inbox")
  @Operation(summary = "Consultar avisos pendentes", description = "Retorna até 20 incidentes graves com menos de 24 horas. O Django seleciona os destinatários autorizados.")
  public List<Alert> pending() {
    if (!monitoring.enabled()) return List.of();
    return jdbc.query("SELECT e.id, i.journey, i.tenant_host, i.started_at, i.recovered_at, e.created_at "
            + "FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id "
            + "JOIN guardiao.service_incidents i ON i.id = e.incident_id "
            + "WHERE d.channel = 'inbox' AND d.status = 'pending' AND e.event_type = 'severe' "
            + "AND d.next_attempt_at <= now() AND e.created_at >= now() - interval '24 hours' ORDER BY e.id LIMIT 20",
        (rs, row) -> new Alert(rs.getLong(1), institutional(rs.getString(2)) ? "organizacao" : rs.getString(2), rs.getString(3), rs.getTimestamp(4).toInstant(),
            rs.getTimestamp(5) == null ? null : rs.getTimestamp(5).toInstant(), rs.getTimestamp(6).toInstant()));
  }

  @PostMapping("/v1/guardiao/alertas/inbox/{eventId}/confirmar")
  @Operation(summary = "Confirmar aviso entregue", description = "Remove o aviso da fila após a gravação na caixa de entrada. A confirmação pode ser repetida.")
  public ResponseEntity<Void> confirm(@PathVariable("eventId") long eventId) {
    if (eventId <= 0) return ResponseEntity.badRequest().build();
    if (!monitoring.enabled()) return ResponseEntity.status(503).build();
    jdbc.update("UPDATE guardiao.incident_alert_deliveries SET status = 'sent', sent_at = now() "
        + "WHERE event_id = ? AND channel = 'inbox' AND status = 'pending'", eventId);
    return ResponseEntity.noContent().build();
  }

  @PostMapping("/v1/guardiao/alertas/inbox/{eventId}/rejeitar")
  @Operation(summary = "Registrar organização não identificada", description = "Retira da fila um aviso institucional sem organização ativa correspondente.")
  public ResponseEntity<Void> reject(@PathVariable("eventId") long eventId) {
    if (eventId <= 0) return ResponseEntity.badRequest().build();
    if (!monitoring.enabled()) return ResponseEntity.status(503).build();
    jdbc.update("UPDATE guardiao.incident_alert_deliveries d SET status = 'failed', last_error = 'TENANT_NOT_FOUND' "
        + "FROM guardiao.incident_alert_events e JOIN guardiao.service_incidents i ON i.id = e.incident_id "
        + "WHERE d.event_id = e.id AND d.event_id = ? AND d.channel = 'inbox' "
        + "AND d.status = 'pending' AND (i.journey = 'organizacao' OR i.journey LIKE 'organizacao:%' OR i.journey LIKE 'sondagem:%')", eventId);
    return ResponseEntity.noContent().build();
  }

  @PostMapping("/v1/guardiao/alertas/inbox/{eventId}/falha")
  @Operation(summary = "Registrar falha de entrega", description = "Registra uma tentativa sem dados sensíveis e agenda até três tentativas.")
  public ResponseEntity<Void> failure(@PathVariable("eventId") long eventId) {
    if (eventId <= 0) return ResponseEntity.badRequest().build();
    if (!monitoring.enabled()) return ResponseEntity.status(503).build();
    jdbc.update("UPDATE guardiao.incident_alert_deliveries SET attempts = attempts + 1, "
        + "status = CASE WHEN attempts + 1 >= 3 THEN 'failed' ELSE 'pending' END, "
        + "next_attempt_at = now() + (CASE WHEN attempts = 0 THEN 1 ELSE 5 END * interval '1 minute'), "
        + "last_error = 'INBOX_DELIVERY_FAILED' WHERE event_id = ? AND channel = 'inbox' "
        + "AND status = 'pending' AND next_attempt_at <= now()", eventId);
    return ResponseEntity.noContent().build();
  }

  private static boolean institutional(String journey) {
    return journey.startsWith("organizacao:") || journey.startsWith("sondagem:");
  }
}
