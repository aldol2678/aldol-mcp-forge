// Trusted local test harness. Sites deploys worker/index.js directly, not this file.
import { createServer } from "node:http";
import { Readable } from "node:stream";
import worker from "../worker/index.js";
const server = createServer(async (incoming, outgoing) => {
  try {
    const request = new Request(`http://127.0.0.1:${server.address().port}${incoming.url}`, {
      method: incoming.method, headers: incoming.headers,
      ...(["GET", "HEAD"].includes(incoming.method) ? {} : { body: Readable.toWeb(incoming), duplex: "half" }),
    });
    const response = await worker.fetch(request);
    outgoing.writeHead(response.status, Object.fromEntries(response.headers));
    outgoing.end(Buffer.from(await response.arrayBuffer()));
  } catch { outgoing.writeHead(500); outgoing.end("Local harness error"); }
});
server.listen(Number(process.env.PORT || 8787), "127.0.0.1", () => console.log(`Listening http://127.0.0.1:${server.address().port}/mcp (local harness; no Sites authentication)`));
