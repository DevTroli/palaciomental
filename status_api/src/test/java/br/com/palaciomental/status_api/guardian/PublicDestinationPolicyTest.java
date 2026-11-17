package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.InetAddress;
import java.net.URI;
import org.junit.jupiter.api.Test;

class PublicDestinationPolicyTest {
  @Test
  void permiteSomenteEnderecosPublicosDoResultadoDns() throws Exception {
    InetAddress external = InetAddress.getByAddress(new byte[] {8, 8, 8, 8});
    InetAddress internal = InetAddress.getByAddress(new byte[] {10, 0, 0, 2});
    var safe = new PublicDestinationPolicy(host -> new InetAddress[] {external});
    assertThat(safe.validate(URI.create("https://example.com/page")).addresses()).containsExactly(external);
    var mixed = new PublicDestinationPolicy(host -> new InetAddress[] {external, internal});
    assertThatThrownBy(() -> mixed.validate(URI.create("https://example.com")))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> safe.validate(URI.create("http://user:secret@example.com")))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> safe.validate(URI.create("file:///etc/passwd")))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void bloqueiaFaixasLocaisReservadasETransicoesIpv6() throws Exception {
    for (String address : new String[] {"127.0.0.1", "10.1.2.3", "169.254.169.254", "100.64.1.2",
        "192.0.2.1", "198.18.1.1", "203.0.113.1", "::1", "fd00::1", "fe80::1",
        "2001:db8::1", "2001:20::1", "3fff::1", "2002:0a00:0001::"}) {
      assertThat(PublicDestinationPolicy.isPublic(InetAddress.getByName(address))).as(address).isFalse();
    }
    assertThat(PublicDestinationPolicy.isPublic(InetAddress.getByName("2606:4700:4700::1111"))).isTrue();
  }
}
