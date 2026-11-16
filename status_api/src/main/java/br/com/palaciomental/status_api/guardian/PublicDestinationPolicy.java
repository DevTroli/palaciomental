package br.com.palaciomental.status_api.guardian;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.URI;
import java.net.UnknownHostException;
import java.util.Arrays;
import java.util.List;

/** Valida URLs e todas as respostas DNS antes de entregá-las ao transporte. */
public final class PublicDestinationPolicy {
  @FunctionalInterface
  public interface Resolver {
    InetAddress[] resolve(String hostname) throws UnknownHostException;
  }

  public record Destination(URI uri, List<InetAddress> addresses) {
    @Override
    public String toString() {
      return "Destination[uri=<redacted>, addresses=<redacted>]";
    }
  }

  private final Resolver resolver;

  public PublicDestinationPolicy(Resolver resolver) {
    this.resolver = resolver;
  }

  /** O transporte deve conectar aos endereços retornados, sem nova resolução DNS. */
  public Destination validate(URI uri) throws UnknownHostException {
    if (uri == null || uri.isOpaque() || uri.getHost() == null || uri.getUserInfo() != null
        || uri.getHost().contains("%") || uri.getPort() > 65535
        || !("http".equalsIgnoreCase(uri.getScheme()) || "https".equalsIgnoreCase(uri.getScheme()))) {
      throw new IllegalArgumentException("Destino não permitido");
    }
    InetAddress[] addresses = resolver.resolve(uri.getHost());
    if (addresses == null || addresses.length == 0 || Arrays.stream(addresses).anyMatch(a -> !isPublic(a))) {
      throw new IllegalArgumentException("Destino não permitido");
    }
    return new Destination(uri, List.copyOf(Arrays.asList(addresses)));
  }

  static boolean isPublic(InetAddress address) {
    if (address == null || address.isAnyLocalAddress() || address.isLoopbackAddress()
        || address.isLinkLocalAddress() || address.isSiteLocalAddress() || address.isMulticastAddress()) {
      return false;
    }
    byte[] bytes = address.getAddress();
    if (address instanceof Inet4Address) {
      return isPublicIpv4(bytes);
    }
    return isPublicIpv6(bytes);
  }

  private static boolean isPublicIpv4(byte[] bytes) {
    int a = bytes[0] & 255, b = bytes[1] & 255, c = bytes[2] & 255;
    return !(a == 0 || a >= 224 || a == 10 || a == 127
        || a == 100 && b >= 64 && b <= 127
        || a == 169 && b == 254 || a == 172 && b >= 16 && b <= 31
        || a == 192 && (b == 168 || b == 0 && (c == 0 || c == 2) || b == 88 && c == 99)
        || a == 198 && (b == 18 || b == 19 || b == 51 && c == 100)
        || a == 203 && b == 0 && c == 113);
  }

  private static boolean isPublicIpv6(byte[] bytes) {
    int a = bytes[0] & 255, b = bytes[1] & 255, c = bytes[2] & 255, d = bytes[3] & 255;
    // Global unicast only; exclude documentation, IETF special-use and transition ranges.
    return (a & 0xe0) == 0x20 && !(a == 0x20 && b == 0x01 && c == 0x0d && d == 0xb8)
        && !(a == 0x20 && b == 0x02) && !(a == 0x20 && b == 0x01 && c <= 1)
        && !(a == 0x3f && b == 0xff && (c & 0xf0) == 0);
  }
}
