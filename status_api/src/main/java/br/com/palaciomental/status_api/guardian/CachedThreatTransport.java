package br.com.palaciomental.status_api.guardian;

import java.io.IOException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Cache por prefixo, inclusive para respostas sem correspondências. */
final class CachedThreatTransport implements SafeBrowsingPrototype.Transport {
  private static final int MAX_PREFIXES = 10_000;
  private record Entry(List<ThreatHashMatcher.Match> matches, Instant receivedAt, Instant expiresAt) {}
  private final SafeBrowsingPrototype.Transport delegate;
  private final Clock clock;
  private final Map<String, Entry> cache = new HashMap<>();

  CachedThreatTransport(SafeBrowsingPrototype.Transport delegate, Clock clock) {
    this.delegate = delegate;
    this.clock = clock;
  }

  @Override
  public synchronized SafeBrowsingPrototype.Reply search(List<String> prefixes) throws IOException {
    Instant now = clock.instant();
    cache.entrySet().removeIf(entry -> !entry.getValue().expiresAt().isAfter(now));
    var missing = prefixes.stream().distinct().filter(prefix -> !cache.containsKey(prefix)).toList();
    if (!missing.isEmpty()) {
      cacheMissing(missing);
    }
    var entries = prefixes.stream().distinct().map(cache::get).toList();
    if (entries.stream().anyMatch(entry -> entry != null && !entry.matches().isEmpty())
        && entries.stream().filter(java.util.Objects::nonNull).map(Entry::receivedAt).distinct().count() > 1) {
      // O contrato possui um único horário: renove o conjunto, sem rejuvenescer dados locais.
      cacheMissing(prefixes.stream().distinct().toList());
    }
    List<ThreatHashMatcher.Match> matches = new ArrayList<>();
    Instant oldest = clock.instant();
    Instant expiry = Instant.MAX;
    for (String prefix : prefixes) {
      Entry entry = cache.get(prefix);
      if (entry == null) throw new IOException("Prefixo não encontrado.");
      matches.addAll(entry.matches());
      if (entry.receivedAt().isBefore(oldest)) oldest = entry.receivedAt();
      if (entry.expiresAt().isBefore(expiry)) expiry = entry.expiresAt();
    }
    return new SafeBrowsingPrototype.Reply(matches, Duration.between(oldest, expiry), oldest);
  }

  private void cacheMissing(List<String> missing) throws IOException {
    long newPrefixes = missing.stream().distinct().filter(prefix -> !cache.containsKey(prefix)).count();
    if (cache.size() + newPrefixes > MAX_PREFIXES) throw new IOException("Cache de consultas cheio.");
    var reply = delegate.search(missing);
    Instant received = clock.instant();
    if (reply == null || reply.matches() == null || reply.cacheDuration() == null
        || reply.cacheDuration().isZero() || reply.cacheDuration().isNegative()) throw new IOException("Resposta inválida.");
    // A API permite estender respostas inteiramente vazias por até 24 horas.
    Duration cacheDuration = reply.matches().isEmpty()
        && reply.cacheDuration().compareTo(Duration.ofHours(24)) < 0
        ? Duration.ofHours(24) : reply.cacheDuration();
    final Instant expires;
    try { expires = received.plus(cacheDuration); }
    catch (RuntimeException ex) { throw new IOException("Validade inválida."); }
    Map<String, List<ThreatHashMatcher.Match>> grouped = new HashMap<>();
    for (String prefix : missing) grouped.put(prefix, new ArrayList<>());
    for (var match : reply.matches()) {
      if (match == null || match.fullHash() == null || match.fullHash().length != 32) throw new IOException("Resposta inválida.");
      String prefix = Base64.getEncoder().encodeToString(java.util.Arrays.copyOf(match.fullHash(), 4));
      if (!grouped.containsKey(prefix)) throw new IOException("Resposta inválida.");
      grouped.get(prefix).add(match);
    }
    grouped.forEach((prefix, matches) -> cache.put(prefix, new Entry(List.copyOf(matches), received, expires)));
  }
}
