package br.com.palaciomental.status_api.guardian;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class GuardiaoAuthFilterTest {
  @Test
  void rejectsBeforeBodyProcessingAndRequiresSecureTransport() throws Exception {
    var filter = new GuardiaoAuthFilter("test-secret");
    var request = new MockHttpServletRequest("POST", "/internal/guardiao/links");
    var response = new MockHttpServletResponse();
    var called = new AtomicBoolean();
    filter.doFilter(request, response, (req, res) -> called.set(true));
    assertEquals(401, response.getStatus());
    assertTrue(!called.get());

    request.addHeader("Authorization", "Bearer test-secret");
    response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> called.set(true));
    assertEquals(403, response.getStatus());
    assertTrue(!called.get());

    request.setSecure(true);
    response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> called.set(true));
    assertTrue(called.get());
  }

  @Test
  void rejectsOversizedAuthenticatedBody() throws Exception {
    var filter = new GuardiaoAuthFilter("test-secret");
    var request = new MockHttpServletRequest("POST", "/internal/guardiao/links");
    request.setSecure(true);
    request.addHeader("Authorization", "Bearer test-secret");
    request.setContent(new byte[65537]);
    var response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> { throw new AssertionError("Unexpected call"); });
    assertEquals(413, response.getStatus());
  }
}
