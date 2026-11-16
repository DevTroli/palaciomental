package br.com.palaciomental.status_api.guardian;

import java.io.IOException;
import java.math.BigDecimal;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** Consulta prefixos ao Google sem transmitir URLs nem credenciais no endereço. */
public final class GoogleSafeBrowsingTransport implements SafeBrowsingPrototype.Transport {
  private static final String ENDPOINT = "https://safebrowsing.googleapis.com/v5/hashes:search?";
  private static final int MAX_RESPONSE_BYTES = 1024 * 1024;
  private static final JsonMapper JSON = new JsonMapper();
  private final String apiKey;

  public GoogleSafeBrowsingTransport(String apiKey) {
    if (apiKey == null || apiKey.isBlank() || apiKey.contains("\n") || apiKey.contains("\r")) {
      throw new IllegalArgumentException("Chave do provedor inválida.");
    }
    this.apiKey = apiKey;
  }

  @Override
  public SafeBrowsingPrototype.Reply search(List<String> prefixes) throws IOException {
    if (prefixes == null || prefixes.isEmpty() || prefixes.size() > 30) throw new IOException("Prefixos inválidos.");
    var query = new StringBuilder();
    try {
      for (String prefix : prefixes) {
        if (Base64.getDecoder().decode(prefix).length != 4) throw new IllegalArgumentException();
        if (!query.isEmpty()) query.append('&');
        query.append("hashPrefixes=").append(URLEncoder.encode(prefix, StandardCharsets.UTF_8));
      }
    } catch (IllegalArgumentException | NullPointerException ex) {
      throw new IOException("Prefixos inválidos.");
    }
    HttpURLConnection connection = (HttpURLConnection) URI.create(ENDPOINT + query).toURL().openConnection();
    connection.setInstanceFollowRedirects(false);
    connection.setConnectTimeout(3000);
    connection.setReadTimeout(3000);
    connection.setRequestProperty("X-Goog-Api-Key", apiKey);
    try {
      if (connection.getResponseCode() != 200) throw new IOException("Provedor indisponível.");
      try (var input = connection.getInputStream()) {
        byte[] bytes = input.readNBytes(MAX_RESPONSE_BYTES + 1);
        if (bytes.length > MAX_RESPONSE_BYTES) throw new IOException("Resposta excedeu o limite.");
        String type = connection.getContentType();
        return type != null && type.toLowerCase(java.util.Locale.ROOT).startsWith("application/x-protobuf")
            ? SafeBrowsingProtobuf.parse(bytes) : parse(bytes);
      }
    } finally {
      connection.disconnect();
    }
  }

  static SafeBrowsingPrototype.Reply parse(byte[] bytes) throws IOException {
    try {
      JsonNode root = JSON.readTree(bytes);
      if (root == null || !root.isObject() || !root.path("cacheDuration").isTextual()) throw new IllegalArgumentException();
      String rawDuration = root.path("cacheDuration").asText();
      if (!rawDuration.matches("[0-9]+(?:\\.[0-9]{1,9})?s")) throw new IllegalArgumentException();
      long nanos = new BigDecimal(rawDuration.substring(0, rawDuration.length() - 1))
          .movePointRight(9).longValueExact();
      Duration duration = Duration.ofNanos(nanos);
      if (duration.isZero() || duration.isNegative()) throw new IllegalArgumentException();
      JsonNode hashes = root.get("fullHashes");
      if (hashes != null && !hashes.isArray()) throw new IllegalArgumentException();
      List<ThreatHashMatcher.Match> matches = parseMatches(hashes);
      return new SafeBrowsingPrototype.Reply(matches, duration);
    } catch (RuntimeException ex) {
      throw new IOException("Resposta inválida do provedor.");
    }
  }

  private static List<ThreatHashMatcher.Match> parseMatches(JsonNode hashes) {
    List<ThreatHashMatcher.Match> matches = new ArrayList<>();
    if (hashes != null) for (JsonNode hash : hashes) {
        if (!hash.path("fullHash").isTextual() || !hash.path("fullHashDetails").isArray()) throw new IllegalArgumentException();
        byte[] fullHash = Base64.getDecoder().decode(hash.path("fullHash").asText());
        if (fullHash.length != 32) throw new IllegalArgumentException();
        matches.add(new ThreatHashMatcher.Match(fullHash, parseDetails(hash.path("fullHashDetails"))));
    }
    return matches;
  }

  private static List<ThreatHashMatcher.Detail> parseDetails(JsonNode detailsNode) {
    List<ThreatHashMatcher.Detail> details = new ArrayList<>();
    for (JsonNode detail : detailsNode) {
          if (!detail.path("threatType").isTextual()) throw new IllegalArgumentException();
          JsonNode attrs = detail.get("attributes");
          if (attrs != null && !attrs.isArray()) throw new IllegalArgumentException();
          List<String> attributes = new ArrayList<>();
          if (attrs != null) for (JsonNode attr : attrs) {
            if (!attr.isTextual()) throw new IllegalArgumentException();
            attributes.add(attr.asText());
          }
      details.add(new ThreatHashMatcher.Detail(detail.path("threatType").asText(), attributes));
    }
    return details;
  }
}
