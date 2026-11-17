package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.util.Map;
import org.junit.jupiter.api.Test;

class GuardiaoMigrationsTest {
  private final Map<String, String> runtime = Map.of(
      "POSTGRES_HOST", "database.internal", "POSTGRES_PORT", "5432", "POSTGRES_DB", "palacio");

  @Test
  void allowsSeparateCredentialsOnlyForTheRuntimeDatabase() {
    assertThatCode(() -> GuardiaoMigrations.validateDestination(runtime,
        "jdbc:postgresql://database.internal:5432/palacio?sslmode=require")).doesNotThrowAnyException();
    assertThatThrownBy(() -> GuardiaoMigrations.validateDestination(runtime,
        "jdbc:postgresql://database.internal:5432/another_database")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> GuardiaoMigrations.validateDestination(runtime,
        "jdbc:postgresql://another.internal:5432/palacio")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> GuardiaoMigrations.validateDestination(runtime,
        "jdbc:postgresql://user:secret@database.internal:5432/palacio")).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void neverFallsBackToRuntimeCredentialsWhenMigrationCredentialsAreAbsent() {
    assertThatThrownBy(() -> GuardiaoMigrations.migrate(runtime)).isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("GUARDIAO_MIGRATION_JDBC_URL");
  }
}
