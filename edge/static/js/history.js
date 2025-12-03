/**
 * history.js - Visualización de datos históricos de la BD
 */

let selectedDevice = null;
let selectedSensor = null;
let currentChart = null;
let currentTimeRange = 24; // horas por defecto

// Inicialización al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    loadDevices();
    loadStats();
    setupEventListeners();
});

function setupEventListeners() {
    // Botones de rango temporal
    document.querySelectorAll('.time-range-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.time-range-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentTimeRange = parseInt(e.target.dataset.hours);
            if (selectedSensor) {
                loadSensorData(selectedSensor);
            }
        });
    });

    // Rango personalizado
    document.getElementById('apply-custom-range').addEventListener('click', () => {
        if (selectedSensor) {
            loadSensorDataCustomRange();
        }
    });
}

/**
 * Cargar lista de dispositivos desde la BD
 */
async function loadDevices() {
    try {
        const response = await fetch('/api/history/devices');
        const data = await response.json();
        
        const container = document.getElementById('devices-list');
        
        if (data.devices && data.devices.length > 0) {
            container.innerHTML = data.devices.map(device => {
                const caps = JSON.parse(device.capabilities);
                const capsStr = caps.join(', ');
                const lastSeen = new Date(device.last_seen).toLocaleString('es-ES');
                
                return `
                    <div class="card device-card mb-2" data-unit-id="${device.unit_id}" onclick="selectDevice(${device.unit_id})">
                        <div class="card-body p-2">
                            <h6 class="mb-1">
                                <span class="badge bg-primary">Unit ${device.unit_id}</span>
                                ${device.alias || 'Device ' + device.unit_id}
                            </h6>
                            <small class="text-muted">
                                📡 ${capsStr}<br>
                                🕐 ${lastSeen}
                            </small>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            container.innerHTML = `
                <div class="alert alert-warning">
                    <small>No hay dispositivos registrados en la BD.</small>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading devices:', error);
        document.getElementById('devices-list').innerHTML = `
            <div class="alert alert-danger">
                <small>Error al cargar dispositivos: ${error.message}</small>
            </div>
        `;
    }
}

/**
 * Cargar estadísticas de la BD
 */
async function loadStats() {
    try {
        const response = await fetch('/api/history/stats');
        const stats = await response.json();
        
        document.getElementById('stat-devices').textContent = stats.device_count || 0;
        document.getElementById('stat-sensors').textContent = stats.sensor_count || 0;
        document.getElementById('stat-measurements').textContent = (stats.measurement_count || 0).toLocaleString();
        document.getElementById('stat-size').textContent = (stats.db_size_mb || 0).toFixed(2) + ' MB';
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

/**
 * Seleccionar un dispositivo
 */
async function selectDevice(unitId) {
    selectedDevice = unitId;
    selectedSensor = null;
    
    // Highlight del dispositivo seleccionado
    document.querySelectorAll('.device-card').forEach(card => {
        card.classList.remove('selected');
    });
    document.querySelector(`[data-unit-id="${unitId}"]`).classList.add('selected');
    
    // Ocultar mensaje inicial
    document.getElementById('no-selection').style.display = 'none';
    
    // Cargar sensores del dispositivo
    try {
        const response = await fetch(`/api/history/sensors/${unitId}`);
        const data = await response.json();
        
        // Mostrar info del dispositivo
        document.getElementById('device-info').style.display = 'block';
        document.getElementById('selected-device-name').textContent = data.device.alias || `Unit ${unitId}`;
        const caps = JSON.parse(data.device.capabilities);
        document.getElementById('selected-device-caps').textContent = caps.join(', ');
        
        // Mostrar sensores
        const sensorsContainer = document.getElementById('sensors-container');
        const sensorsBadges = document.getElementById('sensors-badges');
        
        if (data.sensors && data.sensors.length > 0) {
            sensorsContainer.style.display = 'block';
            sensorsBadges.innerHTML = data.sensors.map(sensor => {
                const typeColors = {
                    'tilt': 'warning',
                    'temperature': 'danger',
                    'acceleration': 'info',
                    'gyroscope': 'secondary',
                    'wind': 'success',
                    'load': 'primary'
                };
                const color = typeColors[sensor.type] || 'secondary';
                
                return `
                    <span class="badge bg-${color} sensor-badge" 
                          data-sensor-id="${sensor.sensor_id}"
                          onclick="selectSensor('${sensor.sensor_id}')">
                        ${sensor.sensor_id}
                    </span>
                `;
            }).join('');
            
            // Mostrar controles de tiempo
            document.getElementById('time-controls').style.display = 'block';
        } else {
            sensorsBadges.innerHTML = '<div class="alert alert-info">No hay sensores para este dispositivo.</div>';
        }
        
    } catch (error) {
        console.error('Error loading device sensors:', error);
    }
}

/**
 * Seleccionar un sensor para visualizar
 */
function selectSensor(sensorId) {
    selectedSensor = sensorId;
    
    // Highlight del sensor seleccionado
    document.querySelectorAll('.sensor-badge').forEach(badge => {
        badge.classList.remove('active');
    });
    document.querySelector(`[data-sensor-id="${sensorId}"]`).classList.add('active');
    
    // Cargar datos del sensor
    loadSensorData(sensorId);
}

/**
 * Cargar datos históricos de un sensor
 */
async function loadSensorData(sensorId) {
    try {
        const response = await fetch(`/api/history/data/${sensorId}?hours=${currentTimeRange}`);
        const data = await response.json();
        
        if (data.measurements && data.measurements.length > 0) {
            // Mostrar estadísticas
            document.getElementById('sensor-stats').style.display = 'block';
            document.getElementById('stat-min').textContent = `${data.stats.min.toFixed(2)} ${data.unit}`;
            document.getElementById('stat-max').textContent = `${data.stats.max.toFixed(2)} ${data.unit}`;
            document.getElementById('stat-avg').textContent = `${data.stats.avg.toFixed(2)} ${data.unit}`;
            document.getElementById('stat-count').textContent = data.stats.count.toLocaleString();
            
            // Renderizar gráfico
            renderChart(data.measurements, sensorId, data.unit);
            
            // Renderizar tabla
            renderTable(data.measurements);
            
            document.getElementById('chart-container').style.display = 'block';
            document.getElementById('data-table-card').style.display = 'block';
        } else {
            alert('No hay datos disponibles para este sensor en el rango seleccionado.');
        }
    } catch (error) {
        console.error('Error loading sensor data:', error);
        alert('Error al cargar datos del sensor: ' + error.message);
    }
}

/**
 * Cargar datos con rango personalizado
 */
async function loadSensorDataCustomRange() {
    const startInput = document.getElementById('custom-start').value;
    const endInput = document.getElementById('custom-end').value;
    
    if (!startInput || !endInput) {
        alert('Por favor, selecciona un rango de fechas válido.');
        return;
    }
    
    try {
        const start = new Date(startInput).toISOString();
        const end = new Date(endInput).toISOString();
        
        const response = await fetch(`/api/history/data/${selectedSensor}?start=${start}&end=${end}`);
        const data = await response.json();
        
        if (data.measurements && data.measurements.length > 0) {
            document.getElementById('sensor-stats').style.display = 'block';
            document.getElementById('stat-min').textContent = `${data.stats.min.toFixed(2)} ${data.unit}`;
            document.getElementById('stat-max').textContent = `${data.stats.max.toFixed(2)} ${data.unit}`;
            document.getElementById('stat-avg').textContent = `${data.stats.avg.toFixed(2)} ${data.unit}`;
            document.getElementById('stat-count').textContent = data.stats.count.toLocaleString();
            
            renderChart(data.measurements, selectedSensor, data.unit);
            renderTable(data.measurements);
        } else {
            alert('No hay datos en el rango seleccionado.');
        }
    } catch (error) {
        console.error('Error loading custom range data:', error);
        alert('Error: ' + error.message);
    }
}

/**
 * Renderizar gráfico con Chart.js
 */
function renderChart(measurements, sensorId, unit) {
    const ctx = document.getElementById('historyChart').getContext('2d');
    
    // Destruir gráfico anterior si existe
    if (currentChart) {
        currentChart.destroy();
    }
    
    // Preparar datos
    const labels = measurements.map(m => new Date(m.timestamp).toLocaleString('es-ES'));
    const values = measurements.map(m => m.value);
    
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: sensorId + ' (' + unit + ')',
                data: values,
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Tiempo'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: `Valor (${unit})`
                    }
                }
            }
        }
    });
}

/**
 * Renderizar tabla de datos
 */
function renderTable(measurements) {
    const tbody = document.getElementById('data-table-body');
    
    tbody.innerHTML = measurements.map(m => {
        const timestamp = new Date(m.timestamp).toLocaleString('es-ES');
        const qualityClass = m.quality === 'OK' ? 'text-success' : 
                            m.quality === 'WARN' ? 'text-warning' : 'text-danger';
        
        return `
            <tr>
                <td><small>${timestamp}</small></td>
                <td><small>${m.sensor_id}</small></td>
                <td><strong>${m.value.toFixed(2)}</strong></td>
                <td><small>${m.unit}</small></td>
                <td><span class="badge bg-${qualityClass === 'text-success' ? 'success' : qualityClass === 'text-warning' ? 'warning' : 'danger'}">${m.quality}</span></td>
            </tr>
        `;
    }).join('');
}
