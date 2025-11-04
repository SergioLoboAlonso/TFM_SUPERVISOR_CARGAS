/**
 * polling.js - Gestión de telemetría en tiempo real con WebSocket
 */

// Estado global
let socket = null;
let pollingActive = false;
let monitoredDevices = {};

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    initWebSocket();
    loadDevices();
    attachEventHandlers();
});

// ============================================================================
// WebSocket
// ============================================================================

function initWebSocket() {
    socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    
    socket.on('connect', function() {
        logEvent('✅ WebSocket conectado', 'success');
    });
    
    socket.on('disconnect', function() {
        logEvent('❌ WebSocket desconectado', 'danger');
    });
    
    socket.on('telemetry_update', function(data) {
        handleTelemetryUpdate(data);
    });
    
    socket.on('device_offline', function(data) {
        logEvent(`⚠️ Dispositivo ${data.unit_id} OFFLINE`, 'warning');
        markDeviceOffline(data.unit_id);
    });
}

// ============================================================================
// Carga inicial de dispositivos
// ============================================================================

function loadDevices() {
    fetch('/api/devices')
        .then(response => response.json())
        .then(devices => {
            const select = document.getElementById('deviceSelect');
            select.innerHTML = '';
            
            if (devices.length === 0) {
                select.innerHTML = '<option disabled>No hay dispositivos descubiertos</option>';
                return;
            }
            
            devices.forEach(dev => {
                const option = document.createElement('option');
                option.value = dev.unit_id;
                option.textContent = `[${dev.unit_id}] ${dev.alias || 'Sin alias'} - ${dev.product_id}`;
                select.appendChild(option);
            });
            
            logEvent(`📥 ${devices.length} dispositivo(s) cargado(s)`, 'info');
        })
        .catch(err => {
            console.error('Error al cargar dispositivos:', err);
            logEvent(`❌ Error: ${err.message}`, 'danger');
        });
}

// ============================================================================
// Event Handlers
// ============================================================================

function attachEventHandlers() {
    document.getElementById('btnStart').addEventListener('click', startPolling);
    document.getElementById('btnStop').addEventListener('click', stopPolling);
    document.getElementById('btnClearLog').addEventListener('click', clearLog);
}

function startPolling() {
    const select = document.getElementById('deviceSelect');
    const selectedOptions = Array.from(select.selectedOptions);
    
    if (selectedOptions.length === 0) {
        alert('Selecciona al menos un dispositivo');
        return;
    }
    
    const unitIds = selectedOptions.map(opt => parseInt(opt.value));
    const interval = parseFloat(document.getElementById('intervalInput').value);
    
    fetch('/api/polling/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            unit_ids: unitIds,
            interval_sec: interval
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'started') {
            pollingActive = true;
            updatePollingUI(true);
            logEvent(`▶️ Polling iniciado: ${unitIds.join(', ')} @ ${interval}s`, 'success');
            
            // Crear tarjetas de telemetría
            createTelemetryCards(unitIds);
        } else {
            alert('Error al iniciar polling: ' + data.message);
        }
    })
    .catch(err => {
        console.error('Error:', err);
        logEvent(`❌ Error: ${err.message}`, 'danger');
    });
}

function stopPolling() {
    fetch('/api/polling/stop', {method: 'POST'})
        .then(response => response.json())
        .then(data => {
            if (data.status === 'stopped') {
                pollingActive = false;
                updatePollingUI(false);
                logEvent('⏹️ Polling detenido', 'warning');
                clearTelemetryCards();
            }
        })
        .catch(err => {
            console.error('Error:', err);
            logEvent(`❌ Error: ${err.message}`, 'danger');
        });
}

// ============================================================================
// UI Updates
// ============================================================================

function updatePollingUI(active) {
    const btnStart = document.getElementById('btnStart');
    const btnStop = document.getElementById('btnStop');
    const statusText = document.getElementById('statusText');
    const statusDiv = document.getElementById('pollingStatus');
    
    if (active) {
        btnStart.disabled = true;
        btnStop.disabled = false;
        statusText.textContent = 'Activo';
        statusDiv.className = 'alert alert-success mt-3';
    } else {
        btnStart.disabled = false;
        btnStop.disabled = true;
        statusText.textContent = 'Detenido';
        statusDiv.className = 'alert alert-secondary mt-3';
    }
}

function createTelemetryCards(unitIds) {
    const container = document.getElementById('telemetryCards');
    container.innerHTML = '';
    
    unitIds.forEach(unitId => {
        const cardHtml = `
            <div class="col-lg-6 col-xl-4 mb-3" id="card-${unitId}">
                <div class="card border-primary">
                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                        <strong>📟 Unit ID ${unitId}</strong>
                        <span class="badge bg-success" id="status-${unitId}">ONLINE</span>
                    </div>
                    <div class="card-body">
                        <div class="row g-2">
                            <!-- Ángulos -->
                            <div class="col-6">
                                <div class="border rounded p-2 text-center">
                                    <small class="text-muted d-block">Ángulo X</small>
                                    <strong id="angle-x-${unitId}">--</strong>°
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="border rounded p-2 text-center">
                                    <small class="text-muted d-block">Ángulo Y</small>
                                    <strong id="angle-y-${unitId}">--</strong>°
                                </div>
                            </div>
                            
                            <!-- Temperatura -->
                            <div class="col-12">
                                <div class="border rounded p-2 text-center">
                                    <small class="text-muted d-block">🌡️ Temperatura</small>
                                    <strong id="temp-${unitId}">--</strong>°C
                                </div>
                            </div>
                            
                            <!-- Carga -->
                            <div class="col-12">
                                <div class="border rounded p-2 text-center">
                                    <small class="text-muted d-block">⚖️ Carga</small>
                                    <strong id="load-${unitId}">--</strong> kg
                                </div>
                            </div>
                            
                            <!-- Acelerómetro -->
                            <div class="col-12">
                                <small class="text-muted">Aceleración (g)</small>
                                <div class="d-flex justify-content-between">
                                    <span>X: <strong id="accel-x-${unitId}">--</strong></span>
                                    <span>Y: <strong id="accel-y-${unitId}">--</strong></span>
                                    <span>Z: <strong id="accel-z-${unitId}">--</strong></span>
                                </div>
                            </div>
                            
                            <!-- Giroscopio -->
                            <div class="col-12">
                                <small class="text-muted">Giroscopio (°/s)</small>
                                <div class="d-flex justify-content-between">
                                    <span>X: <strong id="gyro-x-${unitId}">--</strong></span>
                                    <span>Y: <strong id="gyro-y-${unitId}">--</strong></span>
                                    <span>Z: <strong id="gyro-z-${unitId}">--</strong></span>
                                </div>
                            </div>
                            
                            <!-- Sample counter -->
                            <div class="col-12 mt-2">
                                <small class="text-muted">Sample #<span id="sample-${unitId}">0</span> | 
                                <span id="timestamp-${unitId}">--:--:--</span></small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', cardHtml);
        monitoredDevices[unitId] = {online: true, lastUpdate: Date.now()};
    });
}

function clearTelemetryCards() {
    document.getElementById('telemetryCards').innerHTML = `
        <div class="col-12 text-center text-muted py-5">
            <h5>Polling detenido</h5>
        </div>
    `;
    monitoredDevices = {};
}

function handleTelemetryUpdate(data) {
    const unitId = data.unit_id;
    
    if (!monitoredDevices[unitId]) return;
    
    console.log(`📊 Telemetry update for unit ${unitId}:`, data);
    
    // Validar que tenemos telemetría
    if (!data.telemetry) {
        console.error(`❌ No telemetry data for unit ${unitId}`, data);
        logEvent(`⚠️ Unit ${unitId}: Sin datos de telemetría`, 'warning');
        return;
    }
    
    // Actualizar badge de estado
    const statusBadge = document.getElementById(`status-${unitId}`);
    if (statusBadge) {
        if (data.status === 'error') {
            statusBadge.textContent = 'ERROR';
            statusBadge.className = 'badge bg-danger';
            logEvent(`❌ Unit ${unitId}: ${data.error || 'Unknown error'}`, 'danger');
            return;
        }
        statusBadge.textContent = 'ONLINE';
        statusBadge.className = 'badge bg-success';
    }
    
    const tel = data.telemetry;
    
    // Actualizar valores (con validación)
    if (tel.angle_x_deg !== undefined) updateField(`angle-x-${unitId}`, tel.angle_x_deg.toFixed(1));
    if (tel.angle_y_deg !== undefined) updateField(`angle-y-${unitId}`, tel.angle_y_deg.toFixed(1));
    if (tel.temperature_c !== undefined) updateField(`temp-${unitId}`, tel.temperature_c.toFixed(1));
    if (tel.load_kg !== undefined) updateField(`load-${unitId}`, tel.load_kg.toFixed(2));
    
    if (tel.acceleration) {
        if (tel.acceleration.x_g !== undefined) updateField(`accel-x-${unitId}`, tel.acceleration.x_g.toFixed(3));
        if (tel.acceleration.y_g !== undefined) updateField(`accel-y-${unitId}`, tel.acceleration.y_g.toFixed(3));
        if (tel.acceleration.z_g !== undefined) updateField(`accel-z-${unitId}`, tel.acceleration.z_g.toFixed(3));
    }
    
    if (tel.gyroscope) {
        if (tel.gyroscope.x_dps !== undefined) updateField(`gyro-x-${unitId}`, tel.gyroscope.x_dps.toFixed(1));
        if (tel.gyroscope.y_dps !== undefined) updateField(`gyro-y-${unitId}`, tel.gyroscope.y_dps.toFixed(1));
        if (tel.gyroscope.z_dps !== undefined) updateField(`gyro-z-${unitId}`, tel.gyroscope.z_dps.toFixed(1));
    }
    
    if (tel.sample_count !== undefined) updateField(`sample-${unitId}`, tel.sample_count);
    
    // Timestamp
    if (data.timestamp) {
        const ts = new Date(data.timestamp);
        updateField(`timestamp-${unitId}`, ts.toLocaleTimeString('es-ES'));
    }
    
    monitoredDevices[unitId].lastUpdate = Date.now();
}

function markDeviceOffline(unitId) {
    const statusBadge = document.getElementById(`status-${unitId}`);
    if (statusBadge) {
        statusBadge.textContent = 'OFFLINE';
        statusBadge.className = 'badge bg-danger';
    }
}

function updateField(elementId, value) {
    const elem = document.getElementById(elementId);
    if (elem) {
        elem.textContent = value;
    }
}

// ============================================================================
// Log de Eventos
// ============================================================================

function logEvent(message, type = 'info') {
    const logDiv = document.getElementById('eventLog');
    const timestamp = new Date().toLocaleTimeString('es-ES');
    
    const colorMap = {
        success: '#28a745',
        danger: '#dc3545',
        warning: '#ffc107',
        info: '#17a2b8'
    };
    
    const color = colorMap[type] || '#6c757d';
    
    const entry = document.createElement('div');
    entry.style.color = color;
    entry.textContent = `[${timestamp}] ${message}`;
    
    logDiv.insertBefore(entry, logDiv.firstChild);
    
    // Limitar a 50 entradas
    while (logDiv.children.length > 50) {
        logDiv.removeChild(logDiv.lastChild);
    }
}

function clearLog() {
    document.getElementById('eventLog').innerHTML = '<div class="text-muted">Log limpiado</div>';
}
