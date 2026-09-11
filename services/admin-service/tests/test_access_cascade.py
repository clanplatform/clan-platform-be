"""Unit tests for the form-component access cascade + the role per-field
permission overlay (app.core.access).

Pure functions, no DB — run inside the admin-service container:
    docker exec <admin-service> python -B -m pytest tests/test_access_cascade.py
"""
from app.core.access import cascade_access, apply_field_permissions


def _node(key, access=None, children=None):
    return {"key": key, "access": list(access or []), "children": children or []}


def test_parent_write_cascades_to_empty_children():
    tree = _node("Screen", ["write"], [
        _node("a"),
        _node("b", children=[_node("b1")]),
    ])
    cascade_access(tree, ["write"])
    assert tree["children"][0]["access"] == ["write"]
    assert tree["children"][1]["access"] == ["write"]
    assert tree["children"][1]["children"][0]["access"] == ["write"]


def test_child_override_lower_wins_for_that_subtree_only():
    tree = _node("Screen", ["write"], [
        _node("keeps_write"),
        _node("read_only", ["read"], [_node("grandchild")]),
    ])
    cascade_access(tree, ["write"])
    assert tree["children"][0]["access"] == ["write"]          # sibling still inherits write
    assert tree["children"][1]["access"] == ["read"]           # explicit override kept
    assert tree["children"][1]["children"][0]["access"] == ["read"]  # cascades the override down


def test_child_cannot_exceed_parent_clamped_to_read():
    tree = _node("Screen", ["read"], [_node("wants_write", ["write"])])
    cascade_access(tree, ["read"])
    assert tree["children"][0]["access"] == ["read"]


def test_disabled_parent_disables_children_even_when_they_ask_for_read():
    tree = _node("Screen", ["disable"], [_node("x", ["read"])])
    cascade_access(tree, ["disable"])
    assert tree["children"][0]["access"] == ["disable"]


def test_empty_root_seed_leaves_root_untouched_and_children_inherit_nothing():
    tree = _node("Screen", [], [_node("x")])
    cascade_access(tree, [])
    assert tree["access"] == []
    assert tree["children"][0]["access"] == []


def test_string_access_is_normalized():
    tree = {"key": "Screen", "access": "write", "children": [{"key": "a", "access": "", "children": []}]}
    cascade_access(tree, ["write"])
    assert tree["access"] == ["write"]
    assert tree["children"][0]["access"] == ["write"]


def test_unknown_tokens_are_dropped_not_raised():
    tree = _node("Screen", ["write"], [
        _node("partly_bad", ["bogus", "read"]),
        _node("all_bad", ["garbage"]),   # -> nothing left -> inherits parent
    ])
    cascade_access(tree, ["write"])
    assert tree["children"][0]["access"] == ["read"]
    assert tree["children"][1]["access"] == ["write"]


# ---------------------------------------------------------------------------
# apply_field_permissions — role per-field TREE overlay on an already-cascaded
# form component tree (parallel walk, match children by key)
# ---------------------------------------------------------------------------

def _cascaded_form():
    return _node("Screen", ["write"], [
        _node("layout", ["write"], [
            _node("header", ["write"]),
            _node("saveBtn", ["write"]),
        ]),
        _node("statCard", ["write"]),
    ])


def _perm(key, access=None, children=None):
    return {"key": key, "access": list(access or []), "children": children or []}


def test_field_tree_override_read_on_container_cascades_to_children():
    form = _cascaded_form()
    tree = _perm("Screen", [], [
        _perm("layout", ["read"]),
    ])
    apply_field_permissions(form, tree)
    assert form["children"][0]["access"] == ["read"]
    assert form["children"][0]["children"][0]["access"] == ["read"]   # header inherits
    assert form["children"][0]["children"][1]["access"] == ["read"]   # saveBtn inherits
    assert form["children"][1]["access"] == ["write"]                 # statCard: Default -> untouched


def test_field_tree_hidden_maps_to_disable():
    form = _cascaded_form()
    tree = _perm("Screen", [], [
        _perm("layout", [], [_perm("saveBtn", ["hidden"])]),
        _perm("statCard", ["hidden"]),
    ])
    apply_field_permissions(form, tree)
    assert form["children"][0]["children"][1]["access"] == ["disable"]
    assert form["children"][1]["access"] == ["disable"]


def test_field_tree_child_override_beats_inherited_container_override():
    form = _cascaded_form()
    tree = _perm("Screen", [], [
        _perm("layout", ["read"], [_perm("saveBtn", ["hidden"])]),
    ])
    apply_field_permissions(form, tree)
    assert form["children"][0]["children"][0]["access"] == ["read"]     # header: inherited
    assert form["children"][0]["children"][1]["access"] == ["disable"]  # saveBtn: own


def test_field_tree_role_can_only_restrict_not_widen():
    # form component is read-only by definition; role asking 'write' can't widen it
    form = _node("Screen", ["write"], [_node("ro", ["read"])])
    tree = _perm("Screen", [], [_perm("ro", ["write"])])
    apply_field_permissions(form, tree)
    assert form["children"][0]["access"] == ["read"]


def test_empty_field_tree_leaves_form_untouched():
    form = _cascaded_form()
    apply_field_permissions(form, None)
    assert form["children"][0]["children"][1]["access"] == ["write"]


def test_build_field_tree_clamps_write_on_read_only_form_and_keeps_skeleton():
    from app.user_role.services.user_role import UserRoleService
    # _perm's flat {key, access, children} shape is still valid INPUT here —
    # _extract_node_access falls back to it — but _build_field_tree's OUTPUT
    # is always the current nested props shape (see assertion below).
    incoming = _perm("Screen", [], [
        _perm("a", ["write"]),
        _perm("b", ["hidden"]),
        _perm("c", []),
    ])
    out = UserRoleService._build_field_tree(incoming, ["read"])
    assert out == {
        "key": "Screen", "props": {"access": {"value": []}}, "children": [
            {"key": "a", "props": {"access": {"value": ["read"]}}, "children": []},
            {"key": "b", "props": {"access": {"value": ["hidden"]}}, "children": []},
            {"key": "c", "props": {"access": {"value": []}}, "children": []},
        ],
    }


# ---------------------------------------------------------------------------
# _build_form_perms — the form-builder-shaped form_permissions item
# ---------------------------------------------------------------------------

def _role_form_perm(form_id, form):
    return {"id": form_id, "name": "x", "form": form, "version": "1"}


def test_build_form_perms_from_form_object_empty_root_grants_and_no_clamp():
    from app.user_role.services.user_role import UserRoleService
    item = _role_form_perm("F1", {
        "key": "S", "type": "Screen", "props": {}, "access": [],
        "children": [
            {"key": "a", "type": "AntInput", "access": ["write"], "css": {"x": 1}, "children": []},
            {"key": "b", "type": "AntInput", "access": ["hidden"], "children": []},
        ],
    })
    out = UserRoleService._build_form_perms([item])
    assert out == [{
        "id": "F1", "access": ["read", "write"],
        "fields": {"key": "S", "props": {"access": {"value": []}}, "children": [
            {"key": "a", "props": {"access": {"value": ["write"]}}, "children": []},   # css/type dropped, no label
            {"key": "b", "props": {"access": {"value": ["hidden"]}}, "children": []},
        ]},
    }]


def test_build_form_perms_read_only_form_clamps_children():
    from app.user_role.services.user_role import UserRoleService
    item = _role_form_perm("F2", {
        "key": "S", "access": ["read"],
        "children": [{"key": "a", "access": ["write"], "children": []}],
    })
    out = UserRoleService._build_form_perms([item])
    assert out[0]["access"] == ["read"]
    assert out[0]["fields"]["children"][0]["props"]["access"]["value"] == ["read"]


def test_build_form_perms_hidden_form_not_granted():
    from app.user_role.services.user_role import UserRoleService
    out = UserRoleService._build_form_perms(
        [_role_form_perm("F3", {"key": "S", "access": ["disable"], "children": []})]
    )
    assert out[0]["access"] == ["disable"]


# --- new shape: per-node access at props.access.value -----------------------

def _c(key, access=None, extra_props=None):
    """A component node in the form-builder shape (access at props.access.value)."""
    props = dict(extra_props or {})
    if access is not None:
        props["access"] = {"value": access}
    return {"key": key, "type": "AntInput", "props": props, "children": [], "tooltipProps": {}}


def test_build_form_perms_reads_props_access_value():
    from app.user_role.services.user_role import UserRoleService
    item = _role_form_perm("F1", {
        "key": "Screen", "type": "Screen", "props": {}, "children": [
            _c("code", ["read"], {"label": {"value": "Code"}}),
            _c("name", ["write"]),
            _c("secret", ["hidden"]),
            _c("notes", None),   # no access prop -> Default []
        ],
        "tooltipProps": {},
    })
    out = UserRoleService._build_form_perms([item])
    assert out == [{
        "id": "F1", "access": ["read", "write"],
        "fields": {"key": "Screen", "props": {"access": {"value": []}}, "children": [
            # "code" carried a label -> it's preserved on the stored node too
            {"key": "code", "props": {"access": {"value": ["read"]}, "label": {"value": "Code"}}, "children": []},
            {"key": "name", "props": {"access": {"value": ["write"]}}, "children": []},
            {"key": "secret", "props": {"access": {"value": ["hidden"]}}, "children": []},
            {"key": "notes", "props": {"access": {"value": []}}, "children": []},
        ]},
    }]


def test_build_form_perms_props_access_read_only_root_clamps():
    from app.user_role.services.user_role import UserRoleService
    form = {"key": "Screen", "type": "Screen",
            "props": {"access": {"value": ["read"]}}, "children": [_c("a", ["write"])],
            "tooltipProps": {}}
    out = UserRoleService._build_form_perms([_role_form_perm("F2", form)])
    assert out[0]["access"] == ["read"]
    assert out[0]["fields"]["children"][0]["props"]["access"]["value"] == ["read"]   # write clamped


def test_role_form_component_tree_normalizes_props_access():
    from app.user_role.schemas.user_role import RoleFormComponentTree, _extract_node_access
    node = RoleFormComponentTree.model_validate(
        {"key": "code", "type": "AntInput",
         "props": {"label": {"value": "Code"}, "access": {"value": ["write", "bogus"]}, "tabIndex": {"value": 0}},
         "children": [], "tooltipProps": {}, "schema": {"type": "string"}}
    )
    # unknown token dropped; label/tabIndex/schema ignored; access kept under props.access.value
    assert node.props["access"] == {"value": ["write"]}
    assert _extract_node_access(node) == ["write"]


def test_role_form_permission_reads_back_legacy_flat_shape():
    """Rows written before props/label were kept on the stored fields tree
    ({key, access, children}, no props at all) still read back correctly —
    _fields_node_to_builder falls back to the top-level `access` key via
    _extract_node_access, and simply omits label (never stored)."""
    from app.user_role.schemas.user_role import RoleFormPermission
    stored = {"id": "F1", "access": ["read", "write"], "fields": {
        "key": "Screen", "access": [], "children": [
            {"key": "code", "access": ["write"], "children": []},
            {"key": "notes", "access": [], "children": []},
        ]}}
    resp = RoleFormPermission.model_validate(stored)
    assert resp.id == "F1"
    assert resp.form.props == {"access": {"value": []}}
    assert resp.form.children[0].props == {"access": {"value": ["write"]}}
    assert resp.form.children[1].props == {"access": {"value": []}}
    # no top-level `access` key on the echoed nodes
    assert "access" not in resp.form.model_dump()


def test_role_form_permission_reads_back_with_label_preserved():
    """Current stored shape: {key, props:{access, label?}, children}. label
    round-trips through the response exactly as it was saved."""
    from app.user_role.schemas.user_role import RoleFormPermission
    stored = {"id": "F1", "access": ["read", "write"], "fields": {
        "key": "Screen", "props": {"access": {"value": []}}, "children": [
            {"key": "doctor_code", "props": {
                "access": {"value": ["write"]}, "label": {"value": "Doctor Code"},
            }, "children": []},
            {"key": "layout", "props": {"access": {"value": []}}, "children": []},  # no label
        ]}}
    resp = RoleFormPermission.model_validate(stored)
    assert resp.form.children[0].props == {
        "access": {"value": ["write"]}, "label": {"value": "Doctor Code"},
    }
    assert resp.form.children[1].props == {"access": {"value": []}}


# ---------------------------------------------------------------------------
# _field_node_access / apply_field_permissions — enforcement reads the SAME
# access regardless of which shape the perm node is stored in (new
# props.access.value, or the legacy flat access key from rows saved before
# label was kept).
# ---------------------------------------------------------------------------

def test_field_node_access_reads_new_props_shape():
    from app.core.access import _field_node_access
    assert _field_node_access({"key": "doctor_code", "props": {"access": {"value": ["write"]}}, "children": []}) == ["write"]
    assert _field_node_access({"key": "doctor_ssn", "props": {"access": {"value": ["hidden"]}}, "children": []}) == ["disable"]
    assert _field_node_access({"key": "doctor_notes", "props": {"access": {"value": []}}, "children": []}) is None


def test_field_node_access_falls_back_to_legacy_flat_shape():
    from app.core.access import _field_node_access
    assert _field_node_access({"key": "doctor_code", "access": ["write"], "children": []}) == ["write"]


def test_apply_field_permissions_enforces_identically_for_new_and_legacy_shape():
    """A role's 'hidden' grant on a field must still map to 'disable' on the
    served form whether the stored perm node is in the current props shape
    or the legacy flat shape — same real-world guarantee either way."""
    from app.core.access import apply_field_permissions

    def served_form():
        return {"key": "Screen", "access": ["write"], "children": [
            {"key": "doctor_ssn", "access": ["write"], "children": []},
        ]}

    new_shape_tree = {"key": "Screen", "props": {"access": {"value": []}}, "children": [
        {"key": "doctor_ssn", "props": {"access": {"value": ["hidden"]}}, "children": []},
    ]}
    legacy_shape_tree = {"key": "Screen", "access": [], "children": [
        {"key": "doctor_ssn", "access": ["hidden"], "children": []},
    ]}

    form_a = apply_field_permissions(served_form(), new_shape_tree)
    form_b = apply_field_permissions(served_form(), legacy_shape_tree)
    assert form_a["children"][0]["access"] == ["disable"]
    assert form_b["children"][0]["access"] == ["disable"]
