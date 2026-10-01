"""Inspect the indexed library and explicitly remove a paper's index."""

import argparse

from sqlalchemy.exc import SQLAlchemyError

from app.library import library_inventory, remove_document, validate_document_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage indexed papers; original PDF files are never deleted.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List filenames, chunk counts and indexed-page counts.")
    remove = commands.add_parser("remove", help="Preview removal of one exact indexed filename.")
    remove.add_argument("document", help="Exact filename, including extension (not a path).")
    remove.add_argument("--yes", action="store_true", help="Apply the removal instead of previewing it.")
    args = parser.parse_args()
    if args.command == "remove":
        try:
            validate_document_name(args.document)
        except ValueError as error:
            parser.error(str(error))
    try:
        if args.command == "list":
            inventory = library_inventory()
            if not inventory:
                print("No papers are indexed. Add one with uv run python -m scripts.index_pdf <PDF path>.")
            for paper in inventory:
                print(f"{paper.document}: {paper.chunks} chunks, {paper.indexed_pages} indexed pages")
        elif args.yes:
            count = remove_document(args.document)
            if not count:
                raise SystemExit("No matching indexed paper. Use the list command to check its exact filename.")
            print(f"Removed {count} chunks for {args.document}. The original PDF was not deleted.")
        else:
            target = next((paper for paper in library_inventory() if paper.document == args.document), None)
            if target is None:
                raise SystemExit("No matching indexed paper. Use the list command to check its exact filename.")
            print(f"Would remove {target.chunks} chunks for {target.document} ({target.indexed_pages} indexed pages).")
            print("Re-run this remove command with --yes to apply it. The original PDF will not be deleted.")
    except SQLAlchemyError:
        raise SystemExit("Could not access the database. Check PostgreSQL and your .env settings, then run uv run python -m scripts.init_db.") from None


if __name__ == "__main__":
    main()
