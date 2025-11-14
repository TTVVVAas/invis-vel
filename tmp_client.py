from app import app
client = app.test_client()
resp = client.get('/')
print(resp.status_code)
print(resp.headers.get('Location'))
