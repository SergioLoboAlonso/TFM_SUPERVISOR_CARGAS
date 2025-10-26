async function refresh() {
  const r = await fetch('/state');
  const j = await r.json();
  document.getElementById('data').textContent = JSON.stringify(j, null, 2);
  document.getElementById('unit').value = j.unit;
}
setInterval(refresh, 1000);
refresh();

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
