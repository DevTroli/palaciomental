package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;

@EnabledIfEnvironmentVariable(named = "STATUS_TEST_DATABASE_URL", matches = ".+")
class ServiceMonitoringPostgresTest {
  @Test
  void recordsFailureAndRecoveryAcrossMonitorInstances() {
    var source = new DriverManagerDataSource(System.getenv("STATUS_TEST_DATABASE_URL"), "gc05", "gc05-temporary");
    var jdbc = new JdbcTemplate(source);
    var transactions = new TransactionTemplate(new DataSourceTransactionManager(source));
    var environment = mock(Environment.class);
    when(environment.acceptsProfiles(org.mockito.ArgumentMatchers.any(Profiles.class))).thenReturn(true);
    var monitor = new ServiceMonitoring(jdbc, transactions, environment, true, "", "");
    jdbc.update("DELETE FROM guardiao.service_incidents WHERE journey = 'inicio'");
    jdbc.update("DELETE FROM guardiao.service_checks WHERE journey = 'inicio'");

    transactions.executeWithoutResult(s -> monitor.record("inicio", false));
    ageLastCheck(jdbc);
    transactions.executeWithoutResult(s -> monitor.record("inicio", false));
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.service_incidents WHERE journey = 'inicio' AND recovered_at IS NULL", Integer.class)).isEqualTo(1);

    ageLastCheck(jdbc);
    transactions.executeWithoutResult(s -> monitor.record("inicio", true));
    ageLastCheck(jdbc);
    var restarted = new ServiceMonitoring(jdbc, transactions, environment, true, "", "");
    transactions.executeWithoutResult(s -> restarted.record("inicio", true));
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.service_incidents WHERE journey = 'inicio' AND recovered_at IS NOT NULL", Integer.class)).isEqualTo(1);
    assertThat(jdbc.queryForObject("SELECT count(*) FROM guardiao.service_checks WHERE journey = 'inicio'", Integer.class)).isEqualTo(4);
  }

  private static void ageLastCheck(JdbcTemplate jdbc) {
    jdbc.update("UPDATE guardiao.service_checks SET checked_at = checked_at - interval '5 minutes' WHERE journey = 'inicio'");
  }
}
