// Backend-for-frontend proxy for `POST /auth/login` (`docs/api-spec.md` §15).
//
// The browser calls this route, not the API directly: a same-origin call needs no
// CORS decision (still undecided per `docs/api-spec.md` §15), and relaying FastAPI's
// `Set-Cookie` verbatim scopes the cookie to the dashboard's own origin, since the
// header carries no `Domain` attribute — the browser binds it to whichever response
// carried it, which is this one.

import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const upstream = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });

  const response = new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
  for (const cookie of upstream.headers.getSetCookie()) {
    response.headers.append("Set-Cookie", cookie);
  }
  return response;
}
