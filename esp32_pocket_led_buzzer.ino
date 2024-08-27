#include <WiFi.h>
#include <WebServer.h>
#include <U8g2lib.h>
#include <ArduinoJson.h>

// Replace with your network credentials
const char* ssid = "ground_wifi";
const char* password = "groundwifi";

// Create an instance of the WebServer on port 80
WebServer server(80);

// Define the GPIO pins for the buzzer and LED
const int buzzerPin = 13;
const int ledPin = 2;

// Initialize the OLED display using U8g2 library
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/ U8X8_PIN_NONE);  // Adjust if needed

int totalFaces = 0;

// Function to draw text with a margin/padding from the left
void drawPaddedText(const char* text, int y, int padding) {
  int xPos = padding;  // Add a margin on the left side
  u8g2.drawStr(xPos, y, text);
}

void setup() {
  Serial.begin(115200);
  u8g2.begin();

  // Display initial message on OLED with padding
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_ncenB08_tr);
  drawPaddedText("Waiting for Request...", 12, 5);  // 5-pixel padding
  u8g2.sendBuffer();

  pinMode(buzzerPin, OUTPUT);
  pinMode(ledPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);
  digitalWrite(ledPin, LOW);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to Wi-Fi. IP address: ");
  Serial.println(WiFi.localIP());

  server.on("/on", HTTP_ANY, []() {
    Serial.println("Received /on request");
    String message = "Buzzer and LED are ON";
    digitalWrite(buzzerPin, HIGH);
    digitalWrite(ledPin, HIGH);

    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_ncenB08_tr);
    drawPaddedText("Status: Buzzer ON", 12, 5);  // 5-pixel padding
    drawPaddedText(("Total Faces: " + String(totalFaces)).c_str(), 30, 5);  // 5-pixel padding
    u8g2.sendBuffer();

    server.send(200, "text/plain", message);
  });

  server.on("/off", HTTP_ANY, []() {
    Serial.println("Received /off request");
    String message = "Buzzer and LED are OFF";
    digitalWrite(buzzerPin, LOW);
    digitalWrite(ledPin, LOW);

    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_ncenB08_tr);
    drawPaddedText("Status: Buzzer OFF", 12, 5);  // 5-pixel padding
    drawPaddedText(("Total Faces: " + String(totalFaces)).c_str(), 30, 5);  // 5-pixel padding
    u8g2.sendBuffer();

    server.send(200, "text/plain", message);
  });

  server.on("/update_count", HTTP_POST, []() {
    if (server.hasArg("plain")) {
      String message = "Received total_faces: ";
      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, server.arg("plain"));

      if (!error) {
        totalFaces = doc["total_faces"];
        message += totalFaces;
        Serial.println(message);

        u8g2.clearBuffer();
        u8g2.setFont(u8g2_font_ncenB08_tr);
        drawPaddedText("Total Faces:", 12, 5);  // 5-pixel padding

        String totalFacesStr = String(totalFaces);
        u8g2.setFont(u8g2_font_fur30_tr);
        int16_t width = u8g2.getStrWidth(totalFacesStr.c_str());
        int16_t xPos = (u8g2.getDisplayWidth() - width) / 2;
        u8g2.drawStr(xPos, 50, totalFacesStr.c_str());
        u8g2.sendBuffer();

        server.send(200, "text/plain", message);
      } else {
        Serial.println("Failed to parse JSON.");
        server.send(400, "text/plain", "Failed to parse JSON");
      }
    } else {
      server.send(400, "text/plain", "Invalid Request");
    }
  });

  server.begin();
}

void loop() {
  server.handleClient();
}
