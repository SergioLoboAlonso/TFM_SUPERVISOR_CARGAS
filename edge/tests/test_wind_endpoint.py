import pytest
from src.app import app

class DummyPolling:
    def __init__(self):
        self._data = {}
    def get_last_wind(self, unit_id: int):
        return self._data.get(unit_id)

@pytest.fixture()
def client(monkeypatch):
    dummy = DummyPolling()
    # Inyectar datos de ejemplo para unit 1
    dummy._data[1] = {
        'unit_id': 1,
        'wind_speed_mps': 3.25,
        'wind_direction_deg': 185,
        'timestamp': '2025-11-10T12:00:00'
    }
    # Monkeypatch global polling_service en app
    monkeypatch.setattr('src.app.polling_service', dummy)
    with app.test_client() as c:
        yield c


def test_wind_endpoint_ok(client):
    resp = client.get('/api/wind/1')
    assert resp.status_code == 200
    js = resp.get_json()
    assert js['status'] == 'ok'
    assert js['wind_speed_mps'] == 3.25
    assert js['wind_direction_deg'] == 185


def test_wind_endpoint_not_found(client, monkeypatch):
    # Reemplazar datos para que unit 5 no exista
    dummy = DummyPolling()
    monkeypatch.setattr('src.app.polling_service', dummy)
    resp = client.get('/api/wind/5')
    assert resp.status_code == 404
    js = resp.get_json()
    assert 'error' in js