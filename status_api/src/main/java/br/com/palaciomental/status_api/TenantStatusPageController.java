package br.com.palaciomental.status_api;

import io.swagger.v3.oas.annotations.Hidden;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@Hidden
@RestController
public class TenantStatusPageController {
  @GetMapping(value = {"/status", "/status/org/{slug}"}, produces = MediaType.TEXT_HTML_VALUE)
  public Resource page() {
    return new ClassPathResource("static/index.html");
  }
}
