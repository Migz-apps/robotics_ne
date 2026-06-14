#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Servo.h>

// --- Wi-Fi / MQTT (edit for your network) ---
const char* ssid = "EdNet";
const char* password = "Huawei@123";
// PC running Mosquitto on same Wi-Fi (use your PC LAN IP Ã¢â‚¬â€ not localhost)
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* client_id = "esp8266_team313";
const char* topic_movement = "vision/team313/movement";
const char* topic_heartbeat = "vision/team313/heartbeat";

// Servo on D5 (GPIO14) Ã¢â‚¬â€ SG90 horizontal pan
Servo myServo;
const int servoPin = D5;
int currentAngle = 90;
const int SERVO_STEP = 1;              // degrees per tracking nudge (was 3 Ã¢â‚¬â€ slower pan)
const unsigned long SERVO_MOVE_INTERVAL_MS = 120;  // min gap between tracking moves

// Search / re-acquisition
bool isSearching = true;
unsigned long lastSweepTime = 0;
unsigned long lastTrackMoveTime = 0;
const unsigned long SWEEP_INTERVAL_MS = 180;  // ms between scan steps (was 30)
int sweepStep = 1;                             // degrees per scan step (was 2)

unsigned long lastFaceDetectTime = 0;
const unsigned long FACE_TIMEOUT_MS = 800;

WiFiClient espClient;
PubSubClient client(espClient);

bool containsAny(const String& msg, const char* a, const char* b = nullptr, const char* c = nullptr, const char* d = nullptr) {
  if (msg.indexOf(a) >= 0) return true;
  if (b && msg.indexOf(b) >= 0) return true;
  if (c && msg.indexOf(c) >= 0) return true;
  if (d && msg.indexOf(d) >= 0) return true;
  return false;
}

bool jsonHasStatus(const String& msg, const char* status) {
  String tight = String("\"status\":\"") + status + "\"";
  String spaced = String("\"status\": \"") + status + "\"";
  return msg.indexOf(tight) >= 0 || msg.indexOf(spaced) >= 0;
}

bool jsonLockedTrue(const String& msg) {
  return msg.indexOf("\"locked\":true") >= 0 || msg.indexOf("\"locked\": true") >= 0;
}

bool isJsonPayload(const String& msg) {
  return msg.indexOf("\"status\"") >= 0;
}

void setup_wifi() {
  delay(10);
  Serial.println("\nConnecting to WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("ESP IP: ");
  Serial.println(WiFi.localIP());
}

void moveServo(int delta) {
  unsigned long now = millis();
  if (now - lastTrackMoveTime < SERVO_MOVE_INTERVAL_MS) {
    return;
  }
  lastTrackMoveTime = now;
  currentAngle += delta;
  if (currentAngle < 0) currentAngle = 0;
  if (currentAngle > 180) currentAngle = 180;
  myServo.write(currentAngle);
}

void enterSearchMode() {
  isSearching = true;
  lastSweepTime = 0;
  Serial.println("SCAN mode: horizontal sweep");
}

void onFaceTracked() {
  isSearching = false;
  lastFaceDetectTime = millis();
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  message.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  // JSON payloads from vision node Ã¢â‚¬â€ match status field only (avoids base64 false positives)
  if (isJsonPayload(message)) {
    if (jsonHasStatus(message, "MOVE_LEFT")) {
      onFaceTracked();
      moveServo(-SERVO_STEP);
      return;
    }
    if (jsonHasStatus(message, "MOVE_RIGHT")) {
      onFaceTracked();
      moveServo(SERVO_STEP);
      return;
    }
    if (jsonHasStatus(message, "SCAN") || jsonHasStatus(message, "NO_FACE") || jsonHasStatus(message, "OUT_OF_FRAME")) {
      enterSearchMode();
      return;
    }
    if (jsonHasStatus(message, "STOPPED") || jsonHasStatus(message, "CENTERED")) {
      if (jsonLockedTrue(message)) {
        onFaceTracked();
      } else {
        enterSearchMode();
      }
      return;
    }
    return;
  }

  // Plain-text fallback
  if (containsAny(message, "MOVE_LEFT", "MOVED_LEFT", "LEFT")) {
    onFaceTracked();
    moveServo(-SERVO_STEP);
    return;
  }
  if (containsAny(message, "MOVE_RIGHT", "MOVED_RIGHT", "RIGHT")) {
    onFaceTracked();
    moveServo(SERVO_STEP);
    return;
  }
  if (containsAny(message, "SCAN", "NO_FACE", "OUT_OF_FRAME")) {
    enterSearchMode();
    return;
  }
  if (containsAny(message, "STOPPED", "CENTERED")) {
    onFaceTracked();
    return;
  }
}

void reconnect() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost Ã¢â‚¬â€ reconnecting...");
    setup_wifi();
  }
  while (!client.connected()) {
    Serial.print("MQTT connect ");
    Serial.print(mqtt_server);
    Serial.print(":");
    Serial.print(mqtt_port);
    Serial.print("...");
    if (client.connect(client_id)) {
      Serial.println("ok");
      client.subscribe(topic_movement);
    } else {
      Serial.print("failed rc=");
      Serial.print(client.state());
      Serial.println(" retry in 5s");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  myServo.attach(servoPin);
  myServo.write(currentAngle);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  client.setBufferSize(512);
  Serial.print("MQTT broker: ");
  Serial.println(mqtt_server);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long now = millis();

  if (!isSearching && (now - lastFaceDetectTime > FACE_TIMEOUT_MS)) {
    Serial.println("Watchdog: face timeout -> SCAN");
    enterSearchMode();
  }

  if (isSearching && (now - lastSweepTime > SWEEP_INTERVAL_MS)) {
    lastSweepTime = now;
    currentAngle += sweepStep;
    if (currentAngle >= 180) {
      currentAngle = 180;
      sweepStep = -1;
    } else if (currentAngle <= 0) {
      currentAngle = 0;
      sweepStep = 1;
    }
    myServo.write(currentAngle);
  }

  static unsigned long lastHeartbeat = 0;
  if (now - lastHeartbeat > 5000) {
    lastHeartbeat = now;
    client.publish(topic_heartbeat, "{\"node\":\"esp8266\",\"status\":\"ONLINE\"}");
  }
}
