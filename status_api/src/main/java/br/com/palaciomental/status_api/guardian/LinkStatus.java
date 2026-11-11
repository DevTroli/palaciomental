package br.com.palaciomental.status_api.guardian;

/** Disponibilidade da referência, independente de reputação ou ameaça. */
public enum LinkStatus {
  ACESSIVEL,
  REDIRECIONADO,
  REQUER_LOGIN,
  QUEBRADO,
  SEM_RESPOSTA
}
