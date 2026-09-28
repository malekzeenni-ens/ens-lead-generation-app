# Test fixtures

## `shopify_products_sample.csv`

A 25-handle slice of a real Shopify product export, kept because the catalogue derivation rules in
`app/domains/catalogue/enrichment.py` exist for quirks that only real data has: `Type` empty on
most listings, taxonomy paths in `Product Category`, prices inside `SEO Description`, and store
tags that never use the `segment:` prefix the importer originally looked for.

**Money has been removed.** `Cost per item` and `Variant Compare At Price` are blank, and every
`Variant Price` is the synthetic value `9.99` so the `_pricing` path still has something to derive
from. The repository's `.gitignore` excludes `/products_export*.csv` precisely because a real export
carries cost figures, and this fixture must never reintroduce them.

**If you regenerate this fixture from a newer export, strip the money first** and check it before
committing:

```bash
python - <<'PY'
import csv, io, pathlib
p = pathlib.Path("apps/backend/tests/fixtures/shopify_products_sample.csv")
rows = list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8"))))
money = [c for c in rows[0] if c and any(w in c.lower() for w in ("cost", "price", "profit", "margin"))]
for c in money:
    vals = sorted({(r.get(c) or "").strip() for r in rows if (r.get(c) or "").strip()})
    if vals and vals != ["9.99"]:
        print("LEAK:", c, vals)
PY
```

Product titles, descriptions, handles and tags are public on the storefront and are left as they
are — the derivation rules are tested against real wording, which is the point of the fixture.
