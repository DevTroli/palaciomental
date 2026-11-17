package br.com.palaciomental.status_api.guardian;

import java.net.URI;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Contrato mínimo: não inclui nomes, conteúdos de projetos ou dados de tenants. */
public record LinkBatch(List<Link> links) {
  public static final int MAX_LINKS = 100;
  public static final int MAX_URL_LENGTH = 500;

  public record Link(long linkId, URI url) {
    @Override
    public String toString() {
      return "Link[linkId=" + linkId + ", url=<redacted>]";
    }
  }

  public LinkBatch {
    if (links == null || links.isEmpty() || links.size() > MAX_LINKS) {
      throw new IllegalArgumentException("Lote deve conter entre 1 e 100 links");
    }
    Set<Long> ids = new HashSet<>();
    for (Link link : links) {
      if (link == null || link.linkId() <= 0 || link.url() == null
          || link.url().toASCIIString().length() > MAX_URL_LENGTH || !ids.add(link.linkId())) {
        throw new IllegalArgumentException("Lote contém link inválido ou repetido");
      }
    }
    links = List.copyOf(links);
  }
}
