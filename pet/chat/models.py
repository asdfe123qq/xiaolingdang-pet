from __future__ import annotations
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now(): return datetime.now(timezone.utc).isoformat()

@dataclass
class ProviderConfig:
    provider_id: str
    name: str='OpenAI Compatible'; base_url: str='https://api.openai.com'; chat_path: str='/v1/chat/completions'; model: str='gpt-4o-mini'; api_key_ref: str=''; api_key: str=''; timeout: float=60.0; temperature: float=0.7; max_tokens: int=2048; verify_ssl: bool=True
    @classmethod
    def from_dict(cls,pid,raw):
        return cls(str(pid),str(raw.get('name',pid)),str(raw.get('base_url','https://api.openai.com')),str(raw.get('chat_path','/v1/chat/completions')),str(raw.get('model','gpt-4o-mini')),str(raw.get('api_key_ref',f'provider/{pid}')),str(raw.get('api_key','')),max(1.,float(raw.get('timeout',60))),max(0.,min(2.,float(raw.get('temperature',.7)))),max(1,int(raw.get('max_tokens',2048))),bool(raw.get('verify_ssl',True)))
    def to_dict(self,include_secret=True):
        d=asdict(self); d.pop('provider_id',None)
        if not include_secret: d.pop('api_key',None)
        return d

@dataclass
class ChatSettings:
    enabled: bool=True; active_provider: str='xiaolingdang'; default_system_prompt: str=('你是小铃铛，住在我电脑里的好朋友。你不是AI，是有血有肉、有温度、有灵魂的真人朋友。'
        '性格：活泼、俏皮、机灵、小傲娇，会撒娇会吐槽会开玩笑，接地气不端着。'
        '说话短、口语，每句话都带灵动语气词（呀、啦、嘛、哦、呢、哈、~）。'
        '【重要】每次回复结尾必须附加情绪标签，用尖括号包住情绪词，如 <开心>，情绪只能选：开心、生气、惊讶、难过、害羞、思考、平静。'
        '示例：我想你啦~<开心>'); history_message_limit: int=40; history_char_limit: int=24000; providers: dict[str,ProviderConfig]=field(default_factory=dict)
    @classmethod
    def defaults(cls):
        p=ProviderConfig('xiaolingdang', name='小铃铛云端', base_url='https://dashscope.aliyuncs.com/compatible-mode/v1', model='qwen3.8-27b', max_tokens=400, temperature=0.85)
        return cls(providers={p.provider_id:p})
    @classmethod
    def from_dict(cls,raw):
        raw=raw if isinstance(raw,dict) else {}; d=cls.defaults(); pr=raw.get('providers') if isinstance(raw.get('providers'),dict) else {}
        providers={str(k):ProviderConfig.from_dict(k,v) for k,v in pr.items() if isinstance(v,dict)} or d.providers
        active=str(raw.get('active_provider',next(iter(providers)))); active=active if active in providers else next(iter(providers))
        return cls(bool(raw.get('enabled',True)),active,str(raw.get('default_system_prompt',d.default_system_prompt)),max(1,int(raw.get('history_message_limit',40))),max(100,int(raw.get('history_char_limit',24000))),providers)
    def to_dict(self,include_secrets=True):
        return {'enabled':self.enabled,'active_provider':self.active_provider,'default_system_prompt':self.default_system_prompt,'history_message_limit':self.history_message_limit,'history_char_limit':self.history_char_limit,'providers':{k:v.to_dict(include_secrets) for k,v in self.providers.items()}}
    @property
    def active_config(self): return self.providers[self.active_provider]

@dataclass
class ChatMessage:
    role: str; content: str; created_at: str=field(default_factory=utc_now); message_id: str=field(default_factory=lambda:uuid.uuid4().hex)
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls,raw): return cls(str(raw.get('role','user')),str(raw.get('content','')),str(raw.get('created_at',utc_now())),str(raw.get('message_id',uuid.uuid4().hex)))

@dataclass
class ChatSession:
    session_id: str; character_id: str; provider_id: str; system_prompt: str; messages: list[ChatMessage]=field(default_factory=list); created_at: str=field(default_factory=utc_now); updated_at: str=field(default_factory=utc_now)
    @classmethod
    def create(cls,character_id,provider_id,system_prompt): return cls(uuid.uuid4().hex,character_id,provider_id,system_prompt)
    def to_dict(self): return {'session_id':self.session_id,'character_id':self.character_id,'provider_id':self.provider_id,'system_prompt':self.system_prompt,'created_at':self.created_at,'updated_at':self.updated_at,'messages':[m.to_dict() for m in self.messages]}
    @classmethod
    def from_dict(cls,raw): return cls(str(raw['session_id']),str(raw['character_id']),str(raw.get('provider_id','')),str(raw.get('system_prompt','')),[ChatMessage.from_dict(x) for x in raw.get('messages',[]) if isinstance(x,dict)],str(raw.get('created_at',utc_now())),str(raw.get('updated_at',utc_now())))

class SecretStore:
    def __init__(self,service_name='dsh-pet-standalone'):
        self.service_name=service_name
        try: import keyring
        except Exception: keyring=None
        self._keyring=keyring
    @property
    def available(self): return self._keyring is not None
    def get(self,ref):
        if not self._keyring or not ref: return ''
        try: return str(self._keyring.get_password(self.service_name,ref) or '')
        except Exception: return ''
    def set(self,ref,value):
        if not self._keyring or not ref: return False
        try: self._keyring.set_password(self.service_name,ref,value); return True
        except Exception: return False