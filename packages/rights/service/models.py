from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from policy import LICENSES
from core import _safe_url

class Usage(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    commercial:bool=False
    modified:bool=False
    redistribute:bool=True
    attribution_planned:bool=False
    derivative_license:str=Field(default='',max_length=50)

class AssetInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    asset_id:UUID
    title:str=Field(min_length=1,max_length=300)
    kind:str
    license_id:str='UNKNOWN'
    creator:str=Field(default='',max_length=512)
    rights_holder:str=Field(default='',max_length=512)
    source_url:str=Field(default='',max_length=2048)
    evidence_url:str=Field(default='',max_length=2048)
    license_url:str=Field(default='',max_length=2048)
    project:str=Field(default='',max_length=120)
    notes:str=Field(default='',max_length=4096)
    usage:Usage=Field(default_factory=Usage)
    archived:bool=False
    @field_validator('title')
    @classmethod
    def title_valid(cls,v):
        if not v.strip():raise ValueError('이름을 입력하세요.')
        return v.strip()
    @field_validator('kind')
    @classmethod
    def kind_valid(cls,v):
        if v not in ('image','audio','video','font','3d','code','text','other'): raise ValueError('지원하지 않는 자산 분류입니다.')
        return v
    @field_validator('license_id')
    @classmethod
    def license_valid(cls,v):
        if v not in LICENSES:raise ValueError('지원하지 않는 라이선스입니다. CUSTOM 또는 UNKNOWN으로 등록하세요.')
        return v
    @field_validator('source_url','evidence_url','license_url')
    @classmethod
    def url_valid(cls,v):
        if not _safe_url(v):raise ValueError('HTTPS URL만 허용하며 URL 내 비밀번호는 금지합니다.')
        return v

class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=8,max_length=128)

class CheckInput(BaseModel):
    check_id:UUID
    usage:Usage

class KeyInput(BaseModel):
    label:str=Field(default='ChatGPT',min_length=1,max_length=80)
    days:int=Field(default=30,ge=1,le=90)
