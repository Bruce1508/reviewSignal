// Redirects to `/login` when the session cookie is absent (`docs/api-spec.md` §15).
//
// Presence-only: verifying the signature would require `SESSION_SECRET` here, which
// stays server-side-only in the API. A present-but-expired cookie still reaches the
// page, whose fetches then surface `UNAUTHORIZED` from the API itself.

import { NextRequest, NextResponse } from "next/server";

// Must match `core/auth.py`'s `SESSION_COOKIE`.
const SESSION_COOKIE = "rs_session";
const PUBLIC_PATHS = new Set(["/login"]);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.has(pathname) || pathname.startsWith("/api/")) {
    return NextResponse.next();
  }
  if (!request.cookies.get(SESSION_COOKIE)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
