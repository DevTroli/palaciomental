package br.com.palaciomental.status_api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

import java.util.Map;
import org.junit.jupiter.api.Test;

class PingControllerTest {

  @Test
  void pingDeveResponderOk() {
    PingController controller = new PingController();

    Map<String, String> response = controller.ping();

    assertNotNull(response);
    assertEquals("ok", response.get("status"));
  }
}
