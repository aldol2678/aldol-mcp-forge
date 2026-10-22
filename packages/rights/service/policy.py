"""Shared v0.2 policy wrapper. User records are claims, never legal clearance."""
import sys
import html,re
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core

VERSION = '0.2.0'
LABELS = {'SUITABLE':'조건상 적합','CONFLICT':'조건 충돌','REVIEW':'추가 검토 필요','UNKNOWN':'미확인'}
LICENSES = dict(core.LICENSES)
LICENSES['GPL-3.0-only'] = {'label':'GNU GPL v3 (소스 제공·결합 범위 검토)', 'url':'https://www.gnu.org/licenses/gpl-3.0.en.html'}
LICENSES['GPL-3.0-or-later'] = dict(LICENSES['GPL-3.0-only'])
DISCLAIMER = '입력된 라이선스 조건을 비교한 결과입니다. 법적 사용 승인이나 권리 보유·안전 보증이 아닙니다. 원본 증빙과 별도 권리를 확인하세요.'

def evaluate(asset, usage):
    usage = dict(commercial=False, modified=False, redistribute=True, attribution_planned=False, derivative_license='') | usage
    a = {k:asset.get(k,'') for k in ('asset_id','title','license_id','source_url','evidence_url','creator','license_url')}
    uploaded = bool(asset.get('evidence_path'))
    if uploaded: a['evidence_url'] = a['evidence_url'] or 'https://private-evidence.invalid/recorded'
    lic = a['license_id']
    original_lic = lic
    if lic not in core.LICENSES: a['license_id']='CUSTOM'
    legacy = core._usage(a, **{k:usage[k] for k in ('commercial','modified','redistribute','attribution_planned','derivative_license')})
    missing=[]
    if not asset.get('source_url'): missing.append('출처 URL이 없습니다.')
    if not asset.get('evidence_url') and not uploaded: missing.append('원본 라이선스·허락 증빙이 없습니다.')
    if LICENSES.get(lic,{}).get('attribution') and usage['redistribute'] and not asset.get('creator'): missing.append('표시할 원저작자 정보가 없습니다.')
    reasons=[];conditions=[];reviews=['원본 증빙의 진위, 해당 자산에의 적용 범위, 초상권·상표권 등 별도 권리를 확인하세요.']
    if legacy['blocked_reasons']:
        if lic.startswith('CC-BY-NC') and usage['commercial']: reasons.append('NC 조건과 상업적 사용 목적이 충돌합니다.')
        if '-ND-' in lic and usage['modified'] and usage['redistribute']: reasons.append('ND 조건에서 수정물을 공유하려는 목적이 충돌합니다.')
    if LICENSES.get(lic,{}).get('attribution') and usage['redistribute']:
        conditions.append('저작자·출처·라이선스 링크와 수정 여부를 표시해야 합니다.')
        if not usage['attribution_planned']: reasons.append('출처 표시 의무가 있으나 표시 계획이 없습니다.')
    sa = bool(LICENSES.get(lic,{}).get('share_alike') and usage['modified'] and usage['redistribute'])
    if sa:
        conditions.append('수정물의 동일·호환 라이선스와 적용 범위를 확인해야 합니다.')
        reviews.append('SA 호환성과 수정물 범위는 자동 승인하지 않습니다.')
    manual=not (lic.startswith('CC-') or lic=='CC0-1.0')
    if manual:
        conditions.append({'MIT':'저작권 고지와 라이선스 전문의 포함 여부를 확인하세요.','APACHE-2.0':'라이선스 전문·NOTICE·변경 고지·특허 조건을 검토하세요.','OFL-1.1':'폰트 단독 판매 제한·예약 글꼴명·수정·배포 조건을 검토하세요.'}.get(lic,'계약·소스 제공·결합·재배포 범위를 원문으로 검토하세요.'))
        reviews.append('개별 계약 및 코드·폰트 라이선스의 복합 조건은 사람의 검토가 필요합니다.')
    if reasons: decision='CONFLICT'
    elif lic=='UNKNOWN': decision='UNKNOWN'
    elif missing or manual or sa: decision='REVIEW'
    else: decision='SUITABLE'
    return dict(asset_id=asset['asset_id'],title=asset['title'],license_id=original_lic,decision=decision,status_label=LABELS[decision],
                legacy_status=legacy['status'],legal_clearance=False,checked_at=datetime.now(timezone.utc).isoformat(),engine_version=VERSION,
                basis=[f'사용자 입력 라이선스: {lic}', f"목적: 상업 {usage['commercial']} · 수정 {usage['modified']} · 배포 {usage['redistribute']}", '출처·증빙은 등록된 주장으로 취급하며 자동 진위 확인하지 않습니다.'],
                blocked_reasons=reasons,conditions=conditions,missing_evidence=missing,human_review=reviews,
                confidence='입력 조건 비교: 높음 / 실제 권리 확인: 미검증' if not manual and lic!='UNKNOWN' else '낮음 — 원문·권리 범위 검토 필요',
                license_reference=LICENSES.get(lic,{}).get('url',''),usage=usage,asset_revision=asset.get('revision',1),disclaimer=DISCLAIMER)

def markdown_text(value):
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', html.escape(str(value), quote=False)).replace('\n',' ')

def credits(assets):
    lines=[];missing=[]
    for a in assets:
        values=[a['title'],a.get('creator') or '저작자 미확인',a['license_id'],a.get('source_url') or '출처 누락',a.get('license_url') or LICENSES[a['license_id']].get('url','') or '라이선스 링크 누락']
        lines.append(' | '.join(markdown_text(v) for v in values))
        if not a.get('creator') or not a.get('source_url') or not (a.get('evidence_url') or a.get('evidence_path')): missing.append(a['asset_id'])
    return dict(status='DRAFT_REQUIRES_REVIEW',credits='\n'.join(lines),incomplete=missing,count=len(assets),disclaimer=DISCLAIMER)
