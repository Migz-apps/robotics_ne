const mqtt = require('mqtt');
const WebSocket = require('ws');
const http = require('http');
const fs = require('fs');
const path = require('path');

const CONFIG_PATH = path.join(__dirname, '..', 'config.json');
const LOGS_DIR = path.join(__dirname, '..', 'logs');

let config = {
    team_id: 'team313',
    mqtt_broker: 'broker.hivemq.com',
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
        if (!err) console.log(`Subscribed to topic: ${MQTT_TOPIC_VS}`);
        else console.error('MQTT Subscription Error:', err);
    });
});

mqttClient.on('message', (topic, message) => {
    const msgString = message.toString();
    console.log(`MQTT IN [${topic}]: ${msgString}`);
    try {
        broadcast(JSON.stringify({ type: 'MOVEMENT', payload: JSON.parse(msgString) }));
    } catch (err) {
        broadcast(msgString);
    }
});

const wss = new WebSocket.Server({ port: WS_PORT });
console.log(`WebSocket Server started on port ${WS_PORT}`);

function broadcast(data) {
    wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) client.send(data);
    });
}

function findLatestJsonl() {
    if (!fs.existsSync(LOGS_DIR)) return null;
    const files = fs
        .readdirSync(LOGS_DIR)
        .filter((f) => f.startsWith('operations_') && f.endsWith('.jsonl'))
        .map((f) => {
            const full = path.join(LOGS_DIR, f);
            return { full, mtime: fs.statSync(full).mtimeMs };
        })
        .sort((a, b) => b.mtime - a.mtime);
    return files.length ? files[0].full : null;
}

function readJsonlLines(filePath, maxLines = 80) {
    if (!filePath || !fs.existsSync(filePath)) return [];
    const content = fs.readFileSync(filePath, 'utf8');
    return content
        .trim()
        .split('\n')
        .filter(Boolean)
        .slice(-maxLines)
        .map((line) => {
            try {
                return JSON.parse(line);
            } catch {
                return null;
            }
        })
        .filter(Boolean);
}

let tailFile = null;
let tailOffset = 0;

function tailOperationalLogs() {
    const latest = findLatestJsonl();
    if (!latest) return;

    if (latest !== tailFile) {
        tailFile = latest;
        tailOffset = 0;
    }

    const stat = fs.statSync(tailFile);
    if (stat.size <= tailOffset) return;

    const content = fs.readFileSync(tailFile, 'utf8');
    const chunk = content.slice(tailOffset);
    tailOffset = content.length;

    const lines = chunk.split('\n').filter(Boolean);
    for (const line of lines) {
        try {
            const record = JSON.parse(line);
            broadcast(JSON.stringify({ type: 'LOG', record }));
        } catch {
            /* skip malformed line */
        }
    }
}

setInterval(tailOperationalLogs, 400);

wss.on('connection', (ws) => {
    console.log('New WebSocket Client connected');
    ws.send(JSON.stringify({ type: 'STATUS', message: 'Connected to Vision Backend' }));

    const latest = findLatestJsonl();
    if (latest) {
        const recent = readJsonlLines(latest, 60);
        ws.send(JSON.stringify({ type: 'LOG_BATCH', records: recent }));
    }

    ws.on('close', () => console.log('Client disconnected'));
});

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
        res.end(
            JSON.stringify({
                ws_port: WS_PORT,
                http_port: HTTP_PORT,
                team_id: config.team_id,
                mqtt_broker: config.mqtt_broker,
            })
        );
    } else if (req.url === '/api/logs/recent') {
        const latest = findLatestJsonl();
        const records = readJsonlLines(latest, 100);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ records, file: latest ? path.basename(latest) : null }));
    } else {
        res.writeHead(404);
        res.end('Not Found');
    }
});

server.listen(HTTP_PORT, () => {
    console.log(`HTTP Dashboard: http://localhost:${HTTP_PORT}`);
});
