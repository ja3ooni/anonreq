import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";

import { routing } from "./i18n/routing";
import { BASIC_CHALLENGE, checkAdminAccess, isAuditApiPath } from "./lib/admin-gate";
import { checkApiRequest, resolveAllowedHosts } from "./lib/request-guard";

const intl = createMiddleware(routing);

export default async function middleware(request: NextRequest) {
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
    if (isAuditApiPath(request.nextUrl.pathname)) {
      const access = await checkAdminAccess({
        adminFlag: process.env.ANONREQ_UI_ADMIN,
        adminToken: process.env.ANONREQ_UI_ADMIN_TOKEN,
        authorization: request.headers.get("authorization"),
        nodeEnv: process.env.NODE_ENV,
      });
      if (!access.ok) {
        return NextResponse.json(
          { error: { message: access.message, status: access.status } },
          {
            status: access.status,
            headers: {
              "cache-control": "no-store",
              ...(access.status === 401 ? { "www-authenticate": BASIC_CHALLENGE } : {}),
            },
          },
        );
      }
    }
    return NextResponse.next();
  }
  return intl(request);
}

export const config = {
  matcher: ["/api/:path*", "/((?!api|_next|_vercel|.*\\..*).*)"],
};
