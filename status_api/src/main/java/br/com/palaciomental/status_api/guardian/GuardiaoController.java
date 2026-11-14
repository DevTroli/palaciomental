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

  public GuardiaoController(JdbcTemplate jdbc, TransactionTemplate transaction) {
    repository = new LinkCheckRepository(jdbc);
    this.transaction = transaction;
  }

  public record Item(long link_id, String url) {}
  public record Request(List<Item> links) {}
  public record DeleteRequest(long link_id) {}

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
}
