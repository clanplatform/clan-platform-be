"""
Shared helpers for the ``access`` permission field used by application's,
modules and menus.

The access field is an array of permission strings restricted to
``read`` / ``write`` / ``disable``. These helpers give every resource the
same behaviour:

- ``normalize_access``   — validate/normalize the list on write paths.
- ``is_active_from_access`` — derive ``is_active`` from the permissions.
- ``is_write_locked``    — is the resource read-only (no ``write`` granted)?
"""
from typing import Any, Dict, List, Optional

# The only permissions an access array may contain.
ALLOWED_ACCESS = {"read", "write", "disable"}

# Strength ordering for the access tokens, used to cascade/clamp a form
# component tree: write is the strongest permission, disable the weakest.
_ACCESS_RANK = {"disable": 0, "read": 1, "write": 2}


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


def coerce_access(value: Optional[object]) -> List[str]:
    """Lenient counterpart to normalize_access for the form-component tree:
    accepts a str or list, lower-cases, de-dupes, and SILENTLY DROPS any token
    that isn't read/write/disable (nested component ``access`` is free-form
    JSON and must never 500 a form save). Always returns a list."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    out: List[str] = []
    for item in value:
        if item is None:
            continue
        key = str(item).strip().lower()
        if key in ALLOWED_ACCESS and key not in out:
            out.append(key)
    return out


def _clamp_access(own: List[str], ceiling: List[str]) -> List[str]:
    """Drop any token in ``own`` stronger than the strongest token in
    ``ceiling`` (write > read > disable). If that removes everything, fall
    back to the single strongest ceiling token so a child can never end up
    with more access than its parent."""
    ceiling_rank = max(
        (_ACCESS_RANK.get(a, 0) for a in ceiling),
        default=max(_ACCESS_RANK.values()),
    )
    kept = [a for a in own if _ACCESS_RANK.get(a, 0) <= ceiling_rank]
    if kept:
        return kept
    return [max(ceiling, key=lambda a: _ACCESS_RANK.get(a, 0))]


# cascade_access resolves the definition-level `access` in the tree
# vocabulary (read/write/disable). props.access.value — the form-builder
# convention a frontend actually reads — uses read/write/hidden instead
# (same wire vocabulary FIELD_ACCESS_VALUES/AccessProp use in
# app.forms.schemas.forms). This is the reverse of that module's
# _to_definition_access (hidden -> disable), applied when syncing a
# resolved node's access back into props.access.value.
_TREE_TO_FIELD_ACCESS = {"disable": "hidden"}


def cascade_access(
    node: Dict[str, Any],
    inherited: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Resolve the ``access`` list for a form-component tree ``node`` and every
    descendant, mutating each node in place. Returns ``node``.

    Rules:
      * A node with a non-empty ``access`` list has an explicit override — it
        is kept, but CLAMPED so it can never exceed the parent's resolved
        access (parent ``["read"]`` + child ``["write"]`` -> child ``["read"]``;
        parent ``["disable"]`` -> child ``["disable"]``).
      * A node with an empty / missing ``access`` list inherits the parent's
        resolved access (parent ``["write"]`` -> every non-overridden
        descendant becomes ``["write"]``).
      * The node's resolved access is what cascades further down to its
        ``children``.

    ``inherited`` None/[] at the root means "no ceiling" — the root keeps its
    own access verbatim and empty descendants inherit nothing (so an
    uncalled/rootless cascade can still legitimately end up with an empty
    resolved access — callers that need every node to land on a concrete
    read/write/hidden, such as _cascade_forms_access, must always seed the
    root with a non-empty ``inherited``).

    Also keeps ``props.access.value`` in sync with the resolved access on
    every node (mapped through _TREE_TO_FIELD_ACCESS), so "Default" fields
    that just inherited a concrete value from their parent report that same
    concrete value under props.access.value too, instead of staying stuck at
    ``[]`` — the form-builder convention a frontend actually reads.
    """
    if not isinstance(node, dict):
        return node

    ceiling = coerce_access(inherited)
    own = coerce_access(node.get("access"))

    if own:
        resolved = _clamp_access(own, ceiling) if ceiling else own
    else:
        resolved = list(ceiling)

    node["access"] = resolved

    props = node.get("props")
    if not isinstance(props, dict):
        props = {}
        node["props"] = props
    props["access"] = {"value": [_TREE_TO_FIELD_ACCESS.get(a, a) for a in resolved]}

    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            cascade_access(child, resolved)

    return node


# A role field-permission node's vocabulary ("read" / "write" / "hidden") mapped
# onto the component tree's own vocabulary ("read" / "write" / "disable").
_FIELD_TO_TREE_ACCESS = {"read": ["read"], "write": ["write"], "hidden": ["disable"]}


def _field_node_access(perm_node: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    """The tree-vocabulary access a role field-permission node asks for, or None
    for "Default" (empty / missing access).

    Reads props.access.value — the current userrole_permission
    .form_permissions[].fields node shape, {key, props:{access:{value:[...]},
    label?}, children} (see UserRoleService._build_field_tree) — falling back
    to a legacy top-level `access` key so rows written before props/label were
    kept ({key, access, children}) still enforce correctly."""
    if not isinstance(perm_node, dict):
        return None
    raw = None
    props = perm_node.get("props")
    if isinstance(props, dict) and "access" in props:
        ap = props["access"]
        raw = ap.get("value") if isinstance(ap, dict) else ap
    if raw is None:
        raw = perm_node.get("access")
    for a in (raw or []):
        mapped = _FIELD_TO_TREE_ACCESS.get(str(a).strip().lower())
        if mapped:
            return list(mapped)
    return None


def apply_field_permissions(
    node: Dict[str, Any],
    perm_node: Optional[Dict[str, Any]],
    inherited: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Overlay a role's per-field permission tree onto an already-cascaded form
    component tree, in place, walking both trees in parallel and matching
    children by ``key``. Returns ``node``.

    ``perm_node`` is the matching node in the role's ``form_permissions[].fields``
    tree ({key, props:{access:{value:[...]}, label?}, children} — or the legacy
    {key, access, children} shape, both read by _field_node_access), or None
    when the role tree doesn't cover this branch. Semantics mirror ``cascade_access``:
      * a node whose role access is set ('read'/'write'/'hidden', the last ->
        ``["disable"]``) takes it, and it cascades to descendants that have no
        role access of their own;
      * a node with role "Default" (``[]``) inherits the nearest explicit
        ancestor, else keeps whatever ``cascade_access`` already resolved;
      * a role can only RESTRICT — the result is intersected with the component's
        own definition access (a role can't turn a read-only field writable).

    Serve time only, never persisted. Node-level values were already clamped to
    the form's ``form_access`` on save (UserRoleService._build_field_tree).

    Keeps ``props.access.value`` (the form-builder convention a frontend
    actually reads) in sync with the resolved top-level ``access`` on every
    node this walks — without this, a served form would show the role's
    resolved per-field access (write/read/disable) only under the legacy
    top-level ``access`` key while ``props.access.value`` kept whatever
    static value the field was authored with, never reflecting what the
    viewing role can actually do with that field.
    """
    if not isinstance(node, dict):
        return node

    own = _field_node_access(perm_node)
    effective = own or inherited
    if effective is not None:
        node["access"] = _more_restrictive(effective, coerce_access(node.get("access")))

    props = node.get("props")
    if not isinstance(props, dict):
        props = {}
        node["props"] = props
    props["access"] = {"value": [_TREE_TO_FIELD_ACCESS.get(a, a) for a in coerce_access(node.get("access"))]}

    perm_children = {}
    if isinstance(perm_node, dict):
        for c in (perm_node.get("children") or []):
            if isinstance(c, dict) and c.get("key"):
                perm_children[c["key"]] = c

    for child in (node.get("children") or []):
        if isinstance(child, dict):
            apply_field_permissions(child, perm_children.get(child.get("key")), effective)

    return node


def _more_restrictive(a: List[str], b: List[str]) -> List[str]:
    """The lower-ranked (more restrictive) of two resolved access lists
    (write > read > disable). An empty ``b`` (no definition restriction) yields
    ``a`` unchanged."""
    a = coerce_access(a)
    b = coerce_access(b)
    if not b:
        return a or b
    if not a:
        return b
    ra = max(_ACCESS_RANK.get(x, 0) for x in a)
    rb = max(_ACCESS_RANK.get(x, 0) for x in b)
    lo = a if ra <= rb else b
    return [max(lo, key=lambda x: _ACCESS_RANK.get(x, 0))]
