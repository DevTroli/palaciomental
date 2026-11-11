package br.com.palaciomental.status_api.guardian;

/** Classifica somente a resposta HTTP; validação de destino é responsabilidade do transporte. */
public final class LinkClassification {
  private LinkClassification() {}

  public static LinkStatus fromHttp(int code, boolean redirectDestinationValidated) {
    if (code >= 200 && code < 300) {
      return LinkStatus.ACESSIVEL;
    }
    if (code >= 300 && code < 400) {
      if (!redirectDestinationValidated) {
        throw new IllegalArgumentException("Destino do redirecionamento não foi validado");
      }
      return LinkStatus.REDIRECIONADO;
    }
    if (code == 401 || code == 403) {
      return LinkStatus.REQUER_LOGIN;
    }
    if (code == 404 || code == 410) {
      return LinkStatus.QUEBRADO;
    }
    return LinkStatus.SEM_RESPOSTA;
  }

  public static boolean isTransient(int code) {
    return code == 429 || code >= 500 && code < 600;
  }
}
