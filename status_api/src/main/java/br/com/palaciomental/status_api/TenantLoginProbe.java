package br.com.palaciomental.status_api;

import br.com.palaciomental.status_api.guardian.BoundedDnsResolver;
import br.com.palaciomental.status_api.guardian.PublicDestinationPolicy;
import java.net.InetAddress;
import java.net.URI;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.TimeUnit;
import org.apache.hc.client5.http.DnsResolver;
import org.apache.hc.client5.http.classic.methods.HttpGet;
import org.apache.hc.client5.http.config.ConnectionConfig;
import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.client5.http.impl.io.PoolingHttpClientConnectionManagerBuilder;

/** Consulta somente endereços públicos, fixando o DNS e limitando o corpo recebido. */
final class TenantLoginProbe {
  private TenantLoginProbe() {}

  static boolean check(URI uri, String marker) {
    try (var resolver = new BoundedDnsResolver(Duration.ofSeconds(2))) {
      var destination = new PublicDestinationPolicy(resolver).validate(uri);
      DnsResolver pinned = new DnsResolver() {
        public InetAddress[] resolve(String hostname) throws UnknownHostException {
          if (!hostname.equalsIgnoreCase(uri.getHost())) throw new UnknownHostException("Destino inválido");
          return destination.addresses().toArray(InetAddress[]::new);
        }
        public String resolveCanonicalHostname(String hostname) throws UnknownHostException {
          resolve(hostname);
          return hostname;
        }
      };
      var manager = PoolingHttpClientConnectionManagerBuilder.create().setDnsResolver(pinned)
          .setDefaultConnectionConfig(ConnectionConfig.custom().setConnectTimeout(3, TimeUnit.SECONDS)
              .setSocketTimeout(3, TimeUnit.SECONDS).build()).build();
      try (var client = HttpClients.custom().setConnectionManager(manager)
          .setDefaultRequestConfig(RequestConfig.custom().setResponseTimeout(5, TimeUnit.SECONDS)
              .setConnectionRequestTimeout(3, TimeUnit.SECONDS).build())
          .disableRedirectHandling().disableAutomaticRetries().disableCookieManagement().disableAuthCaching().build()) {
        return client.execute(new HttpGet(uri), response -> {
          if (response.getCode() != 200 || response.getEntity() == null) return false;
          try (var body = response.getEntity().getContent()) {
            return new String(body.readNBytes(262144), StandardCharsets.UTF_8).contains(marker);
          }
        });
      }
    } catch (Exception exception) {
      return false;
    }
  }
}
