import time
from fastapi.testclient import TestClient
from app.main import create_app


def wait(client,run_id):
    for _ in range(200):
        row=client.get('/api/research/'+run_id).json()
        if row['status'] in {'completed','failed','rejected','interrupted'}:
            return row
        time.sleep(.025)
    raise AssertionError('Local research did not finish')


def test_api_and_exports(settings,request_data):
    with TestClient(create_app(settings)) as client:
        assert client.get('/').status_code==200
        assert client.get('/static/app.js').status_code==200
        assert client.get('/api/health').json()['status']=='ok'
        response=client.post('/api/research',json=request_data)
        assert response.status_code==202
        run_id=response.json()['id'];row=wait(client,run_id)
        assert row['status']=='completed'
        assert client.get('/api/research/'+run_id+'/events').json()['events']
        for fmt in ['json','curve','trades','snapshot']:
            assert client.get('/api/research/'+run_id+'/export/'+fmt).status_code==200
        assert 'Quant Research Report' in client.get('/api/research/'+run_id+'/report').text
        replay=client.post('/api/research/'+run_id+'/replay')
        assert replay.status_code==202
        replay_row=wait(client,replay.json()['id'])
        assert replay_row['result']['backtest']['metrics']==row['result']['backtest']['metrics']


def test_api_validation_security_and_unknowns(settings):
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/research',json={'query':'x'}).status_code==422
        assert client.get('/api/research/not-found').status_code==404
        assert client.get('/api/health',headers={'Host':'evil.example'}).status_code==400
        assert client.post('/api/research',headers={'Origin':'https://evil.example'},json={}).status_code==403
        assert client.get('/api/health').headers['X-Content-Type-Options']=='nosniff'


def test_offline_api_docs(settings):
    with TestClient(create_app(settings)) as client:
        response=client.get('/docs')
        assert response.status_code==200
        assert 'cdn.' not in response.text
        assert client.get('/openapi.json').status_code==200
