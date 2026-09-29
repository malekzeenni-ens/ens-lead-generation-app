"""Catalogue questions the app answers itself, without the local model.

"What products do we have?" has an exact answer in the database. Given twelve ranked products,
the 3B model lists them as if they were the whole range, and it cannot reliably write out a
hundred lines. So a broad catalogue question gets an overview by group that ends by asking what
to show, and the reply to that ("all", a group or a trade) gets the exact list. Anything else
goes to the model as before.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.db.models import AssistantMessage, Product
from app.domains.catalogue import enrichment
from app.domains.catalogue.repository import CatalogueRepository

# Stored as the message's model name, so the conversation shows the app wrote it and a reply to
# it can be recognised as a reply to the overview.
CATALOGUE_MODEL_NAME = "app:catalogue"

_TRIGGER = re.compile(r"\b(?:products?|catalogu?e|range|sell|selling|stock)\b")
# Words that carry no subject. A catalogue question made only of these is a broad one.
_FILLER = frozenset(
    {
        "a",
        "about",
        "all",
        "an",
        "any",
        "are",
        "at",
        "available",
        "can",
        "catalog",
        "catalogue",
        "complete",
        "count",
        "currently",
        "current",
        "do",
        "does",
        "entire",
        "every",
        "everything",
        "for",
        "full",
        "give",
        "got",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "items",
        "kind",
        "kinds",
        "list",
        "many",
        "me",
        "moment",
        "much",
        "my",
        "now",
        "number",
        "of",
        "offer",
        "on",
        "our",
        "please",
        "product",
        "products",
        "range",
        "right",
        "sell",
        "selling",
        "show",
        "sort",
        "sorts",
        "stock",
        "tell",
        "that",
        "the",
        "there",
        "this",
        "to",
        "today",
        "total",
        "type",
        "types",
        "us",
        "we",
        "what",
        "which",
        "whole",
        "you",
        "your",
    }
)
_FULL_LIST = frozenset({"all", "every", "everything", "full", "entire", "whole", "complete"})
# A reply to the overview made only of these asks for the full list.
_AFFIRMATIVE = frozenset(
    {
        "all",
        "ahead",
        "do",
        "entire",
        "every",
        "everything",
        "full",
        "go",
        "it",
        "list",
        "lot",
        "me",
        "of",
        "ok",
        "okay",
        "one",
        "ones",
        "please",
        "products",
        "show",
        "sure",
        "the",
        "them",
        "whole",
        "yeah",
        "yep",
        "yes",
    }
)
_DECLINE = frozenset({"no", "nope", "cancel", "nothing", "stop"})
_NAME_STOP_WORDS = frozenset({"and", "the", "for"})
_OVERVIEW_EXAMPLES = 2
_TOP_TRADES = 3
_SUMMARY_LIMIT = 110
# Product names read "short name, spaced dash, detail"; the short name is enough in an overview.
_NAME_SEPARATOR = re.compile(r"\s[-" + chr(0x2013) + chr(0x2014) + r"]\s")


def product_group(product: Product) -> str:
    group = str((product.attributes or {}).get("group") or "").strip()
    return group or enrichment.derive_group(product.name, product.category)


def listable(products: Iterable[Product]) -> list[Product]:
    return [product for product in products if not enrichment.is_add_on(product.name)]


def answer(session: Session, content: str, previous: AssistantMessage | None) -> str | None:
    """The app's own reply to a catalogue question, or None to let the model answer."""
    words = _words(content)
    if not words:
        return None
    products = listable(CatalogueRepository().list(session, active=True))
    if not products:
        return None
    if previous is not None and previous.model_name == CATALOGUE_MODEL_NAME:
        reply = _reply_to_overview(words, products)
        if reply is not None:
            return reply
    if not _TRIGGER.search(content.casefold()):
        return None
    subject = [word for word in words if word not in _FILLER]
    if not subject:
        return _full_list(products) if _FULL_LIST & set(words) else _overview(products)
    # "What drinkware do we sell?" names a group outright. Anything with other words in it,
    # such as "what products suit a gym?", wants advice and goes to the model.
    return _named_listing(subject, products, require_all=True)


def _reply_to_overview(words: list[str], products: list[Product]) -> str | None:
    if _DECLINE & set(words):
        return None
    subject = [word for word in words if word not in _AFFIRMATIVE | _FILLER]
    if not subject:
        return _full_list(products)
    # "Drinkware" or "show me the cafés" picks a list; "which is best for a wedding?" has words
    # that are not a group or trade, so it is a question for the model.
    return _named_listing(subject, products, require_all=True)


def _named_listing(subject: list[str], products: list[Product], *, require_all: bool) -> str | None:
    """A group's or trade's list when the subject names one; with `require_all`, only when every
    subject word belongs to that name."""
    stems = {_stem(word) for word in subject}
    groups = sorted({product_group(product) for product in products})
    for names, render in (
        (groups, lambda name: _group_list(name, products)),
        (list(enrichment.SEGMENTS), lambda name: _trade_list(name, products)),
    ):
        best, best_score = None, 0
        for name in names:
            score = len(stems & _name_stems(name))
            if score > best_score:
                best, best_score = name, score
        if best is not None and (not require_all or best_score == len(stems)):
            return render(best)
    return None


def _overview(products: list[Product]) -> str:
    by_group = _by_group(products)
    lines = [f"You have {len(products)} products in {len(by_group)} groups:"]
    for group, members in by_group:
        examples = ", ".join(
            _short_name(product)
            for product in sorted(members, key=lambda item: (not item.b2b_relevant, item.name))[
                :_OVERVIEW_EXAMPLES
            ]
        )
        lines.append(f"- {group} ({len(members)}), e.g. {examples}")
    trades = Counter(
        segment
        for product in products
        for segment in product.target_segments
        if segment in enrichment.SEGMENT_SET
    )
    if trades:
        top = ", ".join(f"{name} ({count})" for name, count in trades.most_common(_TOP_TRADES))
        lines += ["", f"The trades with the most products tagged for them: {top}."]
    lines += ["", 'Which group or trade would you like to see? Or reply "all" for the full list.']
    return "\n".join(lines)


def _full_list(products: list[Product]) -> str:
    lines = [f"All {len(products)} products, by group:"]
    for group, members in _by_group(products):
        lines += ["", f"{group} ({len(members)})"]
        lines += [f"- {product.name}" for product in sorted(members, key=lambda item: item.name)]
    lines += ["", "Name a group or a trade for a one-line description of each product."]
    return "\n".join(lines)


def _group_list(group: str, products: list[Product]) -> str:
    members = [product for product in products if product_group(product) == group]
    return _described(f"{group}: {len(members)} products", members)


def _trade_list(trade: str, products: list[Product]) -> str:
    members = [product for product in products if trade in product.target_segments]
    if not members:
        return (
            f"No products are tagged for {trade} yet. Tag products for this trade in the "
            "knowledge pack, or ask me which products could suit it."
        )
    return _described(f"{trade}: {len(members)} products tagged for this trade", members)


def _described(heading: str, members: list[Product]) -> str:
    lines = [heading]
    for product in sorted(members, key=lambda item: item.name):
        summary = _first_sentence(product.summary)
        lines.append(f"- {product.name}: {summary}" if summary else f"- {product.name}")
    return "\n".join(lines)


def _by_group(products: list[Product]) -> list[tuple[str, list[Product]]]:
    grouped: defaultdict[str, list[Product]] = defaultdict(list)
    for product in products:
        grouped[product_group(product)].append(product)
    # Largest first, with the catch-all group last whatever its size.
    return sorted(
        grouped.items(),
        key=lambda item: (item[0] == enrichment.OTHER_GROUP, -len(item[1]), item[0]),
    )


def _first_sentence(summary: str | None) -> str:
    # Summaries are price-free when stored; stripping again keeps this path safe on its own.
    text = enrichment.strip_prices(summary or "")
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return sentence if len(sentence) <= _SUMMARY_LIMIT else sentence[: _SUMMARY_LIMIT - 1] + "…"


def _short_name(product: Product) -> str:
    return _NAME_SEPARATOR.split(product.name, maxsplit=1)[0]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9&']+", _fold(text))


def _name_stems(name: str) -> set[str]:
    return {_stem(word) for word in _words(name) if word not in _NAME_STOP_WORDS and len(word) > 2}


def _stem(word: str) -> str:
    # Plural to singular, just enough to match "cafes" to "cafe" and "nurseries" to "nursery".
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))
