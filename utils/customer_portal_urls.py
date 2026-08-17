# utils/customer_portal_urls.py — URL cổng khách hàng (Service C)
from __future__ import annotations

CUSTOMER_PORTAL_ORIGIN = "https://khachhang.daugiathongminh.vn"


def normalize_company_slug(company_code: str) -> str:
    return (company_code or "").strip().lower()


def customer_portal_url(company_code: str, *path_parts: str) -> str:
    """
    Ví dụ:
      customer_portal_url("kinhdo") → https://khachhang.daugiathongminh.vn/kinhdo
      customer_portal_url("kinhdo", "buy") → …/kinhdo/buy
    """
    slug = normalize_company_slug(company_code)
    if not slug:
        return CUSTOMER_PORTAL_ORIGIN
    url = f"{CUSTOMER_PORTAL_ORIGIN}/{slug}"
    for part in path_parts:
        p = (part or "").strip("/")
        if p:
            url = f"{url}/{p}"
    return url


def customer_portal_link_set(company_code: str) -> dict[str, str]:
    slug = normalize_company_slug(company_code)
    if not slug:
        return {}
    return {
        "portal_home_url": customer_portal_url(slug),
        "portal_buy_url": customer_portal_url(slug, "buy"),
        "portal_deposit_url": customer_portal_url(slug, "deposit"),
    }
