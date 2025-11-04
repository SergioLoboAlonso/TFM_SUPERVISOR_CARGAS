/**
 * dashboard.js - Vista principal con información del adaptador
 */

document.addEventListener('DOMContentLoaded', function() {
    loadAdapterInfo();
    // Actualizar cada 5 segundos
    setInterval(loadAdapterInfo, 5000);
});

function loadAdapterInfo() {
    fetch('/api/adapter')
        .then(response => response.json())
        .then(data => {
            updateAdapterInfo(data);
        })
        .catch(err => {
            console.error('Error al cargar info del adaptador:', err);
            showError('No se pudo conectar con el servidor');
        });
}

function updateAdapterInfo(data) {
    // Puerto y baudrate
    document.getElementById('adapterPort').textContent = data.port || 'N/A';
    document.getElementById('adapterBaudrate').textContent = data.baudrate || 'N/A';
    
    // Estado
    const statusElem = document.getElementById('adapterStatus');
    if (data.status === 'connected') {
        statusElem.innerHTML = '<span class="badge bg-success">Conectado</span>';
    } else {
        statusElem.innerHTML = '<span class="badge bg-danger">Desconectado</span>';
    }
    
    // Estadísticas
    if (data.stats) {
        document.getElementById('statTxFrames').textContent = data.stats.total_tx_frames || 0;
        document.getElementById('statRxFrames').textContent = data.stats.total_rx_frames || 0;
        document.getElementById('statCrcErrors').textContent = data.stats.crc_errors || 0;
        document.getElementById('statTimeouts').textContent = data.stats.timeouts || 0;
        document.getElementById('statExceptions').textContent = data.stats.exceptions || 0;
        document.getElementById('statActiveDevices').textContent = data.stats.active_devices || 0;
    }
}

function showError(message) {
    const alertHtml = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <strong>Error:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    document.body.insertAdjacentHTML('afterbegin', alertHtml);
}
