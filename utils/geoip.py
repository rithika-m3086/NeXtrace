"""Lightweight GeoIP resolution for attacker source IPs.

Uses the free, key-less ip-api.com batch endpoint to resolve public IPs to a
country / city / ISP / lat-long so the UI can pin attacker origins on a map and
contrast them with normal developer geography. Private / reserved ranges are
skipped. Results are cached in-process; failures degrade silently (the map is a
nice-to-have, never a blocker).
"""

from __future__ import annotations

import ipaddress
from typing import Any, Dict, Iterable, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover - requests is a declared dependency
    requests = None  # type: ignore

_BATCH_URL = "http://ip-api.com/batch"
_FIELDS = "status,message,country,countryCode,regionName,city,lat,lon,isp,org,query"
_cache: Dict[str, Optional[Dict[str, Any]]] = {}


def _is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_reserved
                or addr.is_link_local or addr.is_multicast or addr.is_unspecified)


def resolve_ips(ips: Iterable[str], timeout: float = 6.0) -> List[Dict[str, Any]]:
    """Resolve a collection of IPs to geo records.

    Returns a list of dicts: ``{ip, country, country_code, region, city, lat,
    lon, isp, org}``. Unresolvable / private IPs are omitted.
    """
    unique = []
    seen = set()
    for ip in ips:
        if not ip or ip in seen:
            continue
        seen.add(ip)
        if _is_public(ip):
            unique.append(ip)

    results: List[Dict[str, Any]] = []
    pending: List[str] = []
    for ip in unique:
        if ip in _cache:
            if _cache[ip]:
                results.append(_cache[ip])  # type: ignore[arg-type]
        else:
            pending.append(ip)

    if pending and requests is not None:
        try:
            resp = requests.post(
                f"{_BATCH_URL}?fields={_FIELDS}",
                json=pending,
                timeout=timeout,
            )
            resp.raise_for_status()
            for item in resp.json():
                ip = item.get("query")
                if item.get("status") == "success":
                    record = {
                        "ip": ip,
                        "country": item.get("country"),
                        "country_code": item.get("countryCode"),
                        "region": item.get("regionName"),
                        "city": item.get("city"),
                        "lat": item.get("lat"),
                        "lon": item.get("lon"),
                        "isp": item.get("isp"),
                        "org": item.get("org"),
                    }
                    _cache[ip] = record
                    results.append(record)
                else:
                    _cache[ip] = None
        except Exception:
            # Silent degradation — the map is optional.
            for ip in pending:
                _cache.setdefault(ip, None)

    return results


def extract_source_ips(stages: Dict[str, Any]) -> List[str]:
    """Pull candidate attacker IPs from forensic + attribution stages."""
    ips: List[str] = []

    timeline = stages.get("forensic_timeline") or {}
    for event in timeline.get("events") or []:
        ip = event.get("source_ip")
        if ip:
            ips.append(ip)

    attribution = stages.get("attack_attribution") or {}
    for ioc in attribution.get("indicators_of_compromise") or []:
        if ioc.get("ioc_type") == "ip_address" and ioc.get("value"):
            ips.append(ioc["value"])

    # De-duplicate, preserve order.
    seen = set()
    ordered = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            ordered.append(ip)
    return ordered
