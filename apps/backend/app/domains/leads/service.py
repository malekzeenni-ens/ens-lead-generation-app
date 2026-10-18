"""Lead management.

The service is a chain, each link in its own module (R9): `lead_base` (reading and identity checks)
-> `editing` -> `operations` -> `privacy` -> this module. Every method keeps its name, so callers
and tests use `LeadService` exactly as before.
"""

from __future__ import annotations

from app.domains.leads.lead_read import lead_to_read
from app.domains.leads.privacy import LeadPrivacy

__all__ = ["LeadService", "lead_to_read"]


class LeadService(LeadPrivacy):
    """Leads, their pipeline, activity, suppression and privacy deletion."""
