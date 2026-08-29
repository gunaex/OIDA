export default {
  async fetch(request, env) {
    const incoming = new URL(request.url);
    if (incoming.pathname.startsWith("/api/") || incoming.pathname === "/health" || incoming.pathname === "/ready") {
      if (!env.API_ORIGIN || !env.API_ORIGIN.startsWith("https://")) {
        return Response.json({ detail: "Backend origin is not configured" }, { status: 503 });
      }
      const upstream = new URL(incoming.pathname + incoming.search, env.API_ORIGIN);
      const headers = new Headers(request.headers);
      headers.set("X-Forwarded-Host", incoming.host);
      return fetch(new Request(upstream, { method: request.method, headers, body: ["GET","HEAD"].includes(request.method) ? undefined : request.body, redirect: "manual" }));
    }
    return env.ASSETS.fetch(request);
  }
};
