package br.com.palaciomental.status_api;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1")
public class PingController {

  @GetMapping("/ping")
  public Map<String, String> ping()  {
    return Map.of("status","ok");
  }
}
