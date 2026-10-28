import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";

import { routing } from "./i18n/routing";
import { checkApiRequest, resolveAllowedHosts } from "./lib/request-guard";

const intl = createMiddleware(routing);

export default function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/api/") || request.nextUrl.pathname === "/api") {
    const result = checkApiRequest({
      method: request.method,
      host: request.headers.get("host"),
      origin: request.headers.get("origin"),
      secFetchSite: request.headers.get("sec-fetch-site"),
      allowedHosts: resolveAllowedHosts(process.env.ANONREQ_ALLOWED_HOSTS, process.env.PORT),
    });
    if (!result.ok) {
      return NextResponse.json({ error: result.message }, { status: result.status });
    }
    return NextResponse.next();
  }
  return intl(request);
}

export const config = {
  matcher: ["/api/:path*", "/((?!api|_next|_vercel|.*\\..*).*)"],
};
