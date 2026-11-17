package br.com.palaciomental.status_api;

import java.net.URI;
import java.util.Map;
import org.flywaydb.core.Flyway;
import org.slf4j.LoggerFactory;

/** Executado no pre-deploy, antes de iniciar o contexto Spring e seus schedulers. */
final class GuardiaoMigrations {
  private GuardiaoMigrations() {}

  static void migrate(Map<String, String> environment) {
    String url = required(environment, "GUARDIAO_MIGRATION_JDBC_URL");
    String user = required(environment, "GUARDIAO_MIGRATION_USER");
    String password = required(environment, "GUARDIAO_MIGRATION_PASSWORD");
    validateDestination(environment, url);
    // A saída do release informa somente o resultado, sem imprimir a URL JDBC.
    if (LoggerFactory.getLogger("org.flywaydb") instanceof ch.qos.logback.classic.Logger logger) {
      logger.setLevel(ch.qos.logback.classic.Level.OFF);
    }
    var flyway = Flyway.configure().dataSource(url, user, password)
        .defaultSchema("guardiao").schemas("guardiao").createSchemas(true)
        .locations("classpath:db/guardiao").loggers("slf4j")
        .cleanDisabled(true).baselineOnMigrate(false).outOfOrder(false)
        .validateMigrationNaming(true).validateOnMigrate(true).load();
    var result = flyway.migrate();
    flyway.validate();
    System.out.println("Guardião: " + result.migrationsExecuted + " migration(s) aplicada(s); histórico validado.");
  }

  static void validateDestination(Map<String, String> environment, String url) {
    if (!url.startsWith("jdbc:postgresql://")) throw new IllegalArgumentException("Destino inválido");
    URI target = URI.create(url.substring("jdbc:".length()));
    int port = target.getPort() == -1 ? 5432 : target.getPort();
    if (target.getUserInfo() != null || target.getFragment() != null
        || !required(environment, "POSTGRES_HOST").equalsIgnoreCase(target.getHost())
        || port != Integer.parseInt(required(environment, "POSTGRES_PORT"))
        || !("/" + required(environment, "POSTGRES_DB")).equals(target.getPath())) {
      throw new IllegalArgumentException("A migração deve usar o banco da API");
    }
  }

  private static String required(Map<String, String> environment, String name) {
    String value = environment.get(name);
    if (value == null || value.isBlank()) throw new IllegalArgumentException("Configuração ausente: " + name);
    return value;
  }
}
