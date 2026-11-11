package br.com.palaciomental.status_api.guardian;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** Verifica um token de serviço sem incluir credenciais em mensagens ou logs. */
public final class ServiceToken {
  private static final int MAX_HEADER_LENGTH = 4096;
  private final byte[] expectedDigest;

  public ServiceToken(String secret) {
    if (secret == null || secret.isBlank()) {
      throw new IllegalArgumentException("Token de serviço não configurado");
    }
    expectedDigest = digest(secret);
  }

  public boolean matches(String authorization) {
    if (authorization == null || authorization.length() > MAX_HEADER_LENGTH
        || !authorization.startsWith("Bearer ") || authorization.length() == 7) {
      return false;
    }
    return MessageDigest.isEqual(expectedDigest, digest(authorization.substring(7)));
  }

  private static byte[] digest(String value) {
    try {
      return MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
    } catch (NoSuchAlgorithmException exc) {
      throw new IllegalStateException("Algoritmo de verificação indisponível", exc);
    }
  }
}
