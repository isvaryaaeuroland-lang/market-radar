"""Small CLI for watchlist management, per SOP §5.

    python -m radar.cli add-watchlist --domain example.com --competitor a.com --competitor b.com
    python -m radar.cli list-watchlist
"""
from __future__ import annotations

import argparse

from .storage import add_to_watchlist, list_watchlist


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the Radar's watchlist.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add-watchlist")
    add_parser.add_argument("--domain", required=True, help="Your own company's domain")
    add_parser.add_argument("--competitor", action="append", default=[], help="Repeatable: a competitor domain")

    subparsers.add_parser("list-watchlist")

    args = parser.parse_args()

    if args.command == "add-watchlist":
        add_to_watchlist(args.domain, is_own_company=True)
        for competitor in args.competitor:
            add_to_watchlist(competitor, is_own_company=False)
        print(f"Added {args.domain} (own) and {len(args.competitor)} competitor(s) to the watchlist.")

    elif args.command == "list-watchlist":
        for row in list_watchlist():
            role = "own" if row["is_own_company"] else "competitor"
            print(f"{row['domain']} ({role}) — added {row['added_at']}")


if __name__ == "__main__":
    main()
