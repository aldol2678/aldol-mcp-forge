#!/usr/bin/env python3
"""Non-network structural tests for the bundled HTML QA runner."""
import json
import sys
import tempfile
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import html_qa as engine

def assert_check(condition,label):
    assert condition,label
    print('PASS',label)

def main():
    with tempfile.TemporaryDirectory() as t:
        root=Path(t)
        h=root/'sample.html'
        h.write_text('<!doctype html><html><head><title>X</title><meta name="viewport" content="width=device-width"></head><body><h1>ok</h1><script>window.X=1;</script></body></html>')
        files,entry,sha=engine.read_artifact(h)
        checks=[];engine.static_checks(files,entry,checks)
        assert_check(entry=='sample.html' and len(sha)==64,'single HTML ingestion and SHA-256')
        assert_check(not [x for x in checks if x['status']=='FAIL'],'valid HTML static test')
        z=root/'resources.zip'
        with zipfile.ZipFile(z,'w') as f:
            f.writestr('index.html','<!doctype html><html><head><title>T</title><meta name="viewport" content="width=device-width"></head><body><script src="js/main.js"></script></body></html>')
            f.writestr('js/main.js','window.QA_OK=true;')
        files,entry,_=engine.read_artifact(z)
        injected=engine.embed_for_browser(files[entry].decode(),entry,files)
        assert_check('window.QA_OK=true;' in injected,'bundled JS embedded for offline QA')
        unsafe=root/'unsafe.zip'
        with zipfile.ZipFile(unsafe,'w') as f:f.writestr('../escape.html','BAD')
        try:engine.read_artifact(unsafe);raise AssertionError('traversal was accepted')
        except ValueError as e:assert_check('unsafe archive path' in str(e),'ZIP path traversal rejection')
        b={'artifact':{'sha256':'abc'},'checks':[{'id':'a','status':'PASS'},{'id':'b','status':'FAIL'}]}
        c={'artifact':{'sha256':'def'},'checks':[{'id':'a','status':'FAIL'},{'id':'b','status':'PASS'}]}
        comp=engine.compare(b,c,root)
        assert_check(comp['verdict']=='BLOCKED' and len(comp['new_regressions'])==1,'regression PASS-to-FAIL detection')
        assert_check(len(comp['resolved'])==1,'regression FAIL-to-PASS detection')
        comp2=engine.compare(b,b,root)
        assert_check(comp2['verdict']=='NO_REGRESSION_DETECTED' and comp2['identical_input'],'identical-input control')
    print('SELFTEST PASSED: 7 assertions')

if __name__=='__main__':main()
