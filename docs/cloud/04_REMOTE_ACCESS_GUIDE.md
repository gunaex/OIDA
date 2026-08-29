# Remote Access Guide

Open the single Cloudflare HTTPS hostname, sign in with the authorized pilot account, and verify the Project workspace. A second browser/device signs in independently and must see the same projects because identity/project truth is in PostgreSQL and the session is a signed cookie—not a copied local file.

If login loops, verify Worker API proxying, cookie Secure/SameSite behavior, allowed origin, and backend clock. If `/health` works but `/ready` fails, inspect database connectivity/config. AI readiness is proven only by an actual generation, never health alone.
