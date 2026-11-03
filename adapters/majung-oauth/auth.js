/**
 * ALDOL MAJUNG authorization server (OAuth Provider 1.1.0).
 *
 * The *only* OAuth grant entrypoint is /authorize, which must be protected
 * by Cloudflare Access with a single-owner email policy. Without verified
 * ctx.access identity it fails closed, even if the Access edge rule is absent.
 * Token, metadata and client registration endpoints remain public as OAuth
 * requires. Client registration NEVER grants user permission.
 */
import { OAuthAuthorizationServer, AuthorizationError } from "@cloudflare/workers-oauth-provider";
import { WorkerEntrypoint } from "cloudflare:workers";

const ISSUER = "https://aldol-majung-auth.aldol-lab.workers.dev";
const RESOURCE = "https://aldol-majung-oauth.aldol-lab.workers.dev/mcp";
const SCOPE = "mcp:read";
const authorizationServer = new OAuthAuthorizationServer({
  issuer: ISSUER,
  resources: [RESOURCE],
  authorizeEndpoint: "/authorize",
  tokenEndpoint: "/oauth/token",
  defaultResource: RESOURCE,
  scopesSupported: [SCOPE, "offline_access"],
  clientIdMetadataDocumentEnabled: true,
  clientRegistrationEndpoint: "/oauth/register",
});
const htmlHeaders = {
  "content-type": "text/html; charset=utf-8",
  "cache-control": "no-store, private",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
  "x-frame-options": "DENY",
  "content-security-policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; style-src 'unsafe-inline'",
};
const esc = value => String(value ?? "").replace(/[&<>"']/g, c =>
  ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[c]);
const unauthorized = () => new Response("Cloudflare Access login required", {
  status: 403, headers: {"cache-control":"no-store"}
});
function page(details, handle) {
  const requested = details.scope || [];
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>마중 MCP 연결 승인</title></head>
  <body style="font:16px system-ui;max-width:460px;margin:9vh auto;padding:24px">
   <h1>마중 MCP 연결 승인</h1>
   <p><strong>${esc(details.clientName)}</strong>에서 마중 MCP 접근을 요청했어요.</p>
   <p>인증 정보를 전달받을 앱: <strong>${esc(details.redirectHost)}</strong></p>
   ${details.redirectIsLoopback?"<p>이 연결은 로컬 앱으로 인증 결과를 전달합니다.</p>":""}
   <form method="post" action="/authorize">
    <input type="hidden" name="handle" value="${esc(handle)}">
    ${requested.filter(s=>s===SCOPE||s==="offline_access").map(s=>
      `<label style="display:block;margin:12px 0"><input name="scope" type="checkbox" value="${esc(s)}" ${s===SCOPE?"checked":""}> ${esc(s)}</label>`).join("")}
    <p>허용 시 위 앱이 시장조사·경쟁분석·사업성 평가 도구를 사용할 수 있습니다. 실시간 검색은 별도로 잠겨 있습니다.</p>
    <button name="decision" value="approve" type="submit">허용</button>
    <button name="decision" value="deny" type="submit">취소</button>
   </form>
  </body></html>`;
}
async function authorize(request, env, context) {
  // Never accept a user-selected principal or an unsigned identity header.
  const access = context?.access;
  if (!access) return unauthorized();
  const identity = await access.getIdentity();
  if (!identity?.email || typeof identity.email !== "string") return unauthorized();
  const oauth = authorizationServer.getOAuthApi(env);
  if (request.method === "GET") {
    let parsed;
    try { parsed = await oauth.parseAuthRequest(request); }
    catch (error) {
      if (!(error instanceof AuthorizationError)) throw error;
      if (error.redirectTo) return Response.redirect(error.redirectTo, 302);
      return new Response("Invalid OAuth authorization request", {status:400, headers:htmlHeaders});
    }
    const details = await oauth.describeConsent(parsed);
    const consent = await oauth.beginConsent(parsed);
    const h = new Headers(consent.headers);
    for (const [key,value] of Object.entries(htmlHeaders)) h.set(key,value);
    return new Response(page(details, consent.handle), {status:200, headers:h});
  }
  if (request.method === "POST") {
    const raw = request.headers.get("content-length");
    if (raw && Number(raw)>8192) return new Response("Request too large",{status:413});
    const form = await request.formData();
    const handle = form.get("handle");
    if (typeof handle !== "string" || handle.length>512) return new Response("Invalid handle",{status:400});
    if (form.get("decision") !== "approve") {
      const denied = await oauth.denyConsent(request, handle);
      return new Response(null, {status:302,headers:denied.headers});
    }
    const selected = form.getAll("scope").map(String);
    if (!selected.includes(SCOPE) || selected.some(s=>s!==SCOPE&&s!=="offline_access"))
      return new Response("Required scope not granted", {status:400,headers:htmlHeaders});
    const approved = await oauth.approveConsent(request,handle,{scope:selected});
    if (!approved.request.scope.includes(SCOPE))
      return new Response("Scope mismatch",{status:400,headers:htmlHeaders});
    const {redirectTo} = await oauth.completeAuthorization({
      request: approved.request,
      userId: identity.email.toLowerCase(),
      metadata: {},
      scope: approved.request.scope,
      props: {userId:identity.email.toLowerCase()},
    });
    const h = new Headers(approved.headers);
    h.set("Location", redirectTo);
    h.set("cache-control","no-store");
    return new Response(null,{status:302,headers:h});
  }
  return new Response("Method not allowed",{status:405});
}
export class AuthServer extends WorkerEntrypoint {
  async fetch(request) {
    if (new URL(request.url).pathname === "/authorize")
      return authorize(request, this.env, this.ctx);
    return authorizationServer.fetch(request,this.env,this.ctx);
  }
  validateToken(resource, token) {
    return authorizationServer.validateToken(resource, token, this.env);
  }
}
export default AuthServer;
