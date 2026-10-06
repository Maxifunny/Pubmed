from pathlib import Path

from pmc import xml_to_text


xml_files = list(
    Path("articles").glob("PMC*/article.xml")
)

print()
print(f"Found {len(xml_files)} XML files.")
print()

for xml_path in xml_files:

    print(f"Processing {xml_path}")

    xml_content = xml_path.read_bytes()

    article_text = xml_to_text(
        xml_content
    )

    txt_path = (
        xml_path.parent / "article.txt"
    )

    txt_path.write_text(
        article_text,
        encoding="utf-8"
    )

    print(
        f"  -> {len(article_text):,} characters"
    )

print()
print("Finished.")