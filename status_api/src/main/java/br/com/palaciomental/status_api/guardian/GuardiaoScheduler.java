package br.com.palaciomental.status_api.guardian;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

/** Busca um único trabalho por vez; outras instâncias usam concessões independentes. */
@Configuration
@EnableScheduling
@ConditionalOnProperty(name = "guardiao.enabled", havingValue = "true")
public class GuardiaoScheduler implements AutoCloseable {
  private final LinkCheckRepository repository;
  private final BoundedDnsResolver resolver = new BoundedDnsResolver(Duration.ofSeconds(3));
  private final VerificationCycle cycle = new VerificationCycle(
      new HttpLinkProbe(new PublicDestinationPolicy(resolver))::check);

  public GuardiaoScheduler(JdbcTemplate jdbc) {
    repository = new LinkCheckRepository(jdbc);
  }

  @Scheduled(fixedDelayString = "${guardiao.poll-delay-ms:10000}")
  public void process() throws InterruptedException {
    Instant now = Instant.now();
    var claims = repository.claimDue(UUID.randomUUID(), now, now.plus(Duration.ofMinutes(2)), 1);
    if (claims.isEmpty()) {
      return;
    }
    var claim = claims.getFirst();
    String host = claim.url().getHost().toLowerCase(Locale.ROOT).replaceFirst("\\.$", "");
    if (!repository.acquireDomain(host, claim.leaseId(), now.plus(Duration.ofMinutes(2)))) {
      repository.releaseClaim(claim);
      return;
    }
    try {
      LinkStatus status;
      try {
        status = cycle.verify(claim.url()).status();
      } catch (IllegalArgumentException ex) {
        // Destinos proibidos ou redirecionamentos inválidos nunca são acessados.
        status = LinkStatus.SEM_RESPOSTA;
      }
      Instant checkedAt = Instant.now();
      long jitterSeconds = ThreadLocalRandom.current().nextLong(
          VerificationCyclePolicy.MAX_JITTER.toSeconds() + 1);
      repository.completeClaim(claim, status, checkedAt,
          VerificationCyclePolicy.nextCycleAt(checkedAt, Duration.ofSeconds(jitterSeconds)));
    } finally {
      repository.releaseDomain(host, claim.leaseId());
    }
  }

  @Override
  public void close() {
    resolver.close();
  }
}
