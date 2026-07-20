"""
Shared helpers for the ``access`` permission field used by applications,
modules and menus.

The access field is an array of permission strings restricted to
``read`` / ``write`` / ``disable``. These helpers give every resource the
same behaviour:

- ``normalize_access``   — validate/normalize the list on write paths.
- ``is_active_from_access`` — derive ``is_active`` from the permissions.
- ``is_write_locked``    — is the resource read-only (no ``write`` granted)?
"""
from typing import List, Optional

# The only permissions an access array may contain.
ALLOWED_ACCESS = {"read", "write", "disable"}


def normalize_access(value: Optional[List[str]]) -> Optional[List[str]]:
    """
    Validate and normalize an access permissions list.

    Each entry is stripped/lower-cased and must be one of ALLOWED_ACCESS
    (read, write, disable); anything else raises a ValueError. Duplicates are
    dropped (access is a set of permissions) and None passes through unchanged
    (field simply not provided on an update).
    """
    if value is None:
        return value
    normalized: List[str] = []
    for item in value:
        if item is None:
            continue
        key = str(item).strip().lower()
        if key not in ALLOWED_ACCESS:
            raise ValueError(
                f"Invalid access value '{item}'. Allowed values: "
                f"{', '.join(sorted(ALLOWED_ACCESS))}"
            )
        if key not in normalized:
            normalized.append(key)
    return normalized


def is_active_from_access(access: Optional[List[str]]) -> Optional[bool]:
    """
    Derive is_active from the access permissions.

    - "disable" present -> False (disable wins over everything else)
    - "write" or "read" -> True  (resource is reachable; write vs read is the
                                   permission level, both are "active")
    - empty / no relevant token -> None (no directive; leave is_active as-is)
    """
    if not access:
        return None
    tokens = {str(a).strip().lower() for a in access if a}
    if "disable" in tokens:
        return False
    if "write" in tokens or "read" in tokens:
        return True
    return None


def is_write_locked(access: Optional[List[str]]) -> bool:
    """
    True when the access permissions make the resource read-only.

    A resource is write-locked when access is set but does not grant "write"
    (e.g. ["read"], ["disable"]). Empty/unset access is unrestricted.
    """
    if not access:
        return False
    tokens = {str(a).strip().lower() for a in access if a}
    return "write" not in tokens
