import time, jwt, os, hashlib, hmac, base64
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import User
from app.core.config import settings
bearer=HTTPBearer(auto_error=False)
def hash_password(password:str)->str:
    salt=os.urandom(16); digest=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1); return 'scrypt$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(digest).decode()
def verify_password(password:str,hashed:str)->bool:
    try:
        scheme,salt,digest=hashed.split('$'); return scheme=='scrypt' and hmac.compare_digest(hashlib.scrypt(password.encode(),salt=base64.b64decode(salt),n=2**14,r=8,p=1),base64.b64decode(digest))
    except Exception:return False
def create_token(user:User)->str:return jwt.encode({'sub':str(user.id),'exp':int(time.time())+86400},settings.secret_key,algorithm='HS256')
def current_user(creds:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db))->User|None:
    if not creds:return None
    try:payload=jwt.decode(creds.credentials,settings.secret_key,algorithms=['HS256']);user=db.get(User,int(payload['sub']))
    except Exception:raise HTTPException(401,'Invalid or expired session')
    if not user:raise HTTPException(401,'User no longer exists')
    return user
def require_user(user:User|None=Depends(current_user))->User:
    if not user:raise HTTPException(401,'Please log in to use this feature')
    return user
def require_admin(user:User=Depends(require_user))->User:
    if user.role!='admin':raise HTTPException(403,'Administrator access required')
    return user
