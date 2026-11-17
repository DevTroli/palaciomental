package br.com.palaciomental.status_api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class StatusApiApplication {

	public static void main(String[] args) {
		if (java.util.Arrays.asList(args).contains("--migrate-only")) {
			try {
				if (args.length != 1) throw new IllegalArgumentException("Argumentos inválidos");
				GuardiaoMigrations.migrate(System.getenv());
			} catch (RuntimeException exception) {
				System.err.println("Migração do Guardião falhou. Confira configuração, conexão, permissões e histórico Flyway.");
				System.exit(1);
			}
			return;
		}
		SpringApplication.run(StatusApiApplication.class, args);
	}

}
