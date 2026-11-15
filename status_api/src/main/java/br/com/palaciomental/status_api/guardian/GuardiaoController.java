package br.com.palaciomental.status_api.guardian;

import java.net.URI;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/** Interface interna autenticada; operações podem ser repetidas com segurança. */
@RestController
public final class GuardiaoController {
  private final LinkCheckRepository repository;
  private final TransactionTemplate transaction;
  private final ThreatService threats;

  public GuardiaoController(JdbcTemplate jdbc, TransactionTemplate transaction, ThreatService threats) {
    repository = new LinkCheckRepository(jdbc);
    this.transaction = transaction;
    this.threats = threats;
  }

  public record Item(long link_id, String url) {}
  public record Request(List<Item> links) {}
  public record DeleteRequest(long link_id) {}
  public record ResultRequest(List<Long> link_ids) {}
  public record ThreatRequest(List<String> urls) {}
  public record ThreatResult(String state, String checkedAt, String expiresAt) {
    static ThreatResult from(ThreatAssessment result) {
      return new ThreatResult(result.state().name(),
          result.checkedAt() == null ? null : result.checkedAt().toString(),
          result.expiresAt() == null ? null : result.expiresAt().toString());
    }
  }

  @PostMapping("/internal/guardiao/links/threats")
  public ResponseEntity<List<ThreatResult>> threats(@RequestBody ThreatRequest body) {
    if (body == null || body.urls() == null || body.urls().size() > 6
        || body.urls().stream().anyMatch(url -> url == null || url.length() > 500)) {
      return ResponseEntity.badRequest().build();
    }
    return ResponseEntity.ok(body.urls().stream().map(threats::check).map(ThreatResult::from).toList());
  }

  @PostMapping("/internal/guardiao/links")
  public ResponseEntity<Void> submit(@RequestBody Request body) {
    try {
      if (body == null || body.links() == null || body.links().size() > LinkBatch.MAX_LINKS) {
        throw new IllegalArgumentException();
      }
      var links = body.links().stream().map(item -> {
        if (item == null || item.url() == null) throw new IllegalArgumentException();
        URI uri = URI.create(item.url());
        if (uri.getHost() == null || uri.getHost().length() > 253 || uri.getUserInfo() != null || uri.isOpaque()
            || !("https".equalsIgnoreCase(uri.getScheme()) || "http".equalsIgnoreCase(uri.getScheme()))) {
          throw new IllegalArgumentException();
        }
        return new LinkBatch.Link(item.link_id(), uri);
      }).toList();
      LinkBatch batch = new LinkBatch(links);
      transaction.executeWithoutResult(status -> repository.enqueue(batch));
      return ResponseEntity.accepted().build();
    } catch (IllegalArgumentException ex) {
      return ResponseEntity.badRequest().build();
    }
  }

  @PostMapping("/internal/guardiao/links/delete")
  public ResponseEntity<Void> delete(@RequestBody DeleteRequest body) {
    if (body == null || body.link_id() <= 0) return ResponseEntity.badRequest().build();
    repository.delete(body.link_id());
    return ResponseEntity.noContent().build();
  }

  @PostMapping("/internal/guardiao/links/results")
  public ResponseEntity<List<LinkCheckRepository.LinkResult>> results(@RequestBody ResultRequest body) {
    if (body == null || body.link_ids() == null || body.link_ids().size() > LinkBatch.MAX_LINKS
        || body.link_ids().stream().anyMatch(id -> id == null || id <= 0)) {
      return ResponseEntity.badRequest().build();
    }
    return ResponseEntity.ok(repository.results(body.link_ids()));
  }
}
