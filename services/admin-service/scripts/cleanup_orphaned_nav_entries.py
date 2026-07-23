"""
Remove orphaned/corrupt entries from the MongoDB navigation documents.

Why this exists: DELETE /menus/{menu_id} used to soft-delete the PostgreSQL
row and then 500 (broken import) before removing the entry from the
navigation document, leaving ghost entries that stay visible in the UI and
can no longer be deleted through the API (retries 404). The endpoint is
fixed (and now idempotent — re-running DELETE prunes leftovers), but entries
stranded before the fix still need manual removal. That is what this script
does.

It walks the master navigation document (mainNavigation) and every
referenced application document in menu_details, and removes entries whose
menu_id starts with one of the given id prefixes. "Default Module"
containers (module_id == "default") that end up empty are removed as well.

Dry-run by default; pass --apply to write changes.

Usage (inside the admin-service container):
    # See the full nav tree with menu_ids first
    python scripts/cleanup_orphaned_nav_entries.py --list

    # Preview what would be removed
    python scripts/cleanup_orphaned_nav_entries.py --ids a9696174,a3824835,4bc47cfc,26686d3f

    # Actually remove
    python scripts/cleanup_orphaned_nav_entries.py --ids a9696174,a3824835,4bc47cfc,26686d3f --apply
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import certifi
from bson import ObjectId
from pymongo import MongoClient

from app.core.config import settings

MASTER_DOC_ID = ObjectId("69074724f217ab8fcb2e3b24")


def get_collection():
    # tlsCAFile implicitly enables TLS in pymongo — only pass it for
    # Atlas-style URLs; the local docker mongodb is plain TCP.
    kwargs = {"serverSelectionTimeoutMS": 5000}
    if settings.MONGODB_URL.startswith("mongodb+srv://"):
        kwargs["tlsCAFile"] = certifi.where()
    client = MongoClient(settings.MONGODB_URL, **kwargs)
    client.admin.command("ping")
    return client[settings.MONGODB_DB_NAME]["menu_details"]


def print_tree(items, indent=0):
    for item in items:
        if not isinstance(item, dict):
            print(f"{'  ' * indent}- <ref {item}>")
            continue
        label = item.get("label") or item.get("key") or "?"
        bits = []
        if item.get("menu_id"):
            bits.append(f"menu_id={item['menu_id']}")
        if item.get("module_id"):
            bits.append(f"module_id={item['module_id']}")
        if item.get("application_id"):
            bits.append(f"app_id={item['application_id']}")
        if item.get("level") is not None:
            bits.append(f"level={item['level']}")
        print(f"{'  ' * indent}- {label} ({', '.join(bits)})")
        children = item.get("children")
        if isinstance(children, list) and children:
            print_tree(children, indent + 1)


def prune(items, prefixes, removed, path=""):
    """Return (kept_items, changed). Removes entries whose menu_id starts with
    any prefix, then drops 'Default Module' containers left empty."""
    changed = False
    kept = []
    for item in items:
        if isinstance(item, dict):
            label = item.get("label") or item.get("key") or "?"
            menu_id = str(item.get("menu_id") or "").lower()
            if menu_id and any(menu_id.startswith(p) for p in prefixes):
                removed.append(f"{path}/{label} (menu_id={menu_id})")
                changed = True
                continue
            children = item.get("children")
            if isinstance(children, list):
                new_children, child_changed = prune(
                    children, prefixes, removed, f"{path}/{label}"
                )
                if child_changed:
                    item["children"] = new_children
                    changed = True
                # Drop Default Module containers that are now (or were) empty
                if item.get("module_id") == "default" and not item["children"]:
                    removed.append(f"{path}/{label} (empty Default Module container)")
                    changed = True
                    continue
        kept.append(item)
    return kept, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Print the nav tree and exit")
    parser.add_argument("--ids", help="Comma-separated menu_id prefixes to remove")
    parser.add_argument("--fix-dangling", action="store_true",
                        help="Remove mainNavigation references whose document no longer exists")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    args = parser.parse_args()

    coll = get_collection()
    master = coll.find_one({"_id": MASTER_DOC_ID})
    if not master:
        print(f"Master navigation document {MASTER_DOC_ID} not found")
        sys.exit(1)

    main_nav = master.get("mainNavigation", [])

    # Resolve referenced application documents
    app_docs = []
    dangling = []
    for ref in main_nav:
        if isinstance(ref, (ObjectId, str)):
            try:
                doc = coll.find_one({"_id": ObjectId(str(ref))})
            except Exception:
                doc = None
            if doc:
                app_docs.append(doc)
            else:
                print(f"! dangling mainNavigation reference: {ref}")
                dangling.append(ref)

    if args.list:
        print(f"=== master doc {MASTER_DOC_ID} mainNavigation ===")
        print_tree([i for i in main_nav if isinstance(i, dict)])
        for doc in app_docs:
            print(f"\n=== app doc {doc['_id']} ({doc.get('label')}, application_id={doc.get('application_id')}) ===")
            print_tree(doc.get("children") or [])
        return

    if not args.ids and not args.fix_dangling:
        parser.error("--ids and/or --fix-dangling is required unless --list is given")

    prefixes = [p.strip().lower() for p in (args.ids or "").split(",") if p.strip()]
    removed = []
    updates = []  # (doc_id, field, new_value)

    # Master document: drop dangling refs (if requested), then prune inline entries
    master_nav = list(main_nav)
    master_changed = False

    if args.fix_dangling and dangling:
        master_nav = [
            r for r in master_nav
            if not (isinstance(r, (ObjectId, str)) and r in dangling)
        ]
        for r in dangling:
            removed.append(f"master/<dangling reference {r}>")
        master_changed = True

    new_dicts, changed = prune(
        [i for i in master_nav if isinstance(i, dict)], prefixes, removed, "master"
    )
    if changed:
        # Re-merge in original order: ObjectId refs untouched, inline dicts
        # kept only if they survived the prune (identity check — prune keeps
        # the same objects it was given).
        kept_dicts = set(map(id, new_dicts))
        master_nav = [
            item for item in master_nav
            if not isinstance(item, dict) or id(item) in kept_dicts
        ]
        master_changed = True

    if master_changed:
        updates.append((MASTER_DOC_ID, "mainNavigation", master_nav))

    # Prune each referenced application document
    for doc in app_docs:
        children = doc.get("children")
        if not isinstance(children, list):
            continue
        new_children, changed = prune(
            children, prefixes, removed, str(doc.get("label") or doc["_id"])
        )
        if changed:
            updates.append((doc["_id"], "children", new_children))

    if not removed:
        print("Nothing matched — no entries removed.")
        return

    print(f"{'Would remove' if not args.apply else 'Removing'} {len(removed)} entries:")
    for r in removed:
        print(f"  - {r}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write these changes.")
        return

    for doc_id, field, value in updates:
        coll.update_one({"_id": doc_id}, {"$set": {field: value}})
        print(f"Updated {doc_id} ({field})")
    print("Done. Restart is not needed; clear Redis nav cache or wait for TTL.")


if __name__ == "__main__":
    main()
