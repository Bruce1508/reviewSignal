// Backend-for-frontend proxy for `POST /auth/logout` (`docs/api-spec.md` §15).
// Same relay pattern as `api/login/route.ts`: FastAPI clears the cookie, this route
// carries that `Set-Cookie` back to the browser under the dashboard's own origin.

import { NextResponse } from "next/server";

// Server-side only, like `lib/api.ts`'s `BASE_URL`: the container-internal address
// takes priority when containerized (docs/deployment.md §16).
const API_BASE_URL =
  process.env.API_INTERNAL_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000/api/v1";

export async function POST() {
  const upstream = await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST" });

  const response = new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
  for (const cookie of upstream.headers.getSetCookie()) {
    response.headers.append("Set-Cookie", cookie);
  }
  return response;
}
