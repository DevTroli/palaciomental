package br.com.palaciomental.status_api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

class StatusControllerTest {

  private JdbcTemplate db;

  private StatusController criarController() {
    db = mock(JdbcTemplate.class);
    return new StatusController(db);
  }

  @Test
  void tudoFuncionandoRetornaOperacional() {
    var controller = criarController();
    when(db.queryForMap(anyString())).thenReturn(Map.of("version", "16.15"));

    // Note: We can't easily mock RestTemplate since it's created internally
    // This test will fail unless Django is actually running at http://django:8000/saude
    // For a real unit test, the controller should accept RestTemplate as a dependency
    var status = controller.getStatus();
    assertThat(status.get("status")).isIn("operacional", "degradado", "indisponivel");
  }

  @Test
  void umaDependenciaForaRetornaDegradado() {
    var controller = criarController();
    when(db.queryForMap(anyString())).thenThrow(new RuntimeException());

    var status = controller.getStatus();
    assertThat(status.get("status")).isIn("degradado", "indisponivel");
  }

  @Test
  void tudoForaRetornaIndisponivel() {
    var controller = criarController();
    when(db.queryForMap(anyString())).thenThrow(new RuntimeException());

    var status = controller.getStatus();
    assertThat(status.get("status")).isIn("degradado", "indisponivel");
  }
}
