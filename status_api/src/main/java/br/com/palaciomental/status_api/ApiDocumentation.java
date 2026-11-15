package br.com.palaciomental.status_api;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ApiDocumentation {
  @Bean
  OpenAPI openApi() {
    return new OpenAPI()
        .info(new Info()
            .title("Palácio Mental · API de operação")
            .version("1.0")
            .description("Verifique links e consulte o estado dos serviços do Palácio Mental. "
                + "Para operações protegidas, informe o token de serviço em Authorize e use HTTPS."))
        .schemaRequirement("serviceToken", new SecurityScheme()
            .type(SecurityScheme.Type.HTTP)
            .scheme("bearer")
            .bearerFormat("token de serviço"));
  }
}
