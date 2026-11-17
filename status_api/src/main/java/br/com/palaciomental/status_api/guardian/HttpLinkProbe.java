package br.com.palaciomental.status_api.guardian;

import java.io.IOException;
import java.net.InetAddress;
import java.net.URI;
import java.net.UnknownHostException;
import java.util.concurrent.TimeUnit;
import org.apache.hc.client5.http.DnsResolver;
import org.apache.hc.client5.http.classic.methods.HttpHead;
import org.apache.hc.client5.http.config.ConnectionConfig;
import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.client5.http.impl.io.PoolingHttpClientConnectionManagerBuilder;
import org.apache.hc.core5.http.Header;

/** Uma tentativa HEAD, sem redirecionamento automático e sem registrar URLs. */
public final class HttpLinkProbe {
  public record Result(LinkStatus status, boolean transientFailure) {}

  private final PublicDestinationPolicy policy;

  public HttpLinkProbe(PublicDestinationPolicy policy) {
    this.policy = policy;
  }

  public Result check(URI uri) {
    final PublicDestinationPolicy.Destination destination;
    try {
      destination = policy.validate(uri);
    } catch (UnknownHostException exc) {
      return new Result(LinkStatus.SEM_RESPOSTA, true);
    }
    DnsResolver pinned = new DnsResolver() {
      @Override
      public InetAddress[] resolve(String hostname) throws UnknownHostException {
        if (!hostname.equalsIgnoreCase(destination.uri().getHost())) {
          throw new UnknownHostException("Destino não autorizado");
        }
        return destination.addresses().toArray(InetAddress[]::new);
      }

      @Override
      public String resolveCanonicalHostname(String hostname) throws UnknownHostException {
        resolve(hostname);
        return hostname;
      }
    };
    var connectionConfig = ConnectionConfig.custom().setConnectTimeout(3, TimeUnit.SECONDS)
        .setSocketTimeout(3, TimeUnit.SECONDS).build();
    var manager = PoolingHttpClientConnectionManagerBuilder.create()
        .setDnsResolver(pinned).setDefaultConnectionConfig(connectionConfig).build();
    var requestConfig = RequestConfig.custom().setResponseTimeout(5, TimeUnit.SECONDS)
        .setConnectionRequestTimeout(3, TimeUnit.SECONDS).build();
    try (var client = HttpClients.custom().setConnectionManager(manager)
        .setDefaultRequestConfig(requestConfig).disableRedirectHandling()
        .disableAutomaticRetries().disableCookieManagement().disableAuthCaching().build()) {
      return client.execute(new HttpHead(uri), response -> {
        int code = response.getCode();
        Header location = response.getFirstHeader("Location");
        return classify(uri, code, location == null ? null : location.getValue());
      });
    } catch (UnknownHostException exc) {
      return new Result(LinkStatus.SEM_RESPOSTA, true);
    } catch (IOException exc) {
      return new Result(LinkStatus.SEM_RESPOSTA, true);
    }
  }

  Result classify(URI uri, int code, String location) throws UnknownHostException {
    boolean safeRedirect = false;
    if (code >= 300 && code < 400) {
      if (location == null) {
        throw new IllegalArgumentException("Redirecionamento sem destino");
      }
      policy.validate(uri.resolve(location));
      safeRedirect = true;
    }
    return new Result(LinkClassification.fromHttp(code, safeRedirect), LinkClassification.isTransient(code));
  }
}
