package br.com.palaciomental.status_api;

import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;

/** Envia cada canal separadamente; os erros registrados não incluem respostas ou credenciais. */
@Component
public class IncidentAlertDispatcher {
  private static final Logger LOG = LoggerFactory.getLogger(IncidentAlertDispatcher.class);
  private static final JsonMapper JSON = new JsonMapper();
  private static final Map<String, String> JOURNEYS = Map.of(
      "inicio", "Página inicial", "vitrine", "Vitrine de projetos", "entrada", "Entrada",
      "cadastro", "Cadastro", "organizacao", "Entrada da organização");
  private final JdbcTemplate jdbc;
  private final TransactionTemplate transactions;
  private final ServiceMonitoring monitoring;
  private final String discordUrl;
  private final String resendKey;
  private final String emailFrom;
  private final String emailTo;

  public IncidentAlertDispatcher(JdbcTemplate jdbc, TransactionTemplate transactions, ServiceMonitoring monitoring,
      @Value("${alerts.discord-webhook:}") String discordUrl,
      @Value("${alerts.resend-key:}") String resendKey,
      @Value("${alerts.email-from:}") String emailFrom,
      @Value("${alerts.email-to:}") String emailTo) {
    this.jdbc = jdbc;
    this.transactions = transactions;
    this.monitoring = monitoring;
    this.discordUrl = discordUrl.trim();
    this.resendKey = resendKey.trim();
    this.emailFrom = emailFrom.trim();
    this.emailTo = emailTo.trim();
  }

  @Scheduled(fixedDelayString = "${alerts.poll-delay-ms:30000}")
  public void dispatch() {
    if (!monitoring.enabled()) return;
    try {
      jdbc.update("UPDATE guardiao.incident_alert_deliveries d SET status = 'expired' FROM guardiao.incident_alert_events e "
          + "WHERE d.event_id = e.id AND d.channel = 'inbox' AND d.status = 'pending' "
          + "AND e.created_at < now() - interval '24 hours'");
    } catch (RuntimeException ex) {
      LOG.warn("Não foi possível atualizar os avisos antigos.");
    }
    boolean emailConfigured = !resendKey.isEmpty() && !emailFrom.isEmpty() && !emailTo.isEmpty();
    if (validDiscord(discordUrl) || emailConfigured) process("discord");
    if (emailConfigured) process("email");
  }

  void process(String channel) {
    try {
      transactions.executeWithoutResult(status -> {
        var pending = jdbc.query("SELECT d.event_id, d.attempts, e.event_type, e.created_at, i.journey "
                + "FROM guardiao.incident_alert_deliveries d JOIN guardiao.incident_alert_events e ON e.id = d.event_id "
                + "JOIN guardiao.service_incidents i ON i.id = e.incident_id "
                + "WHERE d.channel = ? AND d.status = 'pending' AND d.next_attempt_at <= now() "
                + "ORDER BY d.next_attempt_at, d.event_id FOR UPDATE OF d SKIP LOCKED LIMIT 1",
            (rs, row) -> new Delivery(rs.getLong(1), rs.getInt(2), rs.getString(3),
                rs.getTimestamp(4).toInstant(), rs.getString(5)), channel);
        if (pending.isEmpty()) return;
        Delivery delivery = pending.getFirst();
        Outcome result = send(channel, delivery);
        int attempts = delivery.attempts() + 1;
        String nextStatus = result == Outcome.SENT ? "sent"
            : result == Outcome.RETRY && attempts < 3 ? "pending" : "failed";
        jdbc.update("UPDATE guardiao.incident_alert_deliveries SET status = ?, attempts = ?, "
                + "next_attempt_at = now() + (? * interval '1 minute'), last_error = ?, "
                + "sent_at = CASE WHEN ? = 'sent' THEN now() ELSE NULL END WHERE event_id = ? AND channel = ?",
            nextStatus, attempts, attempts == 1 ? 1 : 5, result == Outcome.SENT ? null : result.name(),
            nextStatus, delivery.eventId(), channel);
        if (channel.equals("discord") && nextStatus.equals("failed")) {
          IncidentAlertEvents.enqueueEmailFallback(jdbc, delivery.eventId(), Instant.now());
        }
      });
    } catch (RuntimeException ex) {
      LOG.warn("Não foi possível processar o canal de alerta {}.", channel);
    }
  }

  Outcome send(String channel, Delivery delivery) {
    String state = incidentState(delivery);
    String message = incidentMessage(delivery, state);
    return deliver(channel, delivery, state, message);
  }

  private String incidentState(Delivery delivery) {
    return delivery.type().equals("recovered") ? "Recuperado"
        : delivery.type().equals("extended") ? "Incidente prolongado" : "Incidente aberto";
  }

  private String incidentMessage(Delivery delivery, String state) {
    String journeyId = delivery.journey().startsWith("organizacao:") ? "organizacao" : delivery.journey();
    String journey = JOURNEYS.getOrDefault(journeyId, "Serviço");
    String route = switch (journeyId) {
      case "inicio" -> "/";
      case "vitrine" -> "/projetos/";
      case "entrada" -> "/entrar/";
      case "cadastro" -> "/cadastrar/";
      default -> "entrada institucional monitorada";
    };
    return "Palácio Mental · " + state + "\nJornada: " + journey
        + "\nCategoria: disponibilidade\nPrioridade: " + (delivery.type().equals("recovered") ? "informativa" : "alta")
        + "\nHorário: " + delivery.createdAt() + "\nReprodução: acesse " + route
        + "\nConsulte a página pública de status para acompanhar o acesso.";
  }

  private Outcome deliver(String channel, Delivery delivery, String state, String message) {
    try {
      if (channel.equals("discord") && !validDiscord(discordUrl)) return Outcome.REJECTED;
      Map<String, Object> body = channel.equals("discord")
          ? Map.of("content", message, "allowed_mentions", Map.of("parse", List.of()))
          : Map.of("from", emailFrom, "to", List.of(emailTo), "subject", "Palácio Mental: " + state, "text", message);
      URI target = URI.create(channel.equals("discord") ? discordUrl : "https://api.resend.com/emails");
      HttpURLConnection connection = openConnection(target);
      try {
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(5000);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json");
        if (channel.equals("email")) {
          connection.setRequestProperty("Authorization", "Bearer " + resendKey);
          connection.setRequestProperty("Idempotency-Key", "pm-incident/" + delivery.eventId());
        }
        byte[] payload = JSON.writeValueAsString(body).getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(payload.length);
        try (var out = connection.getOutputStream()) { out.write(payload); }
        int status = connection.getResponseCode();
        if (status >= 200 && status < 300) return Outcome.SENT;
        return status == 429 || status >= 500 ? Outcome.RETRY : Outcome.REJECTED;
      } finally { connection.disconnect(); }
    } catch (Exception ex) {
      // Uma falha sem resposta no Discord pode ter ocorrido após a entrega.
      return channel.equals("email") ? Outcome.RETRY : Outcome.UNKNOWN;
    }
  }

  HttpURLConnection openConnection(URI target) throws java.io.IOException {
    return (HttpURLConnection) target.toURL().openConnection();
  }

  static boolean validDiscord(String value) {
    try {
      URI uri = URI.create(value);
      return "https".equalsIgnoreCase(uri.getScheme()) && "discord.com".equalsIgnoreCase(uri.getHost())
          && uri.getPort() == -1 && uri.getUserInfo() == null && uri.getQuery() == null && uri.getFragment() == null
          && uri.getRawPath().matches("/api/webhooks/[0-9]+/[A-Za-z0-9._-]+");
    } catch (IllegalArgumentException ex) { return false; }
  }

  enum Outcome { SENT, RETRY, REJECTED, UNKNOWN }
  record Delivery(long eventId, int attempts, String type, Instant createdAt, String journey) {}
}
