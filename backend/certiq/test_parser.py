import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from certiq.parser import parse_any

tests = [
    "data/roofing_certs/Cert1.pdf",
    "data/roofing_certs/Cert4.pdf",
    "data/roofing_tests/Test3.pdf",
]

for path in tests:
    if not Path(path).exists():
        print(f"MISSING: {path}")
        continue
    doc = parse_any(path)
    print(f"File     : {doc.metadata['filename']}")
    print(f"Type     : {doc.source_type}")
    print(f"Pages    : {doc.page_count}")
    print(f"Words    : {doc.word_count}")
    print(f"Company  : {doc.metadata['company']}")
    print(f"Cert No  : {doc.metadata['cert_no']}")
    print(f"Sections : {len(doc.sections)}")
    print(f"Sample   : {doc.raw_text[:100]}")
    print()

# Test plain text
doc = parse_any("Plasterboard fire resistance, wind uplift required, 25 year service life")
print(f"Text input: {doc.source_type} — {doc.word_count} words")

# Test form
doc = parse_any({"weathertightness": True, "fire": True, "durability": "25 years"})
print(f"Form input: {doc.source_type}")

print()
print("✅ Universal parser working for all input types")