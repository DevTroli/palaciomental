package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.InetAddress;
import java.net.URI;
import java.net.UnknownHostException;
import org.junit.jupiter.api.Test;

class HttpLinkProbeTest {
  @Test
  void bloqueiaEnderecoInternoAntesDeConectar() throws Exception {
    InetAddress internal = InetAddress.getByAddress(new byte[] {127, 0, 0, 1});
    var probe = new HttpLinkProbe(new PublicDestinationPolicy(host -> new InetAddress[] {internal}));
    assertThatThrownBy(() -> probe.check(URI.create("http://example.com")))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void falhaDnsEhTransitoriaSemAlegarSucesso() {
    var probe = new HttpLinkProbe(new PublicDestinationPolicy(host -> {
      throw new UnknownHostException();
    }));
    var result = probe.check(URI.create("https://example.com"));
    assertThat(result.status()).isEqualTo(LinkStatus.SEM_RESPOSTA);
    assertThat(result.transientFailure()).isTrue();
  }

  @Test
  void destinoDeRedirecionamentoTambemPrecisaSerPublico() throws Exception {
    InetAddress publicAddress = InetAddress.getByAddress(new byte[] {8, 8, 8, 8});
    InetAddress privateAddress = InetAddress.getByAddress(new byte[] {10, 0, 0, 1});
    var probe = new HttpLinkProbe(new PublicDestinationPolicy(host ->
        new InetAddress[] {host.equals("private.example") ? privateAddress : publicAddress}));
    URI source = URI.create("https://example.com/start");
    assertThat(probe.classify(source, 302, "/public").status()).isEqualTo(LinkStatus.REDIRECIONADO);
    assertThatThrownBy(() -> probe.classify(source, 302, "http://private.example/"))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> probe.classify(source, 302, null)).isInstanceOf(IllegalArgumentException.class);
  }
}
