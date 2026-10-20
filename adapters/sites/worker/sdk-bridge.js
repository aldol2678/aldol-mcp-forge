// Signed, server-to-server Studio -> trusted Python SDK verifier.
// This module must NEVER be exposed as a browser script, or imported into
// page.js. The private secret remains in Sites server environment variables.
import { digest } from "./generator.js";
import { getProject, packageProject, subject, writable } from "./store.js";

const bad = (message, status = 503) => Object.assign(new Error(message), {status});
const sdkEncoder = new TextEncoder();
const validId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const hex = arr => [...new Uint8Array(arr)].map(b => b.toString(16).padStart(2, "0")).join("");
const base64 = bytes => {
  let result = "";
  for (let i = 0; i < bytes.length; i += 16384) {
    result += String.fromCharCode(...bytes.subarray(i, i + 16384));
  }
  return btoa(result);
};
const googleTokenEndpoint = "https://oauth2.googleapis.com/token";
const tokenCache = new WeakMap();
const b64url = bytes => base64(bytes).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");

function cloudRunCredentials(env) {
  if (env.SDK_BRIDGE_AUTH_MODE !== "google-service-account") throw bad("Cloud Run IAM 인증이 설정되지 않았습니다.");
  const c = JSON.parse(env.SDK_BRIDGE_GOOGLE_CREDENTIALS);
  if (c.type !== "service_account" || c.project_id !== "aram-slack-bridge-2026" ||
      c.client_email !== "forge-sites-invoker@aram-slack-bridge-2026.iam.gserviceaccount.com" ||
      typeof c.private_key !== "string" || !c.private_key.startsWith("-----BEGIN PRIVATE KEY-----\n")) {
    throw bad("Forge 전용 호출 자격증명을 확인해 주세요.");
  }
  return c;
}

async function cloudRunToken(env, fetcher) {
  const c = cloudRunCredentials(env), now = Math.floor(Date.now() / 1000);
  const old = tokenCache.get(env);
  if (old?.credentials === env.SDK_BRIDGE_GOOGLE_CREDENTIALS &&
      old.audience === env.SDK_BRIDGE_ORIGIN && old.exp > now + 60) return old.token;
  try {
    const pkcs8 = Uint8Array.from(atob(c.private_key.replace(/-----[^-]+-----|\s/g, "")), x => x.charCodeAt(0));
    const key = await crypto.subtle.importKey("pkcs8", pkcs8,
      {name:"RSASSA-PKCS1-v1_5", hash:"SHA-256"}, false, ["sign"]);
    const head = b64url(sdkEncoder.encode(JSON.stringify({alg:"RS256",typ:"JWT"})));
    const claims = b64url(sdkEncoder.encode(JSON.stringify({iss:c.client_email,sub:c.client_email,
      aud:googleTokenEndpoint,iat:now,exp:now+600,target_audience:env.SDK_BRIDGE_ORIGIN})));
    const unsigned = head + "." + claims;
    const signature = b64url(new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, sdkEncoder.encode(unsigned))));
    // Fixed Google endpoint only. Never forward HMAC/ZIP/user data or follow a redirect.
    const response = await fetcher(googleTokenEndpoint, {method:"POST",redirect:"manual",
      headers:{"Content-Type":"application/x-www-form-urlencoded"},
      body:new URLSearchParams({grant_type:"urn:ietf:params:oauth:grant-type:jwt-bearer",
        assertion:unsigned+"."+signature}).toString(),signal:AbortSignal.timeout(10000)});
    if (response.status !== 200 || response.redirected) throw Error("token exchange");
    const {id_token:token} = await response.json();
    if (typeof token !== "string" || token.length > 16000 || token.split(".").length !== 3) throw Error("token");
    const middle = token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/");
    const payload = JSON.parse(atob(middle.padEnd(Math.ceil(middle.length/4)*4,"=")));
    // TLS to Google supplies provenance; Cloud Run verifies Google's signature and IAM.
    if (!["accounts.google.com","https://accounts.google.com"].includes(payload.iss) ||
        payload.aud !== env.SDK_BRIDGE_ORIGIN || payload.email !== c.client_email ||
        !Number.isInteger(payload.exp) || payload.exp <= now+60 || payload.exp > now+3700) throw Error("claims");
    tokenCache.set(env,{token,exp:payload.exp,audience:env.SDK_BRIDGE_ORIGIN,credentials:env.SDK_BRIDGE_GOOGLE_CREDENTIALS});
    return token;
  } catch {
    throw bad("Google IAM 인증 토큰을 가져오지 못했습니다.", 502);
  }
}

export function sdkReady(env) {
  try {
    if (!writable(env) || env.SDK_BRIDGE_ENABLED !== "1" ||
        typeof env.SDK_BRIDGE_SECRET !== "string" || env.SDK_BRIDGE_SECRET.length < 32 ||
        typeof env.SDK_BRIDGE_URL !== "string" ||
        typeof env.SDK_BRIDGE_ORIGIN !== "string" ||
        ![undefined, "async", "cloudrun-sync"].includes(env.SDK_BRIDGE_MODE)) return false;
    const url = new URL(env.SDK_BRIDGE_URL);
    if (env.SDK_BRIDGE_MODE === "cloudrun-sync") {
      cloudRunCredentials(env);
      if (!/^https:\/\/forge-sdk-verifier-[a-z0-9-]+(?:\.[a-z0-9-]+)?\.run\.app$/.test(url.origin)) return false;
    }
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
    "raw", sdkEncoder.encode(env.SDK_BRIDGE_SECRET),
    {name: "HMAC", hash: "SHA-256"}, false, ["sign"],
  );
  const toSign = sdkEncoder.encode(timestamp + "\n" + url.pathname + "\n" + raw);
  const signature = hex(await crypto.subtle.sign("HMAC", key, toSign));
  const iam = env.SDK_BRIDGE_MODE === "cloudrun-sync" ?
    {Authorization:"Bearer " + await cloudRunToken(env, fetcher)} : {};
  const response = await fetcher(url.toString(), {
    method: "POST",
    redirect: "manual",
    headers: {
      "Content-Type": "application/json",
      "X-Forge-Timestamp": timestamp,
      "X-Forge-Signature": signature,
      ...iam,
    },
    body: raw,
    signal: AbortSignal.timeout(env.SDK_BRIDGE_MODE === "cloudrun-sync" ? 95000 : 25000),
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

async function reserveSdkBudget(request, env, projectId) {
  // Atomic R2 create-if-absent bounds attempts, including failed requests.
  // No deletes or reset races; separate UTC dates get separate small records.
  const prefix = await ownerPrefix(request) + "sdk-budget/" + new Date().toISOString().slice(0,10) + "/";
  for (let slot = 0; slot < 30; slot++) {
    const saved = await env.BUCKET.put(prefix + slot + ".json",
      JSON.stringify({project_id:projectId,created_at:Date.now()}), {onlyIf:{etagDoesNotMatch:"*"}});
    if (saved) return;
  }
  throw bad("오늘의 공식 SDK 실행 한도(UTC 기준 30회)에 도달했습니다.", 429);
}

export async function createSdkJob(request, env, projectId, fetcher = fetch) {
  idGuard(projectId);
  subject(request);
  if (!sdkReady(env)) throw bad("공식 SDK 검증 서버를 연결하기 전에는 실행할 수 없습니다.");
  const project = await getProject(request, env, projectId);
  const zip = await packageProject(project); // SHA integrity before external call
  if (zip.bytes.length > 1_000_000) throw bad("SDK 검사 입력 ZIP 용량이 초과됐습니다.", 413);
  const ownerHash = await digest(subject(request));
  if (env.SDK_BRIDGE_MODE === "cloudrun-sync") {
    const cached = await readSdkJob(request, env, projectId);
    if (cached.sha256 === zip.sha256 && ["PASS", "FAIL"].includes(cached.status)) return cached;
    await reserveSdkBudget(request, env, projectId);
  }
  const result = await signedPost(env, "/v1/sdk/jobs", {
    subject_hash: ownerHash, project_id: projectId,
    sha256: zip.sha256, zip_base64: base64(zip.bytes),
  }, fetcher);
  if (!/^[0-9a-f]{64}$/.test(result.job_id || "") ||
      result.project_id !== projectId || result.sha256 !== zip.sha256 ||
      !["QUEUED", "RUNNING", "PASS", "FAIL", "REJECTED", "TIMEOUT", "INTERRUPTED"].includes(result.status)) {
    throw bad("SDK 검증 서버의 작업 식별이 올바르지 않습니다.", 502);
  }
  // Cloud Run request-based CPU: complete SDK validation before returning.
  // Only signed verified final evidence can be saved in owner-scoped Sites R2.
  const normalized = normalizeSdkResult(result);
  if (env.SDK_BRIDGE_MODE === "cloudrun-sync") {
    const expected = await digest(ownerHash + ":" + projectId + ":" + zip.sha256);
    if (result.job_id !== expected || !["PASS", "FAIL", "TIMEOUT"].includes(result.status)) {
      throw bad("Cloud Run 공식 SDK 검증 결과가 완결되지 않았습니다.", 502);
    }
  }
  // Durable project-owned result/pointer, never client-controlled.
  const pointer = {job_id: result.job_id, project_id: projectId,
                   sha256: zip.sha256, created_at: Date.now(),
                   ...(env.SDK_BRIDGE_MODE === "cloudrun-sync" ? {final_result: normalized} : {})};
  await env.BUCKET.put((await ownerPrefix(request)) + "sdk-job-latest/" +
    projectId + ".json", JSON.stringify(pointer));
  return normalized;
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
  if (env.SDK_BRIDGE_MODE === "cloudrun-sync") {
    const expected = await digest(await digest(subject(request)) + ":" + projectId + ":" + pointer.sha256);
    if (pointer.job_id !== expected || !pointer.final_result ||
        pointer.final_result.job_id !== expected ||
        pointer.final_result.project_id !== projectId ||
        pointer.final_result.sha256 !== pointer.sha256) {
      throw bad("SDK 실행 결과의 소유자·파일 해시가 일치하지 않습니다.", 409);
    }
    return {...normalizeSdkResult(pointer.final_result), available: true};
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
  return normalizeSdkResult({...result, available: true});
}

function normalizeSdkResult(result) {
  // Only authenticated final execution evidence for SDK v2 can become PASS.
  const approved = result.status === "PASS" &&
    result.verification?.passed === true &&
    result.verification?.official_sdk === "PASS" &&
    result.verification?.inmemory === "PASS" &&
    result.verification?.stdio === "PASS" &&
    result.verification?.network_used === false &&
    result.verification?.sdk_version === "2.0.0";
  const status = result.status === "PASS" && !approved ? "FAIL" :
    result.status === "REJECTED" ? "FAIL" :
    result.status === "INTERRUPTED" ? "UNKNOWN" : result.status;
  return {...result, status, official_sdk: status, python_execution: status,
    reason: result.status === "INTERRUPTED" ? "실행 호스트가 재시작되어 결과를 확인할 수 없습니다." :
      result.status === "PASS" && !approved ? "공식 SDK v2 실행 증거가 완전하지 않습니다." : result.reason};
}
