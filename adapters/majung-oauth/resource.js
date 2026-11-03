/**
 * OAuth public resource gateway for MAJUNG MCP.
 * The Python backend remains behind a separate bearer + Service Binding.
 * Only validated, scoped OAuth access tokens can trigger backend requests.
 */
import { OAuthResourceServer, insufficientScope } from "@cloudflare/workers-oauth-provider";

const RESOURCE = "https://aldol-majung-oauth.aldol-lab.workers.dev/mcp";
const ISSUER = "https://aldol-majung-auth.aldol-lab.workers.dev";
const scope = "mcp:read";
const protectedServer = new OAuthResourceServer({
  resourceMetadata: {resource:RESOURCE,authorization_servers:[ISSUER]},
  requiredScopes: [scope],
  validateToken: env => env.AUTH_SERVER.validateToken,
  handler: {
    async fetch(request, env, ctx) {
      if (!ctx.auth?.scope?.includes(scope))
        return insufficientScope(ctx.auth, [scope]);
      if (request.method !== "POST" || new URL(request.url).pathname !== "/mcp")
        return new Response("Not found",{status:404});
      if (!env.BACKEND_BEARER || !env.MAJUNG_BACKEND)
        return new Response("Backend unavailable",{status:503});
      const headers = new Headers(request.headers);
      // Never forward caller OAuth tokens or ambient browser credentials to Python.
      headers.set("Authorization", "Bearer " + env.BACKEND_BEARER);
      for(const name of ["cookie","cf-access-jwt-assertion","cf-authorization","x-forwarded-for","x-real-ip","host"])
        headers.delete(name);
      headers.delete("origin");
      const url = "https://aldol-majung-mcp.aldol-lab.workers.dev/mcp";
      const forwarded = new Request(url, {method:"POST",headers,body:request.body,redirect:"manual"});
      const response=await env.MAJUNG_BACKEND.fetch(forwarded);
      if (response.status>=300&&response.status<400)
        return new Response("Upstream redirect rejected",{status:502});
      const cleanHeaders=new Headers();
      for(const name of ["content-type","cache-control","x-content-type-options"])
        if(response.headers.has(name))cleanHeaders.set(name,response.headers.get(name));
      cleanHeaders.set("cache-control","no-store");
      return new Response(response.body,{status:response.status,headers:cleanHeaders});
    }
  }
});
export default {
  fetch(request,env,ctx) {
    if (new URL(request.url).pathname === "/healthz" && request.method === "GET")
      return Response.json({company:"majung",oauth_gateway:true,healthy:true},{headers:{"cache-control":"no-store"}});
    const origin=request.headers.get("origin");
    if(origin&&origin!==new URL(request.url).origin)
      return Response.json({error:"origin_rejected"},{status:403});
    return protectedServer.fetch(request,env,ctx);
  }
};
