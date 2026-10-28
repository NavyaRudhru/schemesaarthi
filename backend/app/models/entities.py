from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True); email: Mapped[str]=mapped_column(String(255),unique=True,index=True); password_hash: Mapped[str]=mapped_column(String(255)); role: Mapped[str]=mapped_column(String(20),default="user"); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class OfficialSource(Base):
    __tablename__="official_sources"
    id: Mapped[int]=mapped_column(primary_key=True); title: Mapped[str]=mapped_column(String(250)); authority: Mapped[str]=mapped_column(String(250),default="Not specified"); url: Mapped[str]=mapped_column(String(1000),unique=True); source_type: Mapped[str]=mapped_column(String(40),default="official webpage"); publication_date: Mapped[str|None]=mapped_column(String(50),nullable=True); retrieved_at: Mapped[str|None]=mapped_column(String(50),nullable=True); verified_at: Mapped[str|None]=mapped_column(String(50),nullable=True); status: Mapped[str]=mapped_column(String(30),default="requires_review"); content: Mapped[str]=mapped_column(Text,default=""); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class Scheme(Base):
    __tablename__="schemes"
    id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(250),index=True); category: Mapped[str]=mapped_column(String(80),index=True); audience: Mapped[str]=mapped_column(String(150),default="Citizens"); description: Mapped[str]=mapped_column(Text); authority: Mapped[str]=mapped_column(String(250),default="Not specified"); state: Mapped[str]=mapped_column(String(100),default="Central"); education_level: Mapped[str]=mapped_column(String(100),default="All"); benefit_type: Mapped[str]=mapped_column(String(100),default="Assistance"); income_limit: Mapped[float|None]=mapped_column(Float,nullable=True); min_age: Mapped[int|None]=mapped_column(Integer,nullable=True); max_age: Mapped[int|None]=mapped_column(Integer,nullable=True); eligibility_text: Mapped[str]=mapped_column(Text,default="Check official source."); benefits: Mapped[str]=mapped_column(Text,default="Not specified in available source"); documents_json: Mapped[str]=mapped_column(Text,default='["Check official guidelines"]'); steps_json: Mapped[str]=mapped_column(Text,default='["Read official guidelines", "Confirm eligibility", "Apply through official portal"]'); application_url: Mapped[str]=mapped_column(String(500),default="https://www.myscheme.gov.in/"); deadline: Mapped[str|None]=mapped_column(String(50),nullable=True); source_id: Mapped[int|None]=mapped_column(ForeignKey("official_sources.id"),nullable=True); verified: Mapped[bool]=mapped_column(Boolean,default=False); last_verified: Mapped[str|None]=mapped_column(String(50),nullable=True); kind: Mapped[str]=mapped_column(String(30),default="scheme"); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class Chunk(Base):
    __tablename__="document_chunks"
    id: Mapped[int]=mapped_column(primary_key=True); source_id: Mapped[int]=mapped_column(ForeignKey("official_sources.id",ondelete="CASCADE"),index=True); title: Mapped[str]=mapped_column(String(250)); url: Mapped[str]=mapped_column(String(1000)); authority: Mapped[str]=mapped_column(String(250)); section: Mapped[str]=mapped_column(String(250),default="Extracted content"); text: Mapped[str]=mapped_column(Text); chunk_hash: Mapped[str]=mapped_column(String(64),unique=True); verification_status: Mapped[str]=mapped_column(String(30),default="requires_review")
class SavedScheme(Base):
    __tablename__="saved_schemes"; __table_args__=(UniqueConstraint("user_id","scheme_id"),)
    id: Mapped[int]=mapped_column(primary_key=True); user_id: Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True); scheme_id: Mapped[int]=mapped_column(ForeignKey("schemes.id",ondelete="CASCADE"),index=True); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class Assessment(Base):
    __tablename__="eligibility_assessments"
    id: Mapped[int]=mapped_column(primary_key=True); user_id: Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True); scheme_id: Mapped[int]=mapped_column(ForeignKey("schemes.id")); outcome: Mapped[str]=mapped_column(String(50)); details_json: Mapped[str]=mapped_column(Text); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class Checklist(Base):
    __tablename__="checklists"
    id: Mapped[int]=mapped_column(primary_key=True); user_id: Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),nullable=True); scheme_id: Mapped[int]=mapped_column(ForeignKey("schemes.id")); guest_key: Mapped[str|None]=mapped_column(String(100),nullable=True); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class ChecklistItem(Base):
    __tablename__="checklist_items"
    id: Mapped[int]=mapped_column(primary_key=True); checklist_id: Mapped[int]=mapped_column(ForeignKey("checklists.id",ondelete="CASCADE"),index=True); name: Mapped[str]=mapped_column(String(250)); status: Mapped[str]=mapped_column(String(30),default="pending"); notes: Mapped[str]=mapped_column(Text,default="")
class ChatSession(Base):
    __tablename__="chat_sessions"
    id: Mapped[int]=mapped_column(primary_key=True); user_id: Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),nullable=True); title: Mapped[str]=mapped_column(String(250),default="New conversation"); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class ChatMessage(Base):
    __tablename__="chat_messages"
    id: Mapped[int]=mapped_column(primary_key=True); session_id: Mapped[int]=mapped_column(ForeignKey("chat_sessions.id",ondelete="CASCADE"),index=True); role: Mapped[str]=mapped_column(String(20)); content: Mapped[str]=mapped_column(Text); citations_json: Mapped[str]=mapped_column(Text,default="[]"); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
class IngestionJob(Base):
    __tablename__="ingestion_jobs"
    id: Mapped[int]=mapped_column(primary_key=True); source_id: Mapped[int|None]=mapped_column(ForeignKey("official_sources.id"),nullable=True); status: Mapped[str]=mapped_column(String(30),default="queued"); message: Mapped[str]=mapped_column(Text,default=""); created_at: Mapped[object]=mapped_column(DateTime,server_default=func.now())
