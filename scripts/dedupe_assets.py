"""Interactively deduplicate assets in the home-asset-agent database.

Finds assets sharing (user_id, LOWER(name), category), shows each set of
duplicates, and asks which asset_id to keep. Deletes the others via ON
DELETE CASCADE (maintenance_tasks referencing a deleted asset are removed
automatically).

Run with:
  uv run python scripts/dedupe_assets.py             # dry-run: show what would be deleted
  uv run python scripts/dedupe_assets.py --apply     # actually delete
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import psycopg
from psycopg.rows import dict_row


def find_duplicate_groups(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, LOWER(name) AS lname, category, COUNT(*) AS n
            FROM assets
            WHERE user_id IS NOT NULL
            GROUP BY user_id, LOWER(name), category
            HAVING COUNT(*) > 1
            ORDER BY n DESC, LOWER(name)
            """
        )
        return cur.fetchall()


def list_group(conn, user_id, lname, category):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.id, a.name, a.category, a.brand, a.model, a.location, a.created_at,
                u.email AS user_email,
                (SELECT COUNT(*) FROM maintenance_tasks m WHERE m.asset_id = a.id)
                    AS maintenance_count
            FROM assets a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE a.user_id = %s AND LOWER(a.name) = %s AND a.category = %s
            ORDER BY a.id
            """,
            [user_id, lname, category],
        )
        return cur.fetchall()


def choose_keeper(rows):
    print()
    for i, r in enumerate(rows, 1):
        print(
            f"  [{i}] id={r['id']}  created={r['created_at']}  "
            f"loc={r['location'] or '-'}  brand={r['brand'] or '-'}  "
            f"maint_rows={r['maintenance_count']}"
        )
    while True:
        answer = input(f"  Keep which? [1-{len(rows)}, s=skip]: ").strip().lower()
        if answer in ("s", "skip", ""):
            return None
        try:
            idx = int(answer)
            if 1 <= idx <= len(rows):
                return rows[idx - 1]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(rows)}, or 's' to skip.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete duplicates. Without this flag the script is a dry run.",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set in environment.", file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        groups = find_duplicate_groups(conn)
        if not groups:
            print("No duplicates found. Database is clean.")
            return

        print(f"Found {len(groups)} duplicate group(s).\n")

        total_deleted = 0
        for g in groups:
            rows = list_group(conn, g["user_id"], g["lname"], g["category"])
            email = rows[0]["user_email"] or "(unknown user)"
            print(f"'{rows[0]['name']}' ({g['category']}) — {g['n']} copies, user: {email}")
            keeper = choose_keeper(rows)
            if keeper is None:
                print("  skipped\n")
                continue

            to_delete = [r["id"] for r in rows if r["id"] != keeper["id"]]
            print(f"  Keep id={keeper['id']}, delete {to_delete}")
            if args.apply:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM assets WHERE id = ANY(%s)", [to_delete])
                total_deleted += len(to_delete)
                print(f"  deleted {len(to_delete)}")
            else:
                print("  dry-run: pass --apply to actually delete")
            print()

        if args.apply:
            print(f"Done. Deleted {total_deleted} row(s).")
        else:
            print("Dry-run complete. Re-run with --apply to delete.")


if __name__ == "__main__":
    main()
