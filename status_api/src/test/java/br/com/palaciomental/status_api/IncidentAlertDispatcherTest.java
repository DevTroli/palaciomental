package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;

class IncidentAlertDispatcherTest {
  @Test
  void acceptsOnlyDiscordHttpsWebhookEndpoints() {
    assertThat(IncidentAlertDispatcher.validDiscord("https://discord.com/api/webhooks/123456/token_abc-123")).isTrue();
    assertThat(IncidentAlertDispatcher.validDiscord("http://discord.com/api/webhooks/123456/token")).isFalse();
    assertThat(IncidentAlertDispatcher.validDiscord("https://discord.com.evil.example/api/webhooks/123456/token")).isFalse();
    assertThat(IncidentAlertDispatcher.validDiscord("https://discord.com/api/webhooks/123456/token?redirect=x")).isFalse();
    assertThat(IncidentAlertDispatcher.validDiscord("https://discord.com/" )).isFalse();
  }

  @Test
  void discordSendsSafeContextAndClassifiesProviderResponses() throws Exception {
    var sender = spy(new IncidentAlertDispatcher(mock(JdbcTemplate.class), mock(TransactionTemplate.class),
        mock(ServiceMonitoring.class), "https://discord.com/api/webhooks/123456/test-token", "", "", ""));
    var connection = mock(HttpURLConnection.class);
    var output = new ByteArrayOutputStream();
    when(connection.getOutputStream()).thenReturn(output);
    when(connection.getResponseCode()).thenReturn(204, 429, 500, 403);
    doReturn(connection).when(sender).openConnection(any());
    var event = new IncidentAlertDispatcher.Delivery(42, 0, "opened", Instant.parse("2026-01-01T12:00:00Z"), "vitrine");

    assertThat(sender.send("discord", event)).isEqualTo(IncidentAlertDispatcher.Outcome.SENT);
    assertThat(output.toString(java.nio.charset.StandardCharsets.UTF_8))
        .contains("Vitrine de projetos", "/projetos/", "allowed_mentions")
        .doesNotContain("test-token");
    assertThat(sender.send("discord", event)).isEqualTo(IncidentAlertDispatcher.Outcome.RETRY);
    assertThat(sender.send("discord", event)).isEqualTo(IncidentAlertDispatcher.Outcome.RETRY);
    assertThat(sender.send("discord", event)).isEqualTo(IncidentAlertDispatcher.Outcome.REJECTED);
  }

  @Test
  void resendUsesStableIdempotencyKeyAndDiscordTimeoutDoesNotBlindlyRetry() throws Exception {
    var sender = spy(new IncidentAlertDispatcher(mock(JdbcTemplate.class), mock(TransactionTemplate.class),
        mock(ServiceMonitoring.class), "https://discord.com/api/webhooks/123456/test-token", "test-key", "from@example.com", "to@example.com"));
    var connection = mock(HttpURLConnection.class);
    when(connection.getOutputStream()).thenReturn(new ByteArrayOutputStream());
    when(connection.getResponseCode()).thenReturn(200).thenThrow(new IOException("provider secret"));
    doReturn(connection).when(sender).openConnection(any());
    var event = new IncidentAlertDispatcher.Delivery(42, 0, "opened", Instant.parse("2026-01-01T12:00:00Z"), "entrada");

    assertThat(sender.send("email", event)).isEqualTo(IncidentAlertDispatcher.Outcome.SENT);
    verify(connection).setRequestProperty("Idempotency-Key", "pm-incident/42");
    assertThat(sender.send("discord", event)).isEqualTo(IncidentAlertDispatcher.Outcome.UNKNOWN);
  }
}
