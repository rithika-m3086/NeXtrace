from typing import Any, Dict, List


def evaluate(data_categories: List[str], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluates exposed data categories against deterministic regulatory rules.

    Args:
        data_categories: List of exposed categories (e.g. ['pii', 'health']).
        metadata: Dict of organization/context attributes (e.g. {'state': 'CA', 'has_soc2': True}).

    Returns:
        List of dicts representing triggered compliance obligations.
    """
    flags = []

    # 1. GDPR (PII exposed)
    if "pii" in data_categories:
        flags.append({
            "regulation": "GDPR",
            "triggered": True,
            "reason": "Personally Identifiable Information (PII) exposed, triggering Article 33 requirements.",
            "mandatory_notification": True,
            "notification_deadline_hours": 72,
            "notification_recipients": ["DPA", "data subjects"]
        })

    # 2. CCPA (PII + CA/US consumer target)
    if "pii" in data_categories:
        is_us_consumer = metadata.get("is_us_consumer", False) or metadata.get("state") == "CA"
        if is_us_consumer:
            flags.append({
                "regulation": "CCPA",
                "triggered": True,
                "reason": "California consumer PII exposed, triggering notice of breach requirements.",
                "mandatory_notification": True,
                "notification_recipients": ["California Attorney General", "consumers"]
            })

    # 3. HIPAA (Health data exposed)
    if "health" in data_categories:
        flags.append({
            "regulation": "HIPAA",
            "triggered": True,
            "reason": "Protected Health Information (PHI) exposed, triggering Breach Notification Rule.",
            "mandatory_notification": True,
            "notification_deadline_hours": 1440,  # 60 days
            "notification_recipients": ["HHS OCR", "affected patients"]
        })

    # 4. PCI DSS (Financial or Card data exposed)
    if "financial" in data_categories or "credentials" in data_categories:
        flags.append({
            "regulation": "PCI_DSS",
            "triggered": True,
            "reason": "Cardholder or authentication credentials exposed, requiring forensic assessment.",
            "mandatory_notification": True,
            "notification_recipients": ["Acquiring Bank", "Card Brands"]
        })

    # 5. SOC2 (Organization has SOC2 certification)
    if metadata.get("has_soc2", False):
        flags.append({
            "regulation": "SOC2",
            "triggered": True,
            "reason": "Breach impacts trust service criteria controls (Security/Confidentiality).",
            "mandatory_notification": False,
            "notification_recipients": ["Auditors", "user entities"]
        })

    # 6. Fallback if no regulations are triggered
    if not flags:
        flags.append({
            "regulation": "none",
            "triggered": False,
            "reason": "No sensitive data categories or SOC2 controls triggered compliance obligations.",
            "mandatory_notification": False,
            "notification_recipients": []
        })

    return flags
