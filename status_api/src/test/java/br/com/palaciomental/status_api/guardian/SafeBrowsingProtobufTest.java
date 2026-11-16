package br.com.palaciomental.status_api.guardian;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import com.google.protobuf.CodedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class SafeBrowsingProtobufTest {
  @FunctionalInterface interface Writer { void write(CodedOutputStream output) throws IOException; }
  private static byte[] message(Writer writer) throws IOException {
    var bytes = new ByteArrayOutputStream();
    var out = CodedOutputStream.newInstance(bytes);
    writer.write(out);
    out.flush();
    return bytes.toByteArray();
  }

  @Test
  void interpretaRespostaRealSemCorrespondencias() throws Exception {
    var reply = SafeBrowsingProtobuf.parse(new byte[]{0x12, 0x03, 0x08, (byte) 0x96, 0x02});
    assertThat(reply.matches()).isEmpty();
    assertThat(reply.cacheDuration()).isEqualTo(Duration.ofSeconds(278));
  }

  @Test
  void interpretaAmeacaEAtributosEmpacotados() throws Exception {
    byte[] detail = message(out -> {
      out.writeEnum(1, 1);
      out.writeByteArray(2, new byte[]{1, 2});
    });
    byte[] match = message(out -> {
      out.writeByteArray(1, new byte[32]);
      out.writeByteArray(2, detail);
    });
    byte[] duration = message(out -> out.writeInt64(1, 300));
    byte[] response = message(out -> {
      out.writeByteArray(1, match);
      out.writeByteArray(2, duration);
    });
    var reply = SafeBrowsingProtobuf.parse(response);
    assertThat(reply.matches()).hasSize(1);
    assertThat(reply.matches().getFirst().details().getFirst().threatType()).isEqualTo("MALWARE");
    assertThat(reply.matches().getFirst().details().getFirst().attributes()).containsExactly("CANARY", "FRAME_ONLY");
  }

  @Test
  void respostaTruncadaOuSemValidadeNaoViraResultadoSeguro() {
    assertThatThrownBy(() -> SafeBrowsingProtobuf.parse(new byte[]{0x12, 0x03, 0x08})).isInstanceOf(IOException.class);
    assertThatThrownBy(() -> SafeBrowsingProtobuf.parse(new byte[0])).isInstanceOf(IOException.class);
  }
}
