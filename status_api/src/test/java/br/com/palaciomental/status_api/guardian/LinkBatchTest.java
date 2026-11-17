package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class LinkBatchTest {
  @Test
  void limitaLoteERejeitaIdentificadoresRepetidos() {
    var link = new LinkBatch.Link(1, URI.create("https://example.com"));
    assertThat(new LinkBatch(List.of(link)).links()).containsExactly(link);
    assertThatThrownBy(() -> new LinkBatch(List.of())).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new LinkBatch(List.of(link, link))).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new LinkBatch(List.of(new LinkBatch.Link(0, link.url()))))
        .isInstanceOf(IllegalArgumentException.class);
    var links = new ArrayList<LinkBatch.Link>();
    for (int i = 1; i <= 101; i++) {
      links.add(new LinkBatch.Link(i, link.url()));
    }
    assertThatThrownBy(() -> new LinkBatch(links)).isInstanceOf(IllegalArgumentException.class);
  }
}
