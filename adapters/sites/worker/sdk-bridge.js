// Signed, server-to-server Studio -> trusted Python SDK verifier.
// This module must NEVER be exposed as a browser script, or imported into
// page.js. The private secret remains in Sites server environment variables.
import { digest } from "./generator.js";
import { getProject, packageProject, subject, writable } from "./store.js";

const bad = (message, status = 503) => Object.assign(new Error(message), {status});
const encoder = new TextEncoder();
const validId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const hex = arr => [...new Uint8Array(arr)].map(b => b.toString(16).padStart(2, "0")).join("");
const base64 = bytes => {
  let result = "";
  for (let i = 0; i < bytes.length; i += 16384) {
    result += String.fromCharCode(...bytes.subarray(i, i + 16384));
  }
  return btoa(result);
};

export function sdkReady(env) {
  try {
    if (!writable(env) || env.SDK_BRIDGE_ENABLED !== "1" ||
        typeof env.SDK_BRIDGE_SECRET !== "string" || env.SDK_BRIDGE_SECRET.length < 32 ||
        typeof env.SDK_BRIDGE_URL !== "string" ||
        typeof env.SDK_BRIDGE_ORIGIN !== "string") return false;
    const url = new URL(env.SDK_BRIDGE_URL);
    return url.protocol === "https:" && !url.username && !url.password &&
      !url.search && !url.hash && url.pathname === "/v1/sdk/jobs" &&
      url.origin === env.SDK_BRIDGE_ORIGIN;
  } catch {
    return false;
  }
}

async function signedPost(env, endpoint, payload, fetcher) {
  if (!sdkReady(env)) throw bad("Python SDK 실행 호스트가 아직 연결되지 않았습니다.");
  const url = new URL(env.SDK_BRIDGE_URL);
  url.pathname = endpoint;
  const raw = JSON.stringify(payload);
  const timestamp = String(Math.floor(Date.now() / 1000));
  const key = await crypto.subtle.importKey(
    "raw", encoder.encode(env.SDK_BRIDGE_SECRET),
    {name: "HMAC", hash: "SHA-256"}, false, ["sign"],
  );
  const toSign = encoder.encode(timestamp + "\n" + url.pathname + "\n" + raw);
  const signature = hex(await crypto.subtle.sign("HMAC", key, toSign));
  const response = await fetcher(url.toString(), {
    method: "POST",
    redirect: "manual",
    headers: {
      "Content-Type": "application/json",
      "X-Forge-Timestamp": timestamp,
      "X-Forge-Signature": signature,
    },
    body: raw,
    signal: AbortSignal.timeout(25000),
  });
  if (response.redirected || ![200, 202].includes(response.status)) {
    throw bad("공식 SDK 실행 호스트가 작업을 받지 못했습니다.", 502);
  }
  const result = await response.json();
  if (!result || typeof result !== "object") throw bad("SDK 작업 응답이 올바르지 않습니다.", 502);
  return result;
}

function idGuard(id) {
  if (!validId.test(id)) throw bad("프로젝트 식별값이 올바르지 않습니다.", 404);
}

async function ownerPrefix(request) {
  return "studio/v1/" + await digest(subject(request)) + "/";
}

export async function createSdkJob(request, env, projectId, fetcher = fetch) {
  idGuard(projectId);
  subject(request);
  if (!sdkReady(env)) throw bad("공식 SDK 검증 서버를 연결하기 전에는 실행할 수 없습니다.");
  const project = await getProject(request, env, projectId);
  const zip = await packageProject(project); // SHA integrity before external call
  if (zip.bytes.length > 1_000_000) throw bad("SDK 검사 입력 ZIP 용량이 초과됐습니다.", 413);
  const ownerHash = await digest(subject(request));
  const result = await signedPost(env, "/v1/sdk/jobs", {
    subject_hash: ownerHash, project_id: projectId,
    sha256: zip.sha256, zip_base64: base64(zip.bytes),
  }, fetcher);
  if (!/^[0-9a-f]{64}$/.test(result.job_id || "") ||
      result.project_id !== projectId || result.sha256 !== zip.sha256 ||
      !["QUEUED", "RUNNING", "PASS", "FAIL"].includes(result.status)) {
    throw bad("SDK 검증 서버의 작업 식별이 올바르지 않습니다.", 502);
  }
  // Persistent user-owned pointer. Saving a job reference is NOT evidence of PASS.
  const pointer = {job_id: result.job_id, project_id: projectId,
                   sha256: zip.sha256, created_at: Date.now()};
  await env.BUCKET.put((await ownerPrefix(request)) + "sdk-job-latest/" +
    projectId + ".json", JSON.stringify(pointer));
  return { ...result, python_execution: "QUEUED", official_sdk: "UNKNOWN" };
}

export async function readSdkJob(request, env, projectId, fetcher = fetch) {
  idGuard(projectId);
  subject(request);
  if (!sdkReady(env)) {
    return {available: false, official_sdk: "SKIP",
            reason: "공식 SDK 검증 서버가 설정되지 않았습니다."};
  }
  await getProject(request, env, projectId);
  const key = (await ownerPrefix(request)) + "sdk-job-latest/" + projectId + ".json";
  const object = await env.BUCKET.get(key);
  if (!object) return {available: true, status: "NOT_RUN", official_sdk: "UNKNOWN"};
  const pointer = await object.json();
  if (pointer.project_id !== projectId ||
      !/^[0-9a-f]{64}$/.test(pointer.job_id || "")) {
    throw bad("저장된 SDK 작업 참조가 올바르지 않습니다.", 409);
  }
  const result = await signedPost(env, "/v1/sdk/jobs/status", {
    subject_hash: await digest(subject(request)),
    project_id: projectId, job_id: pointer.job_id,
  }, fetcher);
  if (result.job_id !== pointer.job_id || result.project_id !== projectId ||
      result.sha256 !== pointer.sha256 ||
      !["QUEUED", "RUNNING", "PASS", "FAIL", "REJECTED", "TIMEOUT", "INTERRUPTED"].includes(result.status)) {
    throw bad("SDK 검증 결과의 소유권·작업 해시가 일치하지 않습니다.", 502);
  }
  // Only a real signed final execution result can become a PASS.
  const approved = result.status === "PASS" &&
    result.verification?.passed === true &&
    result.verification?.official_sdk === "PASS" &&
    result.verification?.inmemory === "PASS" &&
    result.verification?.stdio === "PASS" &&
    result.verification?.network_used === false;
  return {...result, available: true,
          official_sdk: approved ? "PASS" :
            ["QUEUED", "RUNNING"].includes(result.status) ? "UNKNOWN" : "FAIL",
          python_execution: approved ? "PASS" :
            ["QUEUED", "RUNNING"].includes(result.status) ? "UNKNOWN" : "FAIL"};
}
