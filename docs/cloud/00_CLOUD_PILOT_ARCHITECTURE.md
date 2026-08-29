# Cloud Pilot Architecture

The deployable topology is Cloudflare Worker Static Assets at the public HTTPS hostname, with same-origin `/api`, `/health`, and `/ready` requests proxied to the existing FastAPI container. FastAPI owns application semantics and connects to managed PostgreSQL, the only authoritative cloud database. DeepSeek and external-product calls leave the backend directly.

This preserves the accepted product rather than rewriting it for an edge runtime. Cloudflare supports static assets and edge routing; a Cloudflare Tunnel may protect an origin without exposing an inbound IP, but a stable managed container origin is preferred for the pilot. Long AI requests remain synchronous and require observed timeout testing before production claims.

References: [Cloudflare static assets](https://developers.cloudflare.com/workers/static-assets/binding/), [Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/), [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/setup/).
