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
    incoming = _perm("Screen", [], [
        _perm("a", ["write"]),
        _perm("b", ["hidden"]),
        _perm("c", []),
    ])
    out = UserRoleService._build_field_tree(incoming, ["read"])
    assert out == {
        "key": "Screen", "access": [], "children": [
            {"key": "a", "access": ["read"], "children": []},
            {"key": "b", "access": ["hidden"], "children": []},
            {"key": "c", "access": [], "children": []},
        ],
    }
