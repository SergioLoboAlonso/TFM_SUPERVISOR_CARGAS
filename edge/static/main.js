async function refresh() {
  const r = await fetch('/state');
  const j = await r.json();
  document.getElementById('data').textContent = JSON.stringify(j, null, 2);
  const unitEl = document.getElementById('unit');
  // No pisar el valor que el usuario está editando activamente
  if (document.activeElement !== unitEl) {
    unitEl.value = j.unit;
  }

  // Decodificar versiones para mostrar en resumen (major.minor desde registros)
  const hr = j.holding || {};
  // Vendor: si viene como string ASCII, úsalo; si no, intenta decodificar desde el entero 16-bit
  if (typeof hr.vendor_str === 'string') {
    document.getElementById('vendor_str').textContent = hr.vendor_str;
  } else if (typeof hr.vendor === 'number') {
    const msb = (hr.vendor >> 8) & 0xFF;
    const lsb = hr.vendor & 0xFF;
    if (msb >= 32 && msb <= 126 && lsb >= 32 && lsb <= 126) {
      document.getElementById('vendor_str').textContent = String.fromCharCode(msb) + String.fromCharCode(lsb);
    } else {
      document.getElementById('vendor_str').textContent = String(hr.vendor);
    }
  } else {
    document.getElementById('vendor_str').textContent = '—';
  }
  // Alias si está disponible
  if (typeof hr.alias_str === 'string' && hr.alias_str.length > 0) {
    document.getElementById('alias_str').textContent = hr.alias_str;
  } else {
    document.getElementById('alias_str').textContent = '—';
  }
  if (typeof hr.fw_str === 'string') {
    document.getElementById('fw_str').textContent = hr.fw_str;
  } else if (typeof hr.fw === 'number') {
    const maj = (hr.fw >> 8) & 0xFF;
    const min = hr.fw & 0xFF;
    document.getElementById('fw_str').textContent = `${maj}.${min}`;
  } else {
    document.getElementById('fw_str').textContent = '—';
  }
  if (typeof hr.hw_str === 'string') {
    document.getElementById('hw_str').textContent = hr.hw_str;
  } else if (typeof hr.hw === 'number') {
    const maj = (hr.hw >> 8) & 0xFF;
    const min = hr.hw & 0xFF;
    document.getElementById('hw_str').textContent = `${maj}.${min}`;
  } else {
    document.getElementById('hw_str').textContent = '—';
  }
  if (typeof hr.product_str === 'string') {
    document.getElementById('product_str').textContent = hr.product_str;
  } else if (typeof hr.product === 'number') {
    const msb = (hr.product >> 8) & 0xFF;
    const lsb = hr.product & 0xFF;
    if (msb >= 32 && msb <= 126 && lsb >= 32 && lsb <= 126) {
      document.getElementById('product_str').textContent = String.fromCharCode(msb) + String.fromCharCode(lsb);
    } else {
      document.getElementById('product_str').textContent = String(hr.product);
    }
  } else {
    document.getElementById('product_str').textContent = '—';
  }
}
setInterval(refresh, 1000);
refresh();

// Listener para cambiar dinámicamente el UNIT_ID cuando el usuario modifique el input
document.getElementById('unit').addEventListener('change', async function() {
  const unit = parseInt(this.value, 10);
  if (unit >= 1 && unit <= 247) {
    try {
      const r = await fetch('/set_unit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({unit})
      });
      const j = await r.json();
      if (!j.ok) {
        console.error('Error al cambiar UNIT_ID:', j.err);
      }
    } catch (e) {
      console.error('Error al enviar cambio de UNIT_ID:', e);
    }
  }
});

document.getElementById('btn').onclick = async () => {
  const unit = parseInt(document.getElementById('unit').value,10);
  const r = await fetch('/identify', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({unit})
  });
  const j = await r.json();
  if(j.ok){
    const info = j.info || {};
    const lines = [];
    if (typeof info.text === 'string') lines.push(info.text);
    if (info.slaveId !== undefined) lines.push('slaveId=' + info.slaveId);
    if (info.running !== undefined) lines.push('running=' + (info.running ? 'yes' : 'no'));
    document.getElementById('identify_info').textContent = lines.join('\n');

    // Si viene cadena de identidad, intentar extraer FW y HW completos (incluye patch)
    if (typeof info.text === 'string') {
      const mFW = info.text.match(/v(\d+)\.(\d+)\.(\d+)/);
      if (mFW) {
        document.getElementById('fw_str').textContent = `${mFW[1]}.${mFW[2]}.${mFW[3]}`;
      }
      const mHW = info.text.match(/HW(\d+)\.(\d+)\.(\d+)/);
      if (mHW) {
        document.getElementById('hw_str').textContent = `${mHW[1]}.${mHW[2]}.${mHW[3]}`;
      }
    }
  } else {
    document.getElementById('identify_info').textContent = 'Error: ' + (j.err||'desconocido');
  }
};

document.getElementById('btn41').onclick = async () => {
  const unit = parseInt(document.getElementById('unit').value,10);
  const r = await fetch('/identify/trigger', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({unit})
  });
  const j = await r.json();
  if(j.ok){
    const info = j.info || {};
    const lines = [];
    if (typeof info.text === 'string') lines.push(info.text);
    if (info.slaveId !== undefined) lines.push('slaveId=' + info.slaveId);
    if (info.running !== undefined) lines.push('running=' + (info.running ? 'yes' : 'no'));
    document.getElementById('identify_info').textContent = lines.join('\n');

    if (typeof info.text === 'string') {
      const mFW = info.text.match(/v(\d+)\.(\d+)\.(\d+)/);
      if (mFW) {
        document.getElementById('fw_str').textContent = `${mFW[1]}.${mFW[2]}.${mFW[3]}`;
      }
      const mHW = info.text.match(/HW(\d+)\.(\d+)\.(\d+)/);
      if (mHW) {
        document.getElementById('hw_str').textContent = `${mHW[1]}.${mHW[2]}.${mHW[3]}`;
      }
    }
  } else {
    document.getElementById('identify_info').textContent = 'Error: ' + (j.err||'desconocido');
  }
};

document.getElementById('btn_secs').onclick = async () => {
  const unit = parseInt(document.getElementById('unit').value,10);
  const seconds = parseInt(document.getElementById('secs').value,10) || 0;
  const r = await fetch('/identify/seconds', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({unit, seconds})
  });
  const j = await r.json();
  if(j.ok){
    document.getElementById('identify_info').textContent = 'OK: escrito seconds=' + seconds;
  } else {
    document.getElementById('identify_info').textContent = 'Error: ' + (j.err||'desconocido');
  }
};

document.getElementById('btn_alias').onclick = async () => {
  const unit = parseInt(document.getElementById('unit').value,10);
  const alias = String(document.getElementById('alias').value||'').slice(0,64);
  const r = await fetch('/alias', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({unit, alias})
  });
  const j = await r.json();
  if(j.ok){
    document.getElementById('identify_info').textContent = 'OK: alias guardado';
    // refresco rápido del resumen
    refresh();
  } else {
    document.getElementById('identify_info').textContent = 'Error: ' + (j.err||'desconocido');
  }
};

document.getElementById('btn_scan').onclick = async () => {
  const start = parseInt(document.getElementById('scan_start').value,10) || 1;
  const end = parseInt(document.getElementById('scan_end').value,10) || 16;
  const r = await fetch('/diag/scan', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({start, end, includeInfo: true})
  });
  const j = await r.json();
  if (j.ok) {
    const arr = j.results || [];
    const lines = arr.map(e => {
      const sid = (e.slaveId !== undefined && e.slaveId !== null) ? ` slaveId=${e.slaveId}` : '';
      const txt = (e.text && e.text.length) ? `\n  ${e.text}` : '';
      return `unit=${e.unit} dev_unit_id=${e.dev_unit_id}${sid}${txt}`;
    });
    document.getElementById('scan_out').textContent = lines.length ? lines.join('\n') : '— (sin respuestas)';
    // Si hay exactamente uno, seleccionarlo automáticamente en el input UNIT_ID
    if (arr.length === 1 && typeof arr[0].unit === 'number') {
      const unitEl = document.getElementById('unit');
      unitEl.value = arr[0].unit;
    }
  } else {
    document.getElementById('scan_out').textContent = 'Error: ' + (j.err||'desconocido');
  }
};
