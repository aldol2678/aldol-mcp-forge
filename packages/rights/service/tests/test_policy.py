import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from policy import evaluate

def asset(license_id='CC-BY-4.0', **overrides):
    return dict(asset_id='a',title='테스트',kind='image',license_id=license_id,creator='저작자',source_url='https://example.org/a',evidence_url='https://example.org/license',license_url='', **overrides)

def test_four_states_and_no_legal_approval():
    assert evaluate(asset(),dict(attribution_planned=True))['decision']=='SUITABLE'
    assert evaluate(asset('CC-BY-NC-4.0'),dict(commercial=True))['decision']=='CONFLICT'
    assert evaluate(asset('MIT'),{})['decision']=='REVIEW'
    assert evaluate(asset('UNKNOWN'),{})['decision']=='UNKNOWN'
    for lic in ['CC-BY-4.0','CUSTOM','GPL-3.0-only','OFL-1.1']:
        r=evaluate(asset(lic),{})
        assert r['legal_clearance'] is False and r['checked_at'] and r['basis'] and r['conditions'] is not None

def test_sa_and_missing_evidence_never_green():
    r=evaluate(asset('CC-BY-SA-4.0'),dict(modified=True,redistribute=True,attribution_planned=True,derivative_license='CC-BY-SA-4.0'))
    assert r['decision']=='REVIEW'
    a=asset(); a['evidence_url']=''
    assert evaluate(a,dict(attribution_planned=True))['decision']=='REVIEW'

def test_nd_private_modification_and_attribution_conflict():
    assert evaluate(asset('CC-BY-ND-4.0'),dict(modified=True,redistribute=False))['decision']!='CONFLICT'
    assert evaluate(asset(),dict(attribution_planned=False))['decision']=='CONFLICT'

def test_uploaded_proof_is_not_authenticity_guarantee():
    a=asset(); a['evidence_url']='';a['evidence_path']='user/a/proof.pdf'
    r=evaluate(a,dict(attribution_planned=True))
    assert r['legal_clearance'] is False and '원본' in ' '.join(r['human_review'])

def test_exported_credits_do_not_render_user_html_or_markdown_images():
    from policy import credits
    a=asset();a['title']='<img src=https://attacker.invalid> ![x](https://attacker.invalid/a)'
    rendered=credits([a])['credits']
    assert '<img' not in rendered and '![' not in rendered
