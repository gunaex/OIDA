# Cloud Pilot Final Report

Phase 4.5C provisioned and remotely exercised the hybrid deployment. The transition is preserved as:

`STRUCTURAL_CLOUD_READINESS → REAL_RESOURCE_PROVISIONING → REMOTE_DEPLOYMENT_ACCEPTANCE`

Fly Managed Postgres, the Fly backend, the Cloudflare Worker/static UI, auth/session controls, project isolation, independent-session sharing, backup evidence, migrations, and restart persistence pass. The public URL is `https://oida-pilot-web.gunaex.workers.dev`; the backend origin is `https://oida-2-pilot.fly.dev`.

Live DeepSeek did not pass. A real `deepseek-v4-pro` invocation consumed 6,801 tokens and returned after 72,382 ms, but its payload failed the strict schema with `AI_OUTPUT_INVALID`. A public Worker attempt also produced HTTP 524 before the backend recorded the failed run. OIDA correctly created no authoritative candidate.

Document Again and PM Again are online but blocked by missing OIDA-side credentials. The earlier 4.5B report that remote cloud resources were not configured was correct at that time and is superseded, not erased, by this deployment record.

`POSTGRESQL_COMPATIBILITY=PASS`

`CONTAINER_READINESS=PASS`

`CLOUDFLARE_DEPLOYMENT=PASS`

`REMOTE_MULTI_SESSION_ACCEPTANCE=PASS`

`DEEPSEEK_CLOUD=FAIL`

`CLOUD_GOLDEN_FLOW=FAIL`

`CLOUD_PILOT_REMOTE_READY=NO`

No `v2.0-cloud-pilot` tag is permitted until live AI passes through the public deployment path and the full golden flow completes. Phase 5 has not started.
