import base64
import io
import json
from pathlib import Path
import sys
import zipfile
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HTML = '<!doctype html><title>Test</title><meta name="viewport" content="width=device-width"><button id="go" style="width:48px;height:48px">Go</button><script>window.OK=1</script>'


def upload(text=HTML, filename="index.html"):
    return {
        "filename": filename,
        "content_base64": base64.b64encode(text.encode()).decode(),
    }


def zipped(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, data in entries:
            z.writestr(name, data)
    return {
        "filename": "game.zip",
        "content_base64": base64.b64encode(b.getvalue()).decode(),
    }


@pytest.fixture
def svc(tmp_path):
    from service import QAService

    return QAService(tmp_path / "artifacts", tmp_path / "reports", remote=True)


def test_html_report_readback(svc):
    r = svc.run_static_qa(upload())
    assert r["status"] == "PASS"
    assert r["artifact"]["sha256"] and svc.get_qa_report(r["qa_id"]) == r
    assert r["coverage"]["browser"] == "UNKNOWN"


def test_static_fail_unknown(svc):
    assert svc.run_static_qa(upload("<title>x</title>"))["status"] == "FAIL"
    assert (
        svc.run_static_qa(
            upload(HTML + '<script src="https://example.com/x.js"></script>')
        )["status"]
        == "UNKNOWN"
    )


def test_zip_and_hash(svc):
    r = svc.inspect_game_artifact(
        zipped([("index.html", HTML), ("main.js", "let x=1")])
    )
    assert r["status"] == "PASS" and r["artifact"]["files_count"] == 2
    with pytest.raises(ValueError):
        svc.inspect_game_artifact({**upload(), "expected_sha256": "0" * 64})


@pytest.mark.parametrize(
    "name", ["../x.html", "/x.html", "C:/x.html", "a\\x.html", "a/../x.html"]
)
def test_bad_zip_paths(svc, name):
    with pytest.raises(ValueError):
        svc.inspect_game_artifact(zipped([(name, HTML)]))


def test_duplicate_zip(svc):
    with pytest.raises(ValueError):
        svc.inspect_game_artifact(zipped([("index.html", HTML), ("index.html", HTML)]))


@pytest.mark.parametrize(
    "value",
    [
        {"filename": "x.html", "path": "/etc/passwd"},
        {"filename": "x.html", "content_base64": "@@@"},
        upload(filename="../x.html"),
        upload(filename="x.exe"),
        {"filename": "x.zip", "content_base64": "aGVsbG8="},
    ],
)
def test_bad_inputs(svc, value):
    with pytest.raises(ValueError):
        svc.inspect_game_artifact(value)


def test_no_remote_browser(svc):
    r = svc.run_browser_qa(upload())
    assert r["status"] == "UNKNOWN" and r["blocked"] is True
    assert svc.run_game_scenarios(upload(), {"scenarios": []})["status"] == "UNKNOWN"


def test_regression(svc):
    b = svc.run_static_qa(upload())
    c = svc.run_static_qa(upload("<title>x</title>"))
    r = svc.compare_game_versions(b["qa_id"], c["qa_id"])
    assert r["status"] == "FAIL" and r["new_regressions"]
    assert svc.compare_game_versions(b["qa_id"], b["qa_id"])["status"] == "PASS"
    inspect = svc.inspect_game_artifact(upload())
    assert (
        svc.compare_game_versions(b["qa_id"], inspect["qa_id"])["status"] == "UNKNOWN"
    )


def test_report_id_confined(svc):
    with pytest.raises(ValueError):
        svc.get_qa_report("../anything")


def test_local_paths_confined(tmp_path):
    from service import QAService

    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "ok.html").write_text(HTML)
    (tmp_path / "secret.html").write_text(HTML)
    (root / "link.html").symlink_to(tmp_path / "secret.html")
    s = QAService(root, tmp_path / "reports")
    assert (
        s.inspect_game_artifact({"filename": "ok.html", "path": "ok.html"})["status"]
        == "PASS"
    )
    for name in ["../secret.html", "link.html"]:
        with pytest.raises(ValueError):
            s.inspect_game_artifact({"filename": "x.html", "path": name})


def test_zip_limits_and_links(svc):
    with pytest.raises(ValueError):
        svc.inspect_game_artifact(
            zipped([("index.html", HTML)] + [(f"{i}.txt", "x") for i in range(100)])
        )
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.html", "x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError):
        svc.inspect_game_artifact(
            {
                "filename": "game.zip",
                "content_base64": base64.b64encode(b.getvalue()).decode(),
            }
        )
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        i = zipfile.ZipInfo("index.html")
        i.external_attr = 0o120777 << 16
        z.writestr(i, "target")
    with pytest.raises(ValueError):
        svc.inspect_game_artifact(
            {
                "filename": "game.zip",
                "content_base64": base64.b64encode(b.getvalue()).decode(),
            }
        )


def test_report_retention(svc):
    import os, time

    r = svc.inspect_game_artifact(upload())
    p = svc.report_root / (r["qa_id"] + ".json")
    os.utime(p, (time.time() - 90000, time.time() - 90000))
    with pytest.raises(ValueError):
        svc.get_qa_report(r["qa_id"])
    svc.inspect_game_artifact(upload())
    assert not p.exists()


def test_different_profiles_unknown(tmp_path):
    from service import QAService

    s = QAService(tmp_path, tmp_path / "reports", remote=True)
    a = s.run_browser_qa(upload(), {"viewports": ["mobile390"]})
    b = s.run_browser_qa(upload(), {"viewports": ["desktop"]})
    assert s.compare_game_versions(a["qa_id"], b["qa_id"])["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "profile",
    [
        {"viewports": ["bad"]},
        {"scenarios": [{"id": "../evil", "steps": []}]},
        {
            "scenarios": [
                {"id": "ok", "steps": [{"action": "evaluate", "code": "evil"}]}
            ]
        },
    ],
)
def test_profile_rejection(svc, profile):
    with pytest.raises(ValueError):
        svc.run_game_scenarios(upload(), profile)


def test_script_not_executed(svc, tmp_path):
    marker = tmp_path / "executed.txt"
    js = f"require('fs').writeFileSync({json.dumps(str(marker))},'executed')"
    r = svc.run_static_qa(upload(HTML + "<script>" + js + "</script>"))
    assert r["status"] == "PASS" and not marker.exists()


def test_js_syntax_failure(svc):
    r = svc.run_static_qa(upload(HTML + "<script>const = ;</script>"))
    assert r["status"] == "FAIL" and any(
        c["id"].startswith("static.js") and c["status"] == "FAIL" for c in r["checks"]
    )
