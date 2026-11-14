package br.com.palaciomental.status_api.guardian;

import java.net.URI;
import java.util.List;
import java.util.UUID;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

/** Interface interna: a autenticação acontece antes da leitura ou interpretação do corpo. */
@RestController
@ConditionalOnProperty(name = "guardiao.enabled", havingValue = "true")
public final class GuardiaoController {
  private final LinkCheckRepository repository;
  private final TransactionTemplate transaction;

  public GuardiaoController(JdbcTemplate jdbc, TransactionTemplate transaction) {
    repository = new LinkCheckRepository(jdbc);
    this.transaction = transaction;
  }

  public record Item(long link_id, String url) {}
  public record Request(List<Item> links) {}
  public record Snapshot(String id) {}

  @PostMapping("/internal/guardiao/snapshot")
  public ResponseEntity<Snapshot> startSnapshot() {
    UUID id = UUID.randomUUID();
    if (!repository.startSnapshot(id)) {
      return ResponseEntity.status(HttpStatus.CONFLICT).build();
    }
    return ResponseEntity.status(HttpStatus.CREATED).body(new Snapshot(id.toString()));
  }

  @PostMapping("/internal/guardiao/snapshot/finish")
  public ResponseEntity<Void> finishSnapshot(@RequestHeader("X-Guardiao-Snapshot") String snapshot) {
    try {
      UUID id = UUID.fromString(snapshot);
      boolean finished = Boolean.TRUE.equals(transaction.execute(status -> {
        if (!repository.lockSnapshot(id)) return false;
        repository.finishSnapshot(id);
        return true;
      }));
      return finished ? ResponseEntity.noContent().build() : ResponseEntity.status(HttpStatus.CONFLICT).build();
    } catch (IllegalArgumentException ex) {
      return ResponseEntity.badRequest().build();
    }
  }

  @PostMapping("/internal/guardiao/snapshot/abort")
  public ResponseEntity<Void> abortSnapshot(@RequestHeader("X-Guardiao-Snapshot") String snapshot) {
    try {
      UUID id = UUID.fromString(snapshot);
      repository.abortSnapshot(id);
      return ResponseEntity.noContent().build();
    } catch (IllegalArgumentException ex) {
      return ResponseEntity.badRequest().build();
    }
  }

  @PostMapping("/internal/guardiao/links")
  public ResponseEntity<Void> submit(@RequestHeader("X-Guardiao-Snapshot") String snapshot,
      @RequestBody Request body) {
    try {
      UUID id = UUID.fromString(snapshot);
      if (body == null || body.links() == null || body.links().size() > LinkBatch.MAX_LINKS) {
        throw new IllegalArgumentException();
      }
      var links = body.links().stream().map(item -> {
        if (item == null || item.url() == null) {
          throw new IllegalArgumentException();
        }
        URI uri = URI.create(item.url());
        if (uri.getHost() == null || uri.getHost().length() > 253 || uri.getUserInfo() != null || uri.isOpaque()
            || !("https".equalsIgnoreCase(uri.getScheme()) || "http".equalsIgnoreCase(uri.getScheme()))) {
          throw new IllegalArgumentException();
        }
        return new LinkBatch.Link(item.link_id(), uri);
      }).toList();
      LinkBatch batch = new LinkBatch(links);
      boolean accepted = Boolean.TRUE.equals(transaction.execute(status -> {
        if (!repository.lockSnapshot(id)) return false;
        repository.enqueueSnapshot(batch, id);
        return true;
      }));
      return accepted ? ResponseEntity.accepted().build() : ResponseEntity.status(HttpStatus.CONFLICT).build();
    } catch (IllegalArgumentException ex) {
      return ResponseEntity.badRequest().build();
    }
  }
}
