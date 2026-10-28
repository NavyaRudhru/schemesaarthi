import os
os.environ['DATABASE_URL']='sqlite:///./test_schemesaarthi.db';os.environ['SECRET_KEY']='test-secret-key-that-is-long-enough'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base,engine
@pytest.fixture()
def client():
 Base.metadata.drop_all(bind=engine);Base.metadata.create_all(bind=engine)
 with TestClient(app) as c:yield c
 Base.metadata.drop_all(bind=engine)
