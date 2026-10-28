import json
from app.db.session import Base,engine,SessionLocal
from app.models.entities import OfficialSource,Scheme
from app.services.rag.engine import index_source
Base.metadata.create_all(bind=engine);db=SessionLocal()
seeds=[('National Scholarship Portal','Ministry of Education, Government of India','https://scholarships.gov.in/','scholarship'),('myScheme — Government Schemes','Government of India','https://www.myscheme.gov.in/','scheme'),('National Government Services Portal','Government of India','https://services.india.gov.in/','scheme'),('National Portal of India','Government of India','https://www.india.gov.in/','scheme')]
for title,authority,url,kind in seeds:
 s=db.query(OfficialSource).filter_by(url=url).first()
 if not s:s=OfficialSource(title=title,authority=authority,url=url,source_type='official portal',status='requires_review',content=f'{title} is an official portal discovery starting point. Scheme-level rules, benefits, documents, and deadlines must be checked on the relevant official page.');db.add(s);db.flush()
 if not db.query(Scheme).filter_by(name=title).first():db.add(Scheme(name=title,category='Scholarship' if kind=='scholarship' else 'Public services',audience='Students and citizens',description=f'Official portal for discovering current information and application guidance: {title}. This is a portal listing, not a verified individual scheme.',authority=authority,state='Central',education_level='All',benefit_type='Information and applications',eligibility_text='Not specified in this catalogue entry. Review the relevant scheme official guidelines.',benefits='Not specified in available source',documents_json=json.dumps(["Check the selected scheme's official document list"]),steps_json=json.dumps(['Open the official portal','Find the relevant scheme','Read current eligibility and instructions','Apply only through the official application route']),application_url=url,source_id=s.id,verified=False,kind=kind))
 if s.content:index_source(db,s)
db.commit();print(f"Seed complete: {db.query(Scheme).count()} schemes, {db.query(OfficialSource).count()} sources. Records marked requires_review.");db.close()
