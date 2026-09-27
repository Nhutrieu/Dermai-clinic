package com.dermai.patient;

import org.junit.jupiter.api.Test;
import java.nio.charset.StandardCharsets;
import static org.junit.jupiter.api.Assertions.*;

class ImageEncryptionConverterTest {
  private final ImageEncryptionConverter converter = new ImageEncryptionConverter();

  @Test
  void encryptsWithRandomIvAndDecryptsWithoutChangingTheImage() {
    byte[] image = "medical-image-bytes".getBytes(StandardCharsets.UTF_8);

    byte[] first = converter.convertToDatabaseColumn(image);
    byte[] second = converter.convertToDatabaseColumn(image);

    assertFalse(java.util.Arrays.equals(image, first));
    assertFalse(java.util.Arrays.equals(first, second));
    assertArrayEquals(image, converter.convertToEntityAttribute(first));
    assertArrayEquals(image, converter.convertToEntityAttribute(second));
  }

  @Test
  void readsLegacyPlaintextRowsForRollingMigration() {
    byte[] legacy = new byte[]{(byte) 0xff, (byte) 0xd8, (byte) 0xff};
    assertSame(legacy, converter.convertToEntityAttribute(legacy));
  }
}
