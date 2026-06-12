const mqtt = require('mqtt');
const WebSocket = require('ws');
const http = require('http');
const fs = require('fs');
const path = require('path');

// Load shared config.json from project root
const CONFIG_PATH = path.join(__dirname, '..', 'config.json');
let config = {
    team_id: 'team313',
    mqtt_broker: '157.173.101.159',
    mqtt_port: 1883,
    ws_port: 9002,
    http_port: 8080,
};
if (fs.existsSync(CONFIG_PATH)) {
    config = { ...config, ...JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8')) };
}

const MQTT_BROKER = `mqtt://${config.mqtt_broker}:${config.mqtt_port}`;
const MQTT_TOPIC_VS = `vision/${config.team_id}/movement`;
const WS_PORT = config.ws_port;
const HTTP_PORT = config.http_port;

console.log(`Connecting to MQTT Broker: ${MQTT_BROKER}...`);
const mqttClient = mqtt.connect(MQTT_BROKER);

mqttClient.on('connect', () => {
    console.log('Connected to MQTT Broker.');
    mqttClient.subscribe(MQTT_TOPIC_VS, (err) => {
        if (!err) {
            console.log(`Subscribed to topic: ${MQTT_TOPIC_VS}`);
        } else {
            console.error('MQTT Subscription Error:', err);
        }
    });
});

mqttClient.on('message', (topic, message) => {
    const msgString = message.toString();
    console.log(`MQTT IN [${topic}]: ${msgString}`);
    broadcast(msgString);
});

const wss = new WebSocket.Server({ port: WS_PORT });
console.log(`WebSocket Server started on port ${WS_PORT}`);

wss.on('connection', (ws) => {
    console.log('New WebSocket Client connected');
    ws.send(JSON.stringify({ type: 'STATUS', message: 'Connected to Vision Backend' }));
    ws.on('close', () => console.log('Client disconnected'));
});

function broadcast(data) {
    wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(data);
        }
    });
}

const server = http.createServer((req, res) => {
    if (req.url === '/' || req.url === '/index.html') {
        fs.readFile(path.join(__dirname, '../dashboard/index.html'), (err, data) => {
            if (err) {
                res.writeHead(500);
                res.end('Error loading dashboard');
                return;
            }
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(data);
        });
    } else if (req.url === '/config.json') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ws_port: WS_PORT, http_port: HTTP_PORT, team_id: config.team_id }));
    } else {
        res.writeHead(404);
        res.end('Not Found');
    }
});

server.listen(HTTP_PORT, () => {
    console.log(`HTTP Dashboard: http://localhost:${HTTP_PORT}`);
});
