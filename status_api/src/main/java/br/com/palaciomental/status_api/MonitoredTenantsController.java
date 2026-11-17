package br.com.palaciomental.status_api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import java.util.HashSet;
import java.util.List;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@SecurityRequirement(name = "serviceToken")
public class MonitoredTenantsController {
  private final JdbcTemplate jdbc;
  private final TransactionTemplate transactions;

  public MonitoredTenantsController(JdbcTemplate jdbc, TransactionTemplate transactions) {
    this.jdbc = jdbc;
    this.transactions = transactions;
  }

  public record Tenant(UUID organizationId, String hostname) {}
  public record Snapshot(List<Tenant> tenants) {}

  @PutMapping("/v1/guardiao/tenants")
  @Operation(summary = "Sincronizar organizações monitoradas", description = "Substitui a lista pelos domínios verificados das organizações ativas informados pelo Django.")
  public ResponseEntity<Void> synchronize(@RequestBody Snapshot snapshot) {
    if (snapshot == null || snapshot.tenants() == null || snapshot.tenants().size() > 1000) {
      return ResponseEntity.badRequest().build();
    }
    var ids = new HashSet<UUID>();
    var hosts = new HashSet<String>();
    for (Tenant tenant : snapshot.tenants()) {
      if (tenant == null || tenant.organizationId() == null || tenant.hostname() == null
          || tenant.hostname().length() > 253
          || !tenant.hostname().matches("[a-z0-9-]+(?:\\.[a-z0-9-]+)+")
          || !ids.add(tenant.organizationId()) || !hosts.add(tenant.hostname())) {
        return ResponseEntity.badRequest().build();
      }
    }
    transactions.executeWithoutResult(status -> {
      jdbc.execute("LOCK TABLE guardiao.monitored_tenants IN EXCLUSIVE MODE");
      jdbc.update("DELETE FROM guardiao.monitored_tenants");
      for (Tenant tenant : snapshot.tenants()) {
        jdbc.update("INSERT INTO guardiao.monitored_tenants(organization_id, hostname) VALUES (?, ?)",
            tenant.organizationId(), tenant.hostname());
      }
    });
    return ResponseEntity.noContent().build();
  }
}
