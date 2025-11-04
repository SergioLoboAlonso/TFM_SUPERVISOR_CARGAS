/**
 * config.js - Gestión de discovery, alias, identify
 */

let discoveredDevices = [];

document.addEventListener('DOMContentLoaded', function() {
    attachEventHandlers();
    loadExistingDevices();
});

function attachEventHandlers() {
    document.getElementById('btnDiscover').addEventListener('click', runDiscovery);
}

// ============================================================================
// Discovery
// ============================================================================

function runDiscovery() {
    const minId = parseInt(document.getElementById('unitIdMin').value);
    const maxId = parseInt(document.getElementById('unitIdMax').value);
    
    if (minId < 1 || maxId > 247 || minId > maxId) {
        alert('Rango de Unit ID inválido (1-247)');
        return;
    }
    
    const btn = document.getElementById('btnDiscover');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Descubriendo...';
    
    updateStatus(`🔍 Buscando dispositivos ${minId}..${maxId}...`, 'info');
    
    fetch('/api/discover', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({unit_id_min: minId, unit_id_max: maxId})
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'completed') {
            discoveredDevices = data.devices_found;
            updateStatus(`✅ Discovery completado: ${discoveredDevices.length} dispositivo(s) encontrado(s)`, 'success');
            renderDeviceTable(discoveredDevices);
        } else {
            updateStatus('❌ Error en discovery: ' + data.message, 'danger');
        }
    })
    .catch(err => {
        console.error('Error:', err);
        updateStatus('❌ Error: ' + err.message, 'danger');
    })
    .finally(() => {
        btn.disabled = false;
        btn.textContent = '🔍 Descubrir Dispositivos';
    });
}

function loadExistingDevices() {
    fetch('/api/devices')
        .then(response => response.json())
        .then(devices => {
            if (devices.length > 0) {
                discoveredDevices = devices;
                renderDeviceTable(devices);
            }
        })
        .catch(err => console.error('Error al cargar dispositivos:', err));
}

// ============================================================================
// Tabla de Dispositivos
// ============================================================================

function renderDeviceTable(devices) {
    const tbody = document.getElementById('deviceTableBody');
    tbody.innerHTML = '';
    
    if (devices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No hay dispositivos descubiertos</td></tr>';
        return;
    }
    
    devices.forEach(dev => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${dev.unit_id}</strong></td>
            <td>${dev.vendor_id}</td>
            <td>${dev.product_id}</td>
            <td>
                <input type="text" class="form-control form-control-sm" 
                       id="alias-${dev.unit_id}" 
                       value="${dev.alias || ''}" 
                       maxlength="64" 
                       placeholder="Sin alias">
            </td>
            <td>
                <span class="badge ${dev.status === 'online' ? 'bg-success' : 'bg-secondary'}">
                    ${dev.status || 'unknown'}
                </span>
            </td>
            <td>
                <button class="btn btn-primary btn-sm" onclick="identifyDevice(${dev.unit_id})">
                    💡 Identificar
                </button>
                <button class="btn btn-success btn-sm" onclick="saveAlias(${dev.unit_id})">
                    💾 Guardar Alias
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// ============================================================================
// Comandos
// ============================================================================

function identifyDevice(unitId) {
    updateStatus(`💡 Activando LED en dispositivo ${unitId}...`, 'info');
    
    fetch(`/api/devices/${unitId}/identify`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({duration_sec: 10})
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            updateStatus(`✅ LED activado en dispositivo ${unitId} por 10 segundos`, 'success');
        } else {
            updateStatus(`❌ Error: ${data.message}`, 'danger');
        }
    })
    .catch(err => {
        console.error('Error:', err);
        updateStatus('❌ Error: ' + err.message, 'danger');
    });
}

function saveAlias(unitId) {
    const input = document.getElementById(`alias-${unitId}`);
    const alias = input.value.trim();
    
    if (!alias) {
        alert('El alias no puede estar vacío');
        return;
    }
    
    updateStatus(`💾 Guardando alias "${alias}" en dispositivo ${unitId}...`, 'info');
    
    fetch(`/api/devices/${unitId}/alias`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({alias: alias})
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            updateStatus(`✅ Alias guardado en EEPROM del dispositivo ${unitId}`, 'success');
        } else {
            updateStatus(`❌ Error: ${data.message}`, 'danger');
        }
    })
    .catch(err => {
        console.error('Error:', err);
        updateStatus('❌ Error: ' + err.message, 'danger');
    });
}

// ============================================================================
// UI Helpers
// ============================================================================

function updateStatus(message, type = 'info') {
    const statusDiv = document.getElementById('statusMessage');
    const alertClass = `alert-${type}`;
    
    statusDiv.className = `alert ${alertClass}`;
    statusDiv.textContent = message;
    statusDiv.style.display = 'block';
    
    // Auto-ocultar después de 5 segundos
    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 5000);
}
