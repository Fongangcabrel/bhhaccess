"""Client address of a request (audit trail)."""
from fastapi import Request


def client_ip(request: Request, trust_proxy: bool = False) -> str | None:
    """The caller's IP. Behind the site's reverse proxy (Nginx), set BHH_TRUST_PROXY_HEADERS=true
    so that the first X-Forwarded-For hop is used; never trust that header otherwise (spoofable).
    """
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded[:45]
        real = request.headers.get("x-real-ip", "").strip()
        if real:
            return real[:45]
    return request.client.host[:45] if request.client else None
