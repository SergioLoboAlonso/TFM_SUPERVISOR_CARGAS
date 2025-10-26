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
  const seconds = parseInt(document.getElementById('secs').value,10);
  const r = await fetch('/identify', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({unit, seconds})
  });
  const j = await r.json();
  alert(j.ok ? 'OK' : ('Error: ' + (j.err||'desconocido')));
};
