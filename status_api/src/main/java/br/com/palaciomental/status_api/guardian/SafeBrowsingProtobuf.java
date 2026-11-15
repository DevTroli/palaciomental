package br.com.palaciomental.status_api.guardian;

import com.google.protobuf.CodedInputStream;
import java.io.IOException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/** Lê os campos da resposta hashes.search conforme o protocolo público do Google. */
final class SafeBrowsingProtobuf {
  private SafeBrowsingProtobuf() {}

  static SafeBrowsingPrototype.Reply parse(byte[] bytes) throws IOException {
    var input = CodedInputStream.newInstance(bytes);
    List<ThreatHashMatcher.Match> matches = new ArrayList<>();
    Duration duration = null;
    while (!input.isAtEnd()) {
      int tag = input.readTag();
      if (tag == 10) matches.add(fullHash(input.readByteArray()));
      else if (tag == 18) {
        if (duration != null) throw new IOException("Validade duplicada.");
        duration = duration(input.readByteArray());
      } else if (!input.skipField(tag)) throw new IOException("Resposta inválida.");
    }
    if (duration == null || duration.isZero() || duration.isNegative()) throw new IOException("Validade inválida.");
    return new SafeBrowsingPrototype.Reply(matches, duration);
  }

  private static Duration duration(byte[] bytes) throws IOException {
    var input = CodedInputStream.newInstance(bytes);
    long seconds = 0;
    int nanos = 0;
    while (!input.isAtEnd()) {
      int tag = input.readTag();
      if (tag == 8) seconds = input.readInt64();
      else if (tag == 16) nanos = input.readInt32();
      else if (!input.skipField(tag)) throw new IOException("Validade inválida.");
    }
    if (seconds < 0 || nanos < 0 || nanos > 999_999_999) throw new IOException("Validade inválida.");
    return Duration.ofSeconds(seconds, nanos);
  }

  private static ThreatHashMatcher.Match fullHash(byte[] bytes) throws IOException {
    var input = CodedInputStream.newInstance(bytes);
    byte[] hash = null;
    List<ThreatHashMatcher.Detail> details = new ArrayList<>();
    while (!input.isAtEnd()) {
      int tag = input.readTag();
      if (tag == 10) {
        if (hash != null) throw new IOException("Hash duplicado.");
        hash = input.readByteArray();
      } else if (tag == 18) details.add(detail(input.readByteArray()));
      else if (!input.skipField(tag)) throw new IOException("Hash inválido.");
    }
    if (hash == null || hash.length != 32) throw new IOException("Hash inválido.");
    return new ThreatHashMatcher.Match(hash, details);
  }

  private static ThreatHashMatcher.Detail detail(byte[] bytes) throws IOException {
    var input = CodedInputStream.newInstance(bytes);
    int type = 0;
    List<String> attributes = new ArrayList<>();
    while (!input.isAtEnd()) {
      int tag = input.readTag();
      if (tag == 8) type = input.readEnum();
      else if (tag == 16) attributes.add(attribute(input.readEnum()));
      else if (tag == 18) {
        var packed = CodedInputStream.newInstance(input.readByteArray());
        while (!packed.isAtEnd()) attributes.add(attribute(packed.readEnum()));
      } else if (!input.skipField(tag)) throw new IOException("Detalhe inválido.");
    }
    return new ThreatHashMatcher.Detail(switch (type) {
      case 1 -> "MALWARE";
      case 2 -> "SOCIAL_ENGINEERING";
      default -> "UNKNOWN";
    }, attributes);
  }

  private static String attribute(int value) {
    return switch (value) {
      case 1 -> "CANARY";
      case 2 -> "FRAME_ONLY";
      default -> "UNKNOWN";
    };
  }
}
