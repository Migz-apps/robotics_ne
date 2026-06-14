// PlatformIO entry point — same firmware as vision_servo/vision_servo.ino
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Servo.h>

const char* ssid = "EdNet";
const char* password = "Huawei@123";
const char* mqtt_server = "10.11.72.240";
const int mqtt_port = 1883;
const char* client_id = "esp8266_team313";
const char* topic_movement = "vision/team313/movement";
const char* topic_heartbeat = "vision/team313/heartbeat";

Servo myServo;
const int servoPin = D5;
int currentAngle = 90;
const int SERVO_STEP = 1;
const unsigned long SERVO_MOVE_INTERVAL_MS = 120;
bool isSearching = true;
unsigned long lastSweepTime = 0;
unsigned long lastTrackMoveTime = 0;
const unsigned long SWEEP_INTERVAL_MS = 180;
int sweepStep = 1;
unsigned long lastFaceDetectTime = 0;
const unsigned long FACE_TIMEOUT_MS = 2000;

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
}

void moveServo(int delta) {
  unsigned long now = millis();
  if (now - lastTrackMoveTime < SERVO_MOVE_INTERVAL_MS) return;
  lastTrackMoveTime = now;
  currentAngle += delta;
  if (currentAngle < 0) currentAngle = 0;
  if (currentAngle > 180) currentAngle = 180;
  myServo.write(currentAngle);
}

void enterSearchMode() {
  isSearching = true;
}

void onFaceTracked() {
  isSearching = false;
  lastFaceDetectTime = millis();
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  message.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) message += (char)payload[i];

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
      }
      return;
    }
    return;
  }

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
  while (!client.connected()) {
    if (client.connect(client_id)) {
      client.subscribe(topic_movement);
    } else {
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
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();

  unsigned long now = millis();
  if (!isSearching && (now - lastFaceDetectTime > FACE_TIMEOUT_MS)) {
    enterSearchMode();
  }

  if (isSearching && (now - lastSweepTime > SWEEP_INTERVAL_MS)) {
    lastSweepTime = now;
    currentAngle += sweepStep;
    if (currentAngle >= 180) { currentAngle = 180; sweepStep = -1; }
    else if (currentAngle <= 0) { currentAngle = 0; sweepStep = 1; }
    myServo.write(currentAngle);
  }

  static unsigned long lastHeartbeat = 0;
  if (now - lastHeartbeat > 5000) {
    lastHeartbeat = now;
    client.publish(topic_heartbeat, "{\"node\":\"esp8266\",\"status\":\"ONLINE\"}");
  }
}
