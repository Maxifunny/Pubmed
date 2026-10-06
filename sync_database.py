from pathlib import Path
import sqlite3


DATABASE = "pubmed.db"
ARTICLES_DIR = Path("articles")


def sync_database():
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    txt_files = list(
        ARTICLES_DIR.glob("PMC*/article.txt")
    )

    print()
    print(f"Found {len(txt_files)} article.txt files.")
    print()

    updated = 0
    not_found = 0
    empty = 0

    for txt_path in txt_files:

        pmcid = txt_path.parent.name

        text = txt_path.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            print(f"EMPTY: {pmcid}")
            empty += 1
            continue

        cursor.execute(
            """
            UPDATE articles
            SET full_text = ?
            WHERE pmcid = ?
            """,
            (
                text,
                pmcid
            )
        )

        if cursor.rowcount > 0:

            print(
                f"UPDATED: {pmcid} "
                f"({len(text):,} characters)"
            )

            updated += 1

        else:

            print(
                f"NOT FOUND IN DATABASE: {pmcid}"
            )

            not_found += 1

    connection.commit()
    connection.close()

    print()
    print("=" * 60)
    print("Synchronization completed")
    print("=" * 60)

    print(f"Updated:   {updated}")
    print(f"Empty:     {empty}")
    print(f"Not found: {not_found}")
    print()


if __name__ == "__main__":
    sync_database()