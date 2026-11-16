package br.com.palaciomental.status_api.guardian;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import org.apache.hc.client5.http.psl.PublicSuffixMatcherLoader;

/** Protótipo conservador: formatos ainda não suportados retornam vazio, nunca um veredito. */
public final class ThreatUrlHashes {
  private ThreatUrlHashes() {}

  public record Candidates(List<byte[]> fullHashes, List<String> prefixes) {
    public Candidates {
      fullHashes = fullHashes.stream().map(byte[]::clone).toList();
      prefixes = List.copyOf(prefixes);
    }
    @Override public List<byte[]> fullHashes() { return fullHashes.stream().map(byte[]::clone).toList(); }
    @Override public String toString() { return "Candidates[redacted]"; }
  }

  /** Formatos que não podem ser normalizados com segurança permanecem não verificados. */
  public static Optional<Candidates> fromUrl(String value) {
    if (value == null || value.length() > 500
        || value.chars().anyMatch(c -> c < 0x20 || c == 0x7f)) return Optional.empty();
    try {
      URI uri = URI.create(value);
      String host = extractHost(uri);
      if (uri.isOpaque() || uri.getUserInfo() != null || host == null
          || uri.getPort() > 65535
          || !("http".equalsIgnoreCase(uri.getScheme()) || "https".equalsIgnoreCase(uri.getScheme()))
          || !host.matches("[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)*\\.[A-Za-z0-9-]+")) return Optional.empty();
      host = host.toLowerCase(Locale.ROOT);
      java.net.IDN.toASCII(host, java.net.IDN.USE_STD3_ASCII_RULES);
      String tld = host.substring(host.lastIndexOf('.') + 1);
      if (!tld.matches("[a-z-]+|xn--[a-z0-9-]+")) return Optional.empty();
      var suffixes = PublicSuffixMatcherLoader.getDefault();
      if (!suffixes.matches(tld)) return Optional.empty();
      String root = suffixes.getDomainRoot(host);
      if (root == null || !(host.equals(root) || host.endsWith("." + root))) return Optional.empty();
      String rawPath = uri.getRawPath();
      if (rawPath == null || rawPath.isEmpty()) rawPath = "/";
      rawPath = new String(unescape(rawPath), StandardCharsets.ISO_8859_1).replaceAll("/{2,}", "/");
      if (!rawPath.startsWith("/") || rawPath.indexOf('?') >= 0) return Optional.empty();
      rawPath = normalizePath(rawPath);
      String path = escape(rawPath.getBytes(StandardCharsets.ISO_8859_1));
      String query = uri.getRawQuery() == null ? null : escape(unescape(uri.getRawQuery()));
      return Optional.of(buildCandidates(host, root, path, query));
    } catch (IllegalArgumentException ex) {
      return Optional.empty();
    }
  }

  private static String extractHost(URI uri) {
    String host = uri.getHost();
      if (host == null && uri.getRawAuthority() != null) {
        String authority = uri.getRawAuthority();
        if (authority.indexOf('@') >= 0 || authority.indexOf('%') >= 0 || authority.startsWith("[")) return null;
        int colon = authority.lastIndexOf(':');
        if (colon >= 0) {
          String port = authority.substring(colon + 1);
          if (!port.matches("[0-9]{1,5}") || Integer.parseInt(port) > 65535) return null;
          authority = authority.substring(0, colon);
        }
        host = java.net.IDN.toASCII(authority, java.net.IDN.USE_STD3_ASCII_RULES);
      }
    return host;
  }

  private static Candidates buildCandidates(String host, String root, String path, String query) {
      Set<String> paths = new LinkedHashSet<>();
      if (query != null) paths.add(path + "?" + query);
      paths.add(path);
      paths.add("/");
      int slash = 0;
      while (paths.size() < 6 && (slash = path.indexOf('/', slash + 1)) >= 0) {
        paths.add(path.substring(0, slash + 1));
        if (paths.size() >= (query == null ? 5 : 6)) break;
      }
      Set<String> hosts = new LinkedHashSet<>();
      hosts.add(host);
      String[] labels = host.split("\\.");
      int rootStart = labels.length - root.split("\\.").length;
      for (int start = rootStart; start >= 0 && rootStart - start < 4; start--) {
        hosts.add(String.join(".", java.util.Arrays.copyOfRange(labels, start, labels.length)));
      }
      List<byte[]> hashes = new ArrayList<>();
      Set<String> prefixes = new LinkedHashSet<>();
      for (String candidateHost : hosts) {
        for (String candidatePath : paths) {
          byte[] hash = sha256(candidateHost + candidatePath);
          hashes.add(hash);
          prefixes.add(Base64.getEncoder().encodeToString(java.util.Arrays.copyOf(hash, 4)));
        }
      }
    return new Candidates(hashes, List.copyOf(prefixes));
  }

  private static String normalizePath(String path) {
    boolean trailing = path.endsWith("/") || path.endsWith("/.") || path.endsWith("/..");
    var parts = new java.util.ArrayDeque<String>();
    for (String part : path.split("/")) {
      if (part.isEmpty() || part.equals(".")) continue;
      if (part.equals("..")) {
        if (!parts.isEmpty()) parts.removeLast();
      } else parts.addLast(part);
    }
    String result = "/" + String.join("/", parts);
    return trailing && !parts.isEmpty() ? result + "/" : result;
  }

  private static byte[] unescape(String value) {
    byte[] input = value.getBytes(StandardCharsets.UTF_8);
    for (int round = 0; round < 32; round++) {
      var result = new java.io.ByteArrayOutputStream();
      boolean changed = false;
      for (int i = 0; i < input.length; i++) {
        if (input[i] == '%' && i + 2 < input.length) {
          int high = hex(input[i + 1]);
          int low = hex(input[i + 2]);
          if (high >= 0 && low >= 0) {
            result.write((high << 4) | low);
            i += 2;
            changed = true;
            continue;
          }
        }
        result.write(input[i]);
      }
      input = result.toByteArray();
      if (!changed) return input;
    }
    throw new IllegalArgumentException("Codificação excessiva");
  }

  private static int hex(byte value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
  }

  private static String escape(byte[] value) {
    var result = new StringBuilder();
    for (byte item : value) {
      int b = item & 0xff;
      if (b <= 32 || b >= 127 || b == '#' || b == '%') result.append(String.format("%%%02X", b));
      else result.append((char) b);
    }
    return result.toString();
  }

  private static byte[] sha256(String expression) {
    try {
      return MessageDigest.getInstance("SHA-256").digest(expression.getBytes(StandardCharsets.UTF_8));
    } catch (NoSuchAlgorithmException ex) {
      throw new IllegalStateException("SHA-256 indisponível", ex);
    }
  }
}
