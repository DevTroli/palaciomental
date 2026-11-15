package br.com.palaciomental.status_api.guardian;

import java.sql.Timestamp;
import java.time.Instant;
import java.net.URI;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;

/** Persistência isolada no schema do Guardião; não acessa as tabelas Django. */
public final class LinkCheckRepository {
  private final JdbcTemplate jdbc;

  public LinkCheckRepository(JdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  /** Deve ser executado numa transação para que o lote seja atômico. */
  public void enqueue(LinkBatch batch) {
    List<LinkBatch.Link> links = batch.links();
    jdbc.batchUpdate("""
        INSERT INTO guardiao.link_check (link_id, url) VALUES (?, ?)
        ON CONFLICT (link_id) DO UPDATE SET
          url = EXCLUDED.url, status = NULL, checked_at = NULL, failed_cycles = 0,
          last_cycle_id = NULL, url_revision = guardiao.link_check.url_revision + 1,
          lease_id = NULL, lease_until = NULL,
          next_check_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE guardiao.link_check.url IS DISTINCT FROM EXCLUDED.url
        """, links, LinkBatch.MAX_LINKS, (statement, link) -> {
          statement.setLong(1, link.linkId());
          statement.setString(2, link.url().toASCIIString());
        });
  }

  public void delete(long linkId) {
    jdbc.update("DELETE FROM guardiao.link_check WHERE link_id = ?", linkId);
  }

  public List<LinkResult> results(List<Long> ids) {
    if (ids.isEmpty()) return List.of();
    String placeholders = String.join(",", java.util.Collections.nCopies(ids.size(), "?"));
    return jdbc.query("SELECT link_id, status, checked_at, failed_cycles FROM guardiao.link_check WHERE link_id IN ("
        + placeholders + ")", (row, n) -> new LinkResult(row.getLong(1), row.getString(2),
        row.getTimestamp(3) == null ? null : row.getTimestamp(3).toInstant(), row.getInt(4)), ids.toArray());
  }

  public record LinkResult(long link_id, String status, Instant checked_at, int failed_cycles) {}

  public record Claimed(long linkId, URI url, long revision, UUID leaseId) {
    @Override public String toString() { return "Claimed[linkId=" + linkId + ", url=<redacted>]"; }
  }

  /** Uma instrução atômica permite concorrência entre instâncias sem locks durante a rede. */
  public List<Claimed> claimDue(UUID leaseId, Instant now, Instant leaseUntil, int limit) {
    if (leaseId == null || now == null || leaseUntil == null || !leaseUntil.isAfter(now)
        || limit < 1 || limit > LinkBatch.MAX_LINKS) {
      throw new IllegalArgumentException("Concessão inválida");
    }
    return jdbc.query("""
        WITH due AS (
          SELECT link_id FROM guardiao.link_check
          WHERE next_check_at <= ? AND (lease_until IS NULL OR lease_until <= ?)
          ORDER BY next_check_at, link_id FOR UPDATE SKIP LOCKED LIMIT ?
        )
        UPDATE guardiao.link_check AS link SET lease_id = ?, lease_until = ?
        FROM due WHERE link.link_id = due.link_id
        RETURNING link.link_id, link.url, link.url_revision, link.lease_id
        """, (row, n) -> new Claimed(row.getLong(1), URI.create(row.getString(2)),
            row.getLong(3), row.getObject(4, UUID.class)), Timestamp.from(now),
        Timestamp.from(now), limit, leaseId, Timestamp.from(leaseUntil));
  }

  public boolean completeClaim(Claimed claim, LinkStatus status, Instant checkedAt, Instant nextCheckAt) {
    if (claim == null || status == null || checkedAt == null || nextCheckAt == null
        || !nextCheckAt.isAfter(checkedAt)) {
      throw new IllegalArgumentException("Resultado de ciclo inválido");
    }
    return jdbc.update("""
        UPDATE guardiao.link_check SET status = ?, checked_at = ?, next_check_at = ?,
          last_cycle_id = ?, lease_id = NULL, lease_until = NULL,
          failed_cycles = CASE WHEN ? IN ('QUEBRADO', 'SEM_RESPOSTA')
            THEN LEAST(failed_cycles + 1, 3) ELSE 0 END, updated_at = CURRENT_TIMESTAMP
        WHERE link_id = ? AND url_revision = ? AND lease_id = ? AND lease_until > ?
          AND (checked_at IS NULL OR checked_at < ?)
        """, status.name(), Timestamp.from(checkedAt), Timestamp.from(nextCheckAt), claim.leaseId(),
        status.name(), claim.linkId(), claim.revision(), claim.leaseId(), Timestamp.from(checkedAt),
        Timestamp.from(checkedAt)) == 1;
  }

  public boolean acquireDomain(String host, UUID id, Instant until) {
    return jdbc.update("""
        INSERT INTO guardiao.domain_lease(host, lease_id, lease_until) VALUES (?, ?, ?)
        ON CONFLICT (host) DO UPDATE SET lease_id = EXCLUDED.lease_id, lease_until = EXCLUDED.lease_until
        WHERE guardiao.domain_lease.lease_until <= CURRENT_TIMESTAMP
        """, host, id, Timestamp.from(until)) == 1;
  }

  public void releaseDomain(String host, UUID id) {
    jdbc.update("DELETE FROM guardiao.domain_lease WHERE host = ? AND lease_id = ?", host, id);
  }

  public void releaseClaim(Claimed claim) {
    jdbc.update("""
        UPDATE guardiao.link_check SET lease_id = NULL, lease_until = NULL
        WHERE link_id = ? AND url_revision = ? AND lease_id = ?
        """, claim.linkId(), claim.revision(), claim.leaseId());
  }

  /** Aplica uma vez por ciclo e ignora resultados de URLs que foram alteradas. */
  public boolean completeCycle(long linkId, long urlRevision, UUID cycleId, LinkStatus status,
      Instant checkedAt, Instant nextCheckAt) {
    if (linkId <= 0 || urlRevision <= 0 || cycleId == null || status == null || checkedAt == null
        || nextCheckAt == null || !nextCheckAt.isAfter(checkedAt)) {
      throw new IllegalArgumentException("Resultado de ciclo inválido");
    }
    int updated = jdbc.update("""
        UPDATE guardiao.link_check SET
          status = ?, checked_at = ?, next_check_at = ?, last_cycle_id = ?,
          failed_cycles = CASE WHEN ? IN ('QUEBRADO', 'SEM_RESPOSTA')
            THEN LEAST(failed_cycles + 1, 3) ELSE 0 END,
          updated_at = CURRENT_TIMESTAMP
        WHERE link_id = ? AND url_revision = ? AND last_cycle_id IS DISTINCT FROM ?
          AND (checked_at IS NULL OR checked_at < ?)
        """, status.name(), Timestamp.from(checkedAt), Timestamp.from(nextCheckAt), cycleId,
        status.name(), linkId, urlRevision, cycleId, Timestamp.from(checkedAt));
    return updated == 1;
  }
}
