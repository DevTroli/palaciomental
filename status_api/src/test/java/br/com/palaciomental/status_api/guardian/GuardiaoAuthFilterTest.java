package br.com.palaciomental.status_api.guardian;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.mock.env.MockEnvironment;

class GuardiaoAuthFilterTest {
  @Test
  void permitsCompleteTenantSnapshotButKeepsOtherRoutesAt64KiB() throws Exception {
    var filter = new GuardiaoAuthFilter("test-secret", new MockEnvironment());
    String item = "{\"organizationId\":\"" + java.util.UUID.randomUUID()
        + "\",\"hostname\":\"" + "a".repeat(249) + ".org\"}";
    byte[] body = ("{\"tenants\":[" + String.join(",", java.util.Collections.nCopies(1000, item)) + "]}")
        .getBytes(java.nio.charset.StandardCharsets.UTF_8);
    var request = new MockHttpServletRequest("PUT", "/v1/guardiao/tenants");
    request.setSecure(true);
    request.addHeader("Authorization", "Bearer test-secret");
    request.setContent(body);
    var called = new AtomicBoolean();
    filter.doFilter(request, new MockHttpServletResponse(), (req, res) -> {
      assertEquals(body.length, req.getInputStream().readAllBytes().length);
      called.set(true);
    });
    assertTrue(called.get());
    request.setRequestURI("/v1/guardiao/links");
    var response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> { throw new AssertionError("Limite alterado em outra rota"); });
    assertEquals(413, response.getStatus());
    request.setRequestURI("/v1/guardiao/tenants");
    request.setContent(new byte[1024 * 1024 + 1]);
    response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> { throw new AssertionError("Snapshot sem limite"); });
    assertEquals(413, response.getStatus());
  }

  @Test
  void inboxAlertsRequireServiceAuthentication() throws Exception {
    var filter = new GuardiaoAuthFilter("test-secret", new MockEnvironment());
    var request = new MockHttpServletRequest("GET", "/v1/guardiao/alertas/inbox");
    request.setSecure(true);
    var response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> { throw new AssertionError("Token ausente"); });
    assertEquals(401, response.getStatus());
    request.addHeader("Authorization", "Bearer test-secret");
    var called = new AtomicBoolean();
    filter.doFilter(request, new MockHttpServletResponse(), (req, res) -> called.set(true));
    assertTrue(called.get());
  }

  @Test
  void statusTecnicoTambemExigeToken() throws Exception {
    var filter = new GuardiaoAuthFilter("test-secret", new MockEnvironment());
    var request = new MockHttpServletRequest("GET", "/v1/status");
    request.setSecure(true);
    var response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> { throw new AssertionError("Token ausente"); });
    assertEquals(401, response.getStatus());
    request.addHeader("Authorization", "Bearer test-secret");
    var called = new AtomicBoolean();
    filter.doFilter(request, new MockHttpServletResponse(), (req, res) -> called.set(true));
    assertTrue(called.get());
  }

  @Test
  void rejectsBeforeBodyProcessingAndRequiresSecureTransport() throws Exception {
    var filter = new GuardiaoAuthFilter("test-secret", new MockEnvironment());
    var request = new MockHttpServletRequest("POST", "/v1/guardiao/links");
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
    var filter = new GuardiaoAuthFilter("test-secret", new MockEnvironment());
    var request = new MockHttpServletRequest("POST", "/v1/guardiao/links");
    request.setSecure(true);
    request.addHeader("Authorization", "Bearer test-secret");
    request.setContent(new byte[65537]);
    var response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> { throw new AssertionError("Unexpected call"); });
    assertEquals(413, response.getStatus());
  }

  @Test
  void localProfileAllowsOnlyAuthenticatedHttpAndProductionStillRequiresHttps() throws Exception {
    var request = new MockHttpServletRequest("POST", "/v1/guardiao/links");
    var local = new MockEnvironment().withProperty("spring.profiles.active", "guardiao-local");
    var filter = new GuardiaoAuthFilter("test-secret", local);
    var response = new MockHttpServletResponse();
    filter.doFilter(request, response, (req, res) -> { throw new AssertionError("Token ausente"); });
    assertEquals(401, response.getStatus());
    request.addHeader("Authorization", "Bearer test-secret");
    response = new MockHttpServletResponse();
    var called = new AtomicBoolean();
    filter.doFilter(request, response, (req, res) -> called.set(true));
    assertTrue(called.get());

    var production = new MockEnvironment().withProperty("spring.profiles.active", "guardiao-local,production");
    response = new MockHttpServletResponse();
    new GuardiaoAuthFilter("test-secret", production).doFilter(request, response,
        (req, res) -> { throw new AssertionError("HTTP em produção"); });
    assertEquals(403, response.getStatus());
  }
}
