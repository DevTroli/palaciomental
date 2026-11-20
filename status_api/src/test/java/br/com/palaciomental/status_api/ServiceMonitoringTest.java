package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class ServiceMonitoringTest {
  @Test
  void requiresTwoMatchingRecentChecksForIncidentOrRecovery() {
    Instant now = Instant.parse("2026-01-01T12:00:00Z");
    assertThat(ServiceMonitoring.consecutive(false, now.minusSeconds(300), false, now)).isTrue();
    assertThat(ServiceMonitoring.consecutive(true, now.minusSeconds(300), true, now)).isTrue();
    assertThat(ServiceMonitoring.consecutive(false, now.minusSeconds(300), true, now)).isFalse();
    assertThat(ServiceMonitoring.consecutive(false, now.minusSeconds(1801), false, now)).isFalse();
  }
}
