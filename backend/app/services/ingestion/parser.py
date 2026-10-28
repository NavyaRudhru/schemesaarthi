from bs4 import BeautifulSoup
from pathlib import Path
import fitz
def parse_bytes(filename:str,data:bytes)->str:
    suffix=Path(filename).suffix.lower()
    if suffix=='.pdf':
        doc=fitz.open(stream=data,filetype='pdf');return '\n'.join(p.get_text() for p in doc).strip()
    if suffix in ('.txt','.md'):return data.decode('utf-8',errors='replace').strip()
    if suffix in ('.html','.htm'):return BeautifulSoup(data.decode('utf-8',errors='replace'),'html.parser').get_text(' ',strip=True)
    raise ValueError('Unsupported file type. Upload PDF, TXT, Markdown, or HTML.')
def parse_html_url(url:str)->str:
    import httpx
    from urllib.parse import urlparse
    p=urlparse(url)
    if p.scheme!='https' or not p.netloc or p.username or p.password:raise ValueError('A valid HTTPS URL without embedded credentials is required.')
    r=httpx.get(url,timeout=15,follow_redirects=True,headers={'User-Agent':'SchemeSaarthiResearchBot/1.0'});r.raise_for_status()
    if len(r.content)>5_000_000:raise ValueError('Source exceeds 5 MB limit.')
    return BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
