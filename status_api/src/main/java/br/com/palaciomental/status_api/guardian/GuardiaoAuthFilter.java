package br.com.palaciomental.status_api.guardian;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletInputStream;
import jakarta.servlet.ReadListener;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Bloqueia chamadas antes que o MVC leia o corpo ou acesse o banco. */
@Component
public final class GuardiaoAuthFilter extends OncePerRequestFilter {
  private static final int MAX_BODY_BYTES = 65536;
  private final ServiceToken token;
  private final boolean localHttp;

  public GuardiaoAuthFilter(@Value("${guardiao.service-token:}") String secret, Environment environment) {
    token = new ServiceToken(secret);
    localHttp = environment.acceptsProfiles(Profiles.of("guardiao-local & !production & !prod"));
  }

  @Override
  protected boolean shouldNotFilter(HttpServletRequest request) {
    String path = request.getRequestURI().substring(request.getContextPath().length());
    return !path.startsWith("/v1/guardiao/") && !path.equals("/v1/status");
  }

  @Override
  protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
      FilterChain chain) throws ServletException, IOException {
    int bodyLimit = request.getRequestURI().equals(request.getContextPath() + "/v1/guardiao/tenants")
        && request.getMethod().equals("PUT") ? 1024 * 1024 : MAX_BODY_BYTES;
    if (!token.matches(request.getHeader("Authorization"))) {
      response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
    } else if (!request.isSecure() && !localHttp) {
      response.setStatus(HttpServletResponse.SC_FORBIDDEN);
    } else if (request.getContentLengthLong() > bodyLimit) {
      response.setStatus(HttpServletResponse.SC_REQUEST_ENTITY_TOO_LARGE);
    } else {
      chain.doFilter(new LimitedRequest(request, bodyLimit), response);
    }
  }

  private static final class LimitedRequest extends HttpServletRequestWrapper {
    private ServletInputStream stream;
    private final int bodyLimit;

    LimitedRequest(HttpServletRequest request, int bodyLimit) {
      super(request);
      this.bodyLimit = bodyLimit;
    }

    @Override
    public ServletInputStream getInputStream() throws IOException {
      if (stream == null) {
        ServletInputStream input = super.getInputStream();
        stream = new ServletInputStream() {
          private int count;
          @Override public int read() throws IOException {
            int value = input.read();
            if (value >= 0 && ++count > bodyLimit) throw new IOException("Corpo excede o limite");
            return value;
          }
          @Override public boolean isFinished() { return input.isFinished(); }
          @Override public boolean isReady() { return input.isReady(); }
          @Override public void setReadListener(ReadListener listener) { input.setReadListener(listener); }
        };
      }
      return stream;
    }

    @Override public BufferedReader getReader() throws IOException {
      return new BufferedReader(new InputStreamReader(getInputStream(), StandardCharsets.UTF_8));
    }
  }
}
