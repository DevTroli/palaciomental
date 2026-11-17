package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import java.net.URI;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;

class MonitoredTenantsControllerTest {
  @Test
  void rejectsDuplicateOrganizationsWithoutChangingStoredTargets() {
    var jdbc = mock(JdbcTemplate.class);
    var transactions = mock(TransactionTemplate.class);
    var controller = new MonitoredTenantsController(jdbc, transactions);
    UUID id = UUID.randomUUID();
    var result = controller.synchronize(new MonitoredTenantsController.Snapshot(List.of(
        new MonitoredTenantsController.Tenant(id, "one.example.org"),
        new MonitoredTenantsController.Tenant(id, "two.example.org"))));
    assertThat(result.getStatusCode().value()).isEqualTo(400);
    verifyNoInteractions(jdbc, transactions);
  }

  @Test
  void neverProbesLoopbackAddresses() {
    assertThat(TenantLoginProbe.check(URI.create("https://127.0.0.1/entrar/"), "marker")).isFalse();
    assertThat(TenantLoginProbe.check(URI.create("https://[::1]/entrar/"), "marker")).isFalse();
  }
}
