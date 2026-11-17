package br.com.palaciomental.status_api.guardian;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.time.Duration;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/** Limita a espera por DNS e a quantidade de resoluções presas simultaneamente. */
public final class BoundedDnsResolver implements PublicDestinationPolicy.Resolver, AutoCloseable {
  private final ThreadPoolExecutor executor;
  private final Duration timeout;
  private final PublicDestinationPolicy.Resolver lookup;

  public BoundedDnsResolver(Duration timeout) {
    this(timeout, InetAddress::getAllByName);
  }

  BoundedDnsResolver(Duration timeout, PublicDestinationPolicy.Resolver lookup) {
    if (timeout == null || timeout.isZero() || timeout.isNegative()) {
      throw new IllegalArgumentException("Timeout DNS inválido");
    }
    this.timeout = timeout;
    this.lookup = lookup;
    this.executor = new ThreadPoolExecutor(4, 4, 0, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(100), runnable -> {
          Thread thread = new Thread(runnable, "guardiao-dns");
          thread.setDaemon(true);
          return thread;
        }, new ThreadPoolExecutor.AbortPolicy());
  }

  @Override
  public InetAddress[] resolve(String hostname) throws UnknownHostException {
    Future<InetAddress[]> future = null;
    try {
      future = executor.submit(() -> lookup.resolve(hostname));
      return future.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
    } catch (RejectedExecutionException | TimeoutException | ExecutionException exc) {
      throw new UnknownHostException("Resolução DNS indisponível");
    } catch (InterruptedException exc) {
      Thread.currentThread().interrupt();
      throw new UnknownHostException("Resolução DNS interrompida");
    } finally {
      if (future != null && !future.isDone()) {
        future.cancel(true);
        executor.remove((Runnable) future);
      }
    }
  }

  @Override
  public void close() {
    executor.shutdownNow();
  }
}
