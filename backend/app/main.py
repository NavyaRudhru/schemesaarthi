import json, os
from datetime import datetime,timezone
from fastapi import FastAPI,Depends,HTTPException,UploadFile,File,Form,Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field
from sqlalchemy.orm import Session
from sqlalchemy import or_,func,text
from app.db.session import Base,engine,get_db
from app.models.entities import User,Scheme,OfficialSource,Chunk,SavedScheme,Assessment,Checklist,ChecklistItem,ChatSession,ChatMessage,IngestionJob
from app.services.security import hash_password,verify_password,create_token,current_user,require_user,require_admin
from app.services.rag.engine import index_source,answer_question
from app.services.ingestion.parser import parse_bytes,parse_html_url
from app.core.config import settings
app=FastAPI(title='SchemeSaarthi AI API',version='1.0.0',description='Source-grounded government scheme and scholarship assistant')
app.add_middleware(CORSMiddleware,allow_origins=list({settings.frontend_url,'http://127.0.0.1:5173'}),allow_credentials=True,allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],allow_headers=['Authorization','Content-Type'])
class RegisterIn(BaseModel): email:EmailStr;password:str=Field(min_length=8,max_length=72)
class LoginIn(BaseModel): email:EmailStr;password:str
class ChatIn(BaseModel): question:str=Field(min_length=2,max_length=4000);language:str='en';session_id:int|None=None
class EligibilityIn(BaseModel): scheme_id:int;state:str|None=None;age:int|None=None;education_level:str|None=None;annual_income:float|None=None;student_status:str|None=None;domicile:bool|None=None;academic_percentage:float|None=None
class SourceIn(BaseModel): title:str=Field(min_length=3,max_length=250);url:str;authority:str=Field(min_length=2,max_length=250);source_type:str='official webpage'
def source_out(s):return {'id':s.id,'title':s.title,'authority':s.authority,'url':s.url,'source_type':s.source_type,'publication_date':s.publication_date,'retrieved_at':s.retrieved_at,'verified_at':s.verified_at,'status':s.status,'chunks':len(s.content)//900 if s.content else 0}
def scheme_out(s):
 src=None
 if s.source_id:
  from sqlalchemy.orm import object_session
  db=object_session(s);z=db.get(OfficialSource,s.source_id) if db else None
  if z:src=source_out(z)
 return {'id':s.id,'name':s.name,'category':s.category,'audience':s.audience,'description':s.description,'authority':s.authority,'state':s.state,'education_level':s.education_level,'benefit_type':s.benefit_type,'income_limit':s.income_limit,'min_age':s.min_age,'max_age':s.max_age,'eligibility_text':s.eligibility_text,'benefits':s.benefits,'documents':json.loads(s.documents_json or '[]'),'steps':json.loads(s.steps_json or '[]'),'application_url':s.application_url,'deadline':s.deadline if s.verified else None,'verified':s.verified,'last_verified':s.last_verified,'kind':s.kind,'source':src}
def checklist_out(c,db):
 s=db.get(Scheme,c.scheme_id);items=db.query(ChecklistItem).filter_by(checklist_id=c.id).all();done=sum(i.status!='pending' for i in items)
 return {'id':c.id,'scheme':scheme_out(s) if s else None,'items':[{'id':i.id,'name':i.name,'status':i.status,'notes':i.notes} for i in items],'progress':round(done/len(items)*100) if items else 0}
def init_db():Base.metadata.create_all(bind=engine)
@app.on_event('startup')
def startup():init_db()
@app.get('/health')
def health():return {'status':'ok','service':'schemesaarthi-ai'}
@app.get('/ready')
def ready(db:Session=Depends(get_db)):
 try:db.execute(text('SELECT 1'));return {'status':'ready','database':'ok'}
 except Exception:raise HTTPException(503,'Database is not ready')
@app.post('/api/v1/auth/register',status_code=201)
def register(data:RegisterIn,db:Session=Depends(get_db)):
 if db.query(User).filter(func.lower(User.email)==data.email.lower()).first():raise HTTPException(409,'Email is already registered')
 u=User(email=data.email.lower(),password_hash=hash_password(data.password),role='user');db.add(u);db.commit();db.refresh(u);return {'access_token':create_token(u),'token_type':'bearer','user':{'id':u.id,'email':u.email,'role':u.role}}
@app.post('/api/v1/auth/login')
def login(data:LoginIn,db:Session=Depends(get_db)):
 u=db.query(User).filter(func.lower(User.email)==data.email.lower()).first()
 if not u or not verify_password(data.password,u.password_hash):raise HTTPException(401,'Email or password is incorrect')
 return {'access_token':create_token(u),'token_type':'bearer','user':{'id':u.id,'email':u.email,'role':u.role}}
@app.post('/api/v1/auth/logout')
def logout(user:User=Depends(require_user)):return {'message':'Discard the bearer token on this client to log out.'}
@app.get('/api/v1/auth/me')
def me(user:User=Depends(require_user)):return {'id':user.id,'email':user.email,'role':user.role}
def get_schemes(db,q=None,state=None,category=None,education_level=None,kind=None,sort='relevance',page=1,page_size=12):
 query=db.query(Scheme)
 if q:query=query.filter(or_(Scheme.name.ilike(f'%{q}%'),Scheme.description.ilike(f'%{q}%'),Scheme.authority.ilike(f'%{q}%'),Scheme.category.ilike(f'%{q}%')))
 if state and state!='All':query=query.filter(Scheme.state==state)
 if category and category!='All':query=query.filter(Scheme.category==category)
 if education_level and education_level!='All':query=query.filter(or_(Scheme.education_level==education_level,Scheme.education_level=='All'))
 if kind:query=query.filter(Scheme.kind==kind)
 if sort=='name':query=query.order_by(Scheme.name.asc())
 elif sort=='deadline':query=query.order_by(Scheme.deadline.asc().nullslast())
 total=query.count();items=query.offset((page-1)*page_size).limit(page_size).all()
 return {'items':[scheme_out(s) for s in items],'total':total,'page':page,'page_size':page_size,'pages':(total+page_size-1)//page_size}
@app.get('/api/v1/schemes')
def list_schemes(q:str|None=None,state:str|None=None,category:str|None=None,education_level:str|None=None,kind:str|None=None,sort:str='relevance',page:int=Query(1,ge=1),page_size:int=Query(12,ge=1,le=100),db:Session=Depends(get_db)):return get_schemes(db,q,state,category,education_level,kind,sort,page,page_size)
@app.get('/api/v1/schemes/search')
def search_schemes(q:str=Query(min_length=1),db:Session=Depends(get_db)):return get_schemes(db,q,page_size=20)
@app.get('/api/v1/schemes/featured')
def featured(db:Session=Depends(get_db)):return {'items':[scheme_out(s) for s in db.query(Scheme).order_by(Scheme.id).limit(4).all()]}
@app.get('/api/v1/schemes/{scheme_id}')
def scheme_detail(scheme_id:int,db:Session=Depends(get_db)):
 s=db.get(Scheme,scheme_id)
 if not s:raise HTTPException(404,'Scheme not found')
 return scheme_out(s)
@app.get('/api/v1/scholarships')
def scholarships(q:str|None=None,state:str|None=None,education_level:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(12,ge=1,le=100),db:Session=Depends(get_db)):return get_schemes(db,q,state,'All',education_level,'scholarship','name',page,page_size)
@app.get('/api/v1/scholarships/{scheme_id}')
def scholarship_detail(scheme_id:int,db:Session=Depends(get_db)):
 s=db.get(Scheme,scheme_id)
 if not s or s.kind!='scholarship':raise HTTPException(404,'Scholarship not found')
 return scheme_out(s)
@app.post('/api/v1/eligibility/check')
def eligibility(data:EligibilityIn,db:Session=Depends(get_db),user:User|None=Depends(current_user)):
 s=db.get(Scheme,data.scheme_id)
 if not s:raise HTTPException(404,'Scheme not found')
 missing=[];matched=[];failed=[]
 if s.min_age is not None or s.max_age is not None:
  if data.age is None:missing.append('age')
  elif (s.min_age is not None and data.age<s.min_age) or (s.max_age is not None and data.age>s.max_age):failed.append(f'Age must be between {s.min_age or "any"} and {s.max_age or "any"}')
  else:matched.append('Age is within the configured range')
 if s.income_limit is not None:
  if data.annual_income is None:missing.append('annual family income')
  elif data.annual_income>s.income_limit:failed.append(f'Annual family income exceeds configured limit of ₹{s.income_limit:,.0f}')
  else:matched.append('Annual family income is within the configured limit')
 if s.education_level not in ('All','Not specified'):
  if not data.education_level:missing.append('education level')
  elif data.education_level.lower()!=s.education_level.lower():failed.append(f'Education level does not match configured requirement: {s.education_level}')
  else:matched.append('Education level matches configured requirement')
 outcome='likely_not_eligible' if failed else ('more_information_required' if missing else ('likely_eligible' if s.verified else 'cannot_determine'))
 result={'outcome':outcome,'matched_rules':matched,'requirements_not_met':failed,'missing_information':missing,'scheme':scheme_out(s),'citations':[s.source_id] if s.source_id else [],'disclaimer':'Preliminary assessment only. This is not an official government decision. Catalogue rules may be incomplete or unverified.'}
 db.add(Assessment(user_id=user.id if user else None,scheme_id=s.id,outcome=outcome,details_json=json.dumps(result)));db.commit();return result
@app.get('/api/v1/eligibility/history')
def eligibility_history(db:Session=Depends(get_db),user:User=Depends(require_user)):return {'items':[{'id':a.id,'scheme_id':a.scheme_id,'outcome':a.outcome,'created_at':str(a.created_at)} for a in db.query(Assessment).filter_by(user_id=user.id).order_by(Assessment.id.desc()).limit(50).all()]}
@app.get('/api/v1/saved')
def get_saved(db:Session=Depends(get_db),user:User=Depends(require_user)):return {'items':[scheme_out(s) for x in db.query(SavedScheme).filter_by(user_id=user.id).all() if (s:=db.get(Scheme,x.scheme_id))]}
@app.post('/api/v1/saved/{scheme_id}',status_code=201)
def save_scheme(scheme_id:int,db:Session=Depends(get_db),user:User=Depends(require_user)):
 if not db.get(Scheme,scheme_id):raise HTTPException(404,'Scheme not found')
 if not db.query(SavedScheme).filter_by(user_id=user.id,scheme_id=scheme_id).first():db.add(SavedScheme(user_id=user.id,scheme_id=scheme_id));db.commit()
 return {'saved':True,'scheme_id':scheme_id}
@app.delete('/api/v1/saved/{scheme_id}')
def unsave_scheme(scheme_id:int,db:Session=Depends(get_db),user:User=Depends(require_user)):db.query(SavedScheme).filter_by(user_id=user.id,scheme_id=scheme_id).delete();db.commit();return {'saved':False,'scheme_id':scheme_id}
@app.get('/api/v1/checklists')
def get_checklists(db:Session=Depends(get_db),user:User|None=Depends(current_user),guest_key:str|None=None):
 q=db.query(Checklist).filter(Checklist.user_id==user.id) if user else db.query(Checklist).filter(Checklist.guest_key==guest_key)
 return {'items':[checklist_out(c,db) for c in q.order_by(Checklist.id.desc()).all()]}
@app.post('/api/v1/checklists',status_code=201)
def create_checklist(payload:dict,db:Session=Depends(get_db),user:User|None=Depends(current_user)):
 sid=payload.get('scheme_id');s=db.get(Scheme,sid) if isinstance(sid,int) else None
 if not s:raise HTTPException(404,'Scheme not found')
 c=Checklist(user_id=user.id if user else None,scheme_id=s.id,guest_key=payload.get('guest_key') if not user else None);db.add(c);db.flush()
 for name in json.loads(s.documents_json or '[]'):db.add(ChecklistItem(checklist_id=c.id,name=name,status='pending',notes=''))
 db.commit();db.refresh(c);return checklist_out(c,db)
def check_access(c,user,guest_key):
 if (user and c.user_id!=user.id) or (not user and c.guest_key!=guest_key):raise HTTPException(403,'Checklist access denied')
@app.patch('/api/v1/checklists/{checklist_id}/items/{item_id}')
def update_checklist_item(checklist_id:int,item_id:int,payload:dict,db:Session=Depends(get_db),user:User|None=Depends(current_user),guest_key:str|None=None):
 c=db.get(Checklist,checklist_id);i=db.get(ChecklistItem,item_id)
 if not c or not i or i.checklist_id!=c.id:raise HTTPException(404,'Checklist item not found')
 check_access(c,user,guest_key)
 if payload.get('status') not in ('pending','prepared','not_applicable'):raise HTTPException(422,'Invalid status')
 i.status=payload['status'];i.notes=str(payload.get('notes',''))[:2000];db.commit();return checklist_out(c,db)
@app.delete('/api/v1/checklists/{checklist_id}')
def delete_checklist(checklist_id:int,db:Session=Depends(get_db),user:User|None=Depends(current_user),guest_key:str|None=None):
 c=db.get(Checklist,checklist_id)
 if not c:raise HTTPException(404,'Checklist not found')
 check_access(c,user,guest_key);db.delete(c);db.commit();return {'deleted':True}
@app.post('/api/v1/schemes/compare')
def compare(payload:dict,db:Session=Depends(get_db)):
 ids=payload.get('scheme_ids',[])
 if not isinstance(ids,list) or not 2<=len(ids)<=5:raise HTTPException(422,'Select between 2 and 5 schemes')
 return {'items':[scheme_out(s) for i in ids if (s:=db.get(Scheme,i))]}
@app.post('/api/v1/assistant/chat')
def chat(data:ChatIn,db:Session=Depends(get_db),user:User|None=Depends(current_user)):
 sess=db.get(ChatSession,data.session_id) if data.session_id else None
 if sess and ((user and sess.user_id!=user.id) or (not user and sess.user_id is not None)):raise HTTPException(403,'Conversation access denied')
 if not sess:sess=ChatSession(user_id=user.id if user else None,title=data.question[:80]);db.add(sess);db.commit();db.refresh(sess)
 db.add(ChatMessage(session_id=sess.id,role='user',content=data.question));result=answer_question(db,data.question,data.language);db.add(ChatMessage(session_id=sess.id,role='assistant',content=result['answer'],citations_json=json.dumps(result['citations'])));db.commit();result['session_id']=sess.id
 result['related_schemes']=[];return result
@app.get('/api/v1/assistant/sessions')
def sessions(db:Session=Depends(get_db),user:User|None=Depends(current_user)):
 q=db.query(ChatSession).filter(ChatSession.user_id==user.id) if user else db.query(ChatSession).filter(ChatSession.user_id.is_(None))
 return {'items':[{'id':s.id,'title':s.title,'created_at':str(s.created_at)} for s in q.order_by(ChatSession.id.desc()).limit(50).all()]}
@app.get('/api/v1/assistant/sessions/{session_id}')
def session_detail(session_id:int,db:Session=Depends(get_db),user:User|None=Depends(current_user)):
 s=db.get(ChatSession,session_id)
 if not s or (user and s.user_id!=user.id) or (not user and s.user_id is not None):raise HTTPException(404,'Conversation not found')
 return {'id':s.id,'title':s.title,'messages':[{'id':m.id,'role':m.role,'content':m.content,'citations':json.loads(m.citations_json or '[]')} for m in db.query(ChatMessage).filter_by(session_id=s.id).order_by(ChatMessage.id).all()]}
@app.delete('/api/v1/assistant/sessions/{session_id}')
def delete_session(session_id:int,db:Session=Depends(get_db),user:User|None=Depends(current_user)):
 s=db.get(ChatSession,session_id)
 if not s or (user and s.user_id!=user.id) or (not user and s.user_id is not None):raise HTTPException(404,'Conversation not found')
 db.delete(s);db.commit();return {'deleted':True}
@app.get('/api/v1/sources')
def sources(q:str|None=None,status:str|None=None,db:Session=Depends(get_db)):
 query=db.query(OfficialSource)
 if q:query=query.filter(or_(OfficialSource.title.ilike(f'%{q}%'),OfficialSource.authority.ilike(f'%{q}%')))
 if status:query=query.filter(OfficialSource.status==status)
 return {'items':[source_out(s) for s in query.order_by(OfficialSource.id).all()]}
@app.get('/api/v1/sources/{source_id}')
def source_detail(source_id:int,db:Session=Depends(get_db)):
 s=db.get(OfficialSource,source_id)
 if not s:raise HTTPException(404,'Source not found')
 return {**source_out(s),'content_preview':s.content[:3000]}
@app.post('/api/v1/admin/sources',status_code=201)
def add_source(data:SourceIn,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
 if not data.url.startswith('https://'):raise HTTPException(422,'Only HTTPS source URLs are accepted')
 if db.query(OfficialSource).filter_by(url=data.url).first():raise HTTPException(409,'Source URL already exists')
 s=OfficialSource(title=data.title,authority=data.authority,url=data.url,source_type=data.source_type,status='requires_review');db.add(s);db.commit();db.refresh(s);return source_out(s)
@app.post('/api/v1/admin/sources/upload',status_code=201)
async def upload_source(title:str=Form(...),authority:str=Form(...),file:UploadFile=File(...),db:Session=Depends(get_db),admin:User=Depends(require_admin)):
 data=await file.read(settings.max_upload_mb*1024*1024+1)
 if len(data)>settings.max_upload_mb*1024*1024:raise HTTPException(413,'File exceeds configured upload limit')
 try:content=parse_bytes(file.filename or 'upload.txt',data)
 except Exception as e:raise HTTPException(422,str(e))
 if not content:raise HTTPException(422,'No readable text found in uploaded file')
 s=OfficialSource(title=title[:250],authority=authority[:250],url=f"local-upload://{datetime.now(timezone.utc).timestamp()}-{(file.filename or 'document')[:100]}",source_type=(file.filename or 'document').split('.')[-1].lower(),retrieved_at=datetime.now(timezone.utc).isoformat(),status='requires_review',content=content);db.add(s);db.commit();db.refresh(s);count=index_source(db,s);db.add(IngestionJob(source_id=s.id,status='completed',message=f'Indexed {count} chunks; source remains unverified.'));db.commit();return {**source_out(s),'indexed_chunks':count}
@app.post('/api/v1/admin/sources/{source_id}/reindex')
def reindex_source(source_id:int,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
 s=db.get(OfficialSource,source_id)
 if not s:raise HTTPException(404,'Source not found')
 if not s.content and s.url.startswith('https://'):
  try:s.content=parse_html_url(s.url);s.retrieved_at=datetime.now(timezone.utc).isoformat()
  except Exception as e:raise HTTPException(422,f'Source fetch failed: {str(e)[:200]}')
 if not s.content:raise HTTPException(422,'Source has no content. Upload or fetch content first.')
 count=index_source(db,s);s.status='requires_review';db.commit();db.add(IngestionJob(source_id=s.id,status='completed',message=f'Re-indexed {count} chunks; verification requires human review.'));db.commit();return {'source':source_out(s),'indexed_chunks':count}
@app.post('/api/v1/admin/sources/{source_id}/review')
def review_source(source_id:int,payload:dict,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
 s=db.get(OfficialSource,source_id)
 if not s:raise HTTPException(404,'Source not found')
 status=payload.get('status')
 if status not in ('verified','stale','requires_review','unverified'):raise HTTPException(422,'Invalid source status')
 s.status=status;s.verified_at=datetime.now(timezone.utc).date().isoformat() if status=='verified' else None
 for c in db.query(Chunk).filter_by(source_id=s.id).all():c.verification_status=status
 db.commit();return source_out(s)
@app.get('/api/v1/admin/ingestion-jobs')
def ingestion_jobs(db:Session=Depends(get_db),admin:User=Depends(require_admin)):return {'items':[{'id':j.id,'source_id':j.source_id,'status':j.status,'message':j.message,'created_at':str(j.created_at)} for j in db.query(IngestionJob).order_by(IngestionJob.id.desc()).limit(100).all()]}
@app.get('/api/v1/admin/metrics')
def metrics(db:Session=Depends(get_db),admin:User=Depends(require_admin)):return {'users':db.query(User).count(),'schemes':db.query(Scheme).count(),'sources':db.query(OfficialSource).count(),'chunks':db.query(Chunk).count(),'chat_messages':db.query(ChatMessage).count(),'assessments':db.query(Assessment).count()}
@app.post('/api/v1/admin/bootstrap')
def bootstrap_admin(payload:dict,db:Session=Depends(get_db)):
 if db.query(User).filter_by(role='admin').first():raise HTTPException(403,'An administrator already exists')
 if not settings.admin_bootstrap_secret or payload.get('bootstrap_secret')!=settings.admin_bootstrap_secret:raise HTTPException(403,'Set ADMIN_BOOTSTRAP_SECRET in backend environment before bootstrap')
 email=str(payload.get('email',''));password=str(payload.get('password',''))
 if len(password)<12 or '@' not in email:raise HTTPException(422,'Valid email and password of at least 12 characters required')
 u=User(email=email.lower(),password_hash=hash_password(password),role='admin');db.add(u);db.commit();return {'created':True,'email':u.email,'message':'Remove ADMIN_BOOTSTRAP_SECRET after bootstrap.'}
