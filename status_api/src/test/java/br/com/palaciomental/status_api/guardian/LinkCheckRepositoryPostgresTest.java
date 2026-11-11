package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.sql.Connection;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;

@EnabledIfEnvironmentVariable(named = "GUARDIAO_TEST_JDBC_URL", matches = ".+")
class LinkCheckRepositoryPostgresTest {
  private SingleConnectionDataSource source;
  private Connection connection;
  private JdbcTemplate jdbc;
  private LinkCheckRepository repository;

  @BeforeEach
  void setup() throws Exception {
    String url = System.getenv("GUARDIAO_TEST_JDBC_URL");
    if (!url.matches("jdbc:postgresql://(127\\.0\\.0\\.1|localhost):[0-9]+/guardiao_test")) {
      throw new IllegalStateException("Use apenas o banco local descartável guardiao_test");
    }
    source = new SingleConnectionDataSource(url, System.getenv("GUARDIAO_TEST_USER"),
        System.getenv("GUARDIAO_TEST_PASSWORD"), true);
    connection = source.getConnection();
    connection.setAutoCommit(false);
    jdbc = new JdbcTemplate(source);
    repository = new LinkCheckRepository(jdbc);
  }

  @AfterEach
  void cleanup() throws Exception {
    if (connection != null) connection.rollback();
    if (source != null) source.destroy();
  }

  @Test
  void lotePreservaEstadoERejeitaCicloDuplicadoOuUrlAntiga() {
    var original = new LinkBatch(List.of(new LinkBatch.Link(123456789, URI.create("https://example.com/a"))));
    repository.enqueue(original);
    Instant now = Instant.parse("2026-01-01T00:00:00Z");
    UUID cycle = UUID.randomUUID();
    assertThat(repository.completeCycle(123456789, 1, cycle, LinkStatus.SEM_RESPOSTA, now, now.plus(Duration.ofHours(48)))).isTrue();
    assertThat(repository.completeCycle(123456789, 1, cycle, LinkStatus.SEM_RESPOSTA, now, now.plus(Duration.ofHours(48)))).isFalse();
    repository.enqueue(original);
    assertThat(jdbc.queryForObject("SELECT failed_cycles FROM guardiao.link_check WHERE link_id = ?", Integer.class, 123456789)).isEqualTo(1);
    repository.enqueue(new LinkBatch(List.of(new LinkBatch.Link(123456789, URI.create("https://example.com/b")))));
    repository.enqueue(original);
    assertThat(jdbc.queryForObject("SELECT url_revision FROM guardiao.link_check WHERE link_id = ?", Long.class, 123456789)).isEqualTo(3L);
    assertThat(repository.completeCycle(123456789, 1, UUID.randomUUID(), LinkStatus.QUEBRADO, now, now.plus(Duration.ofHours(48)))).isFalse();
    assertThat(jdbc.queryForObject("SELECT status FROM guardiao.link_check WHERE link_id = ?", String.class, 123456789)).isNull();
  }

  @Test
  void concessaoExpiradaOuUrlAlteradaNaoAceitaResultado() {
    var original = new LinkBatch(List.of(new LinkBatch.Link(123456790, URI.create("https://example.com/a"))));
    repository.enqueue(original);
    Instant now = Instant.now().plusSeconds(1);
    var claim = repository.claimDue(UUID.randomUUID(), now, now.plusSeconds(30), 1).getFirst();
    assertThat(repository.completeClaim(claim, LinkStatus.QUEBRADO, now.plusSeconds(31), now.plusSeconds(60))).isFalse();
    repository.enqueue(new LinkBatch(List.of(new LinkBatch.Link(123456790, URI.create("https://example.com/b")))));
    assertThat(repository.completeClaim(claim, LinkStatus.QUEBRADO, now.plusSeconds(2), now.plusSeconds(60))).isFalse();
    var replacement = repository.claimDue(UUID.randomUUID(), now.plusSeconds(3), now.plusSeconds(33), 1).getFirst();
    assertThat(repository.completeClaim(replacement, LinkStatus.ACESSIVEL, now.plusSeconds(4), now.plusSeconds(60))).isTrue();
    assertThat(repository.completeClaim(replacement, LinkStatus.ACESSIVEL, now.plusSeconds(5), now.plusSeconds(60))).isFalse();
  }

  @Test
  void sincronizacaoSoRemoveReferenciasAusentesAposConclusao() {
    repository.enqueue(new LinkBatch(List.of(
        new LinkBatch.Link(123456791, URI.create("https://example.com/a")),
        new LinkBatch.Link(123456792, URI.create("https://example.com/b")))));
    UUID snapshot = UUID.randomUUID();
    assertThat(repository.startSnapshot(snapshot)).isTrue();
    assertThat(repository.startSnapshot(UUID.randomUUID())).isFalse();
    assertThat(repository.lockSnapshot(snapshot)).isTrue();
    repository.enqueueSnapshot(new LinkBatch(List.of(
        new LinkBatch.Link(123456791, URI.create("https://example.com/a")))), snapshot);
    assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM guardiao.link_check WHERE link_id IN (?, ?)",
        Integer.class, 123456791, 123456792)).isEqualTo(2);
    repository.finishSnapshot(snapshot);
    assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM guardiao.link_check WHERE link_id IN (?, ?)",
        Integer.class, 123456791, 123456792)).isEqualTo(1);
  }

  @Test
  void limiteDeDominioEhCompartilhadoERecuperaConcessoesExpiradas() {
    UUID first = UUID.randomUUID();
    UUID second = UUID.randomUUID();
    assertThat(repository.acquireDomain("example.com", first, Instant.now().plusSeconds(30))).isTrue();
    assertThat(repository.acquireDomain("example.com", second, Instant.now().plusSeconds(30))).isFalse();
    repository.releaseDomain("example.com", second);
    assertThat(repository.acquireDomain("example.com", second, Instant.now().plusSeconds(30))).isFalse();
    repository.releaseDomain("example.com", first);
    assertThat(repository.acquireDomain("example.com", second, Instant.now().plusSeconds(30))).isTrue();
  }
}
