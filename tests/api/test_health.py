from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"} 