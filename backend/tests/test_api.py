def test_health(client):assert client.get('/health').json()['status']=='ok'
def test_register_login(client):
 r=client.post('/api/v1/auth/register',json={'email':'test@example.com','password':'safe-password-123'});assert r.status_code==201;token=r.json()['access_token']
 assert client.get('/api/v1/auth/me',headers={'Authorization':f'Bearer {token}'}).status_code==200
 assert client.post('/api/v1/auth/login',json={'email':'test@example.com','password':'safe-password-123'}).status_code==200
def test_scheme_not_found(client):assert client.get('/api/v1/schemes/999').status_code==404
def test_admin_protected(client):assert client.get('/api/v1/admin/metrics').status_code==401
def test_chat_no_evidence(client):
 r=client.post('/api/v1/assistant/chat',json={'question':'What is the verified deadline for this scheme?'});assert r.status_code==200;assert r.json()['citations']==[];assert 'couldn\'t find' in r.json()['answer']
