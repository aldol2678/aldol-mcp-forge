"""Explicit remote acceptance probe. Token is read from a local secret file, never logged."""

import argparse
import asyncio
import base64
import datetime
import io
import json
from pathlib import Path
import zipfile
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main(args):
    token = Path(args.token_file).read_text().strip()
    headers = {"Authorization": "Bearer " + token}
    base = args.url.removesuffix("/mcp")
    evidence = {
        "endpoint": args.url,
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    async with httpx2.AsyncClient(timeout=45) as client:
        evidence["health"] = (await client.get(base + "/healthz")).status_code
        evidence["unauthenticated"] = (await client.post(args.url)).status_code
        evidence["incorrect_token"] = (
            await client.post(args.url, headers={"Authorization": "Bearer incorrect"})
        ).status_code
        assert evidence["health"] == 200
        assert evidence["unauthenticated"] == evidence["incorrect_token"] == 401
    async with httpx2.AsyncClient(headers=headers, timeout=45) as client:
        async with streamable_http_client(args.url, http_client=client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                evidence["tools"] = [x.name for x in (await session.list_tools()).tools]
                assert len(evidence["tools"]) == 9
                inventory = await call("list_games", {"query": "군단"})
                assert inventory["total"] >= 1 and inventory["verification"] == "UNVERIFIED"
                resume = await call("get_game_resume", {"game_id": "tiny-army-expedition"})
                assert resume["release_readiness"] == "UNKNOWN"

                async def call(name, arguments):
                    r = await session.call_tool(name, arguments)
                    assert not r.is_error, str(r)
                    return json.loads(r.content[0].text)

                content = b'<!doctype html><title>Remote QA</title><meta name="viewport" content="width=device-width"><script>window.QA_OK=true;</script>'
                artifact = {
                    "filename": "remote.html",
                    "content_base64": base64.b64encode(content).decode(),
                }
                evidence["html"] = await call("run_static_qa", {"artifact": artifact})
                b = io.BytesIO()
                with zipfile.ZipFile(b, "w") as z:
                    z.writestr("index.html", content)
                evidence["zip"] = await call(
                    "inspect_game_artifact",
                    {
                        "artifact": {
                            "filename": "remote.zip",
                            "content_base64": base64.b64encode(b.getvalue()).decode(),
                        }
                    },
                )
                evidence["report_readback"] = (
                    await call("get_qa_report", {"qa_id": evidence["html"]["qa_id"]})
                    == evidence["html"]
                )
                evidence["regression"] = await call(
                    "compare_game_versions",
                    {
                        "baseline_id": evidence["html"]["qa_id"],
                        "candidate_id": evidence["html"]["qa_id"],
                    },
                )
                bad = {
                    "filename": "bad.html",
                    "content_base64": base64.b64encode(b"<title>Bad</title>").decode(),
                }
                failed = await call("run_static_qa", {"artifact": bad})
                evidence["regression_detected"] = await call(
                    "compare_game_versions",
                    {
                        "baseline_id": evidence["html"]["qa_id"],
                        "candidate_id": failed["qa_id"],
                    },
                )
                assert evidence["regression_detected"]["status"] == "FAIL"
                uncertain = {
                    "filename": "uncertain.html",
                    "content_base64": base64.b64encode(
                        b'<title>Bad</title><script src="https://example.com/external.js"></script>'
                    ).decode(),
                }
                uncertain_report = await call("run_static_qa", {"artifact": uncertain})
                evidence["masked_unknown"] = await call(
                    "compare_game_versions",
                    {
                        "baseline_id": failed["qa_id"],
                        "candidate_id": uncertain_report["qa_id"],
                    },
                )
                assert evidence["masked_unknown"]["status"] == "UNKNOWN"
                evidence["browser"] = await call(
                    "run_browser_qa", {"artifact": artifact}
                )
                evidence["scenarios"] = await call(
                    "run_game_scenarios",
                    {"artifact": artifact, "profile": {"scenarios": []}},
                )
                evidence["path_rejected"] = (
                    await session.call_tool(
                        "inspect_game_artifact",
                        {"artifact": {"filename": "x.html", "path": "/etc/passwd"}},
                    )
                ).is_error
                assert evidence["html"]["status"] == evidence["zip"]["status"] == "PASS"
                assert evidence["report_readback"] and evidence["path_rejected"]
                assert evidence["regression"]["status"] == "PASS"
                assert (
                    evidence["browser"]["status"]
                    == evidence["scenarios"]["status"]
                    == "UNKNOWN"
                )
    Path(args.output).write_text(json.dumps(evidence, indent=2))
    print(
        json.dumps(
            {
                "health": evidence["health"],
                "unauthenticated": evidence["unauthenticated"],
                "tools": evidence["tools"],
                "html": evidence["html"]["status"],
                "zip": evidence["zip"]["status"],
                "readback": evidence["report_readback"],
                "browser": evidence["browser"]["status"],
            }
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--token-file", required=True)
    p.add_argument("--output", required=True)
    asyncio.run(main(p.parse_args()))
