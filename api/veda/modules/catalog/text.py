"""Customer-visible text governance (V3 customer-safety closure).

**Field classes.** Every string-bearing field of every catalog document model is classified in FIELD_CLASSES:

| Class | Meaning |
|---|---|
| `factual` | Free text a customer can read (a name, description, label or caption). It may carry no promise wording, no marketing claim and none of the always-forbidden content: amounts, pricing words, durations, contact details |
| `statement` | A copy record's statement, the only place a promise or claim may be made. A promise needs its promise-matrix row (ESSENTIAL-1.1); a claim needs its claim governance; otherwise it is held to the factual rule |
| `staff` | Never sent to customers (stripped from the customer view) |
| `identifier` | A key, code, closed choice, hash, URL or date; not prose |

`tests/unit/test_catalog_text_inventory.py` enumerates the models' fields by type and fails when a string-bearing field is
missing from FIELD_CLASSES, so a new customer-visible field cannot ship unclassified. The inventory document
(`docs/implementation/catalog/CATALOG-V3-customer-text-inventory.md`) is generated from this registry and checked to
be current.

**Claims** are matched as words and phrases, never substrings. "Premium" or "Luxury" alone name a package tier (a
fact); "premium pick", "premium quality" and "luxury choice" are claims. "Top shelf", "countertop" and
"space-saving" are facts; "top rated", "save up to" and "best" are claims.
"""

from __future__ import annotations

import hashlib
import re
import types
import typing
import unicodedata
from collections.abc import Iterator

from pydantic import BaseModel

from veda.modules.estimator import customer_spec

# --- canonical normalisation (canonical customer-copy closure) -----------------------------------------------------
# One normalisation for every check: claims, promises, money, controlled-copy matching, release validation and the
# public serialisers' check at serve time. The approved display text is never rewritten; newly authored text with
# invisible or formatting characters, or with words mixing scripts, is refused, and detection runs on canonical forms.
# Detection is defence in depth: the primary controls are the content policy of each field, governed claim records
# with four-eyes review, and typed engine-generated amounts (no money is ever authored in prose).
_CONFUSABLES = str.maketrans({
    # Cyrillic and Greek letters that look like Latin ones (after case folding), and a few Latin lookalikes.
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c", "т": "t",
    "у": "y", "х": "x", "і": "i", "ї": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ӏ": "l", "һ": "h", "ԛ": "q", "ԝ": "w",
    "ɡ": "g", "ı": "i", "ℓ": "l", "ο": "o", "α": "a", "ν": "v", "ι": "i", "κ": "k", "ρ": "p", "τ": "t", "υ": "u",
    "χ": "x", "ε": "e", "β": "b", "η": "n", "μ": "u", "ς": "s", "σ": "o", "ɑ": "a", "ɩ": "i", "ʋ": "u", "ԅ": "d",
    # Latin small capitals (no compatibility decomposition in NFKC).
    "ᴀ": "a", "ʙ": "b", "ᴄ": "c", "ᴅ": "d", "ᴇ": "e", "ꜰ": "f", "ɢ": "g", "ʜ": "h", "ɪ": "i", "ᴊ": "j", "ᴋ": "k",
    "ʟ": "l", "ᴍ": "m", "ɴ": "n", "ᴏ": "o", "ᴘ": "p", "ꞯ": "q", "ʀ": "r", "ꜱ": "s", "ᴛ": "t", "ᴜ": "u", "ᴠ": "v",
    "ᴡ": "w", "ʏ": "y", "ᴢ": "z",
})  # fmt: skip
_SEPARATOR = re.compile(r"[\s_/\\.:|·•‧∙⁄,;!?¡¿\"“”„«»()\[\]{}*~^`+=<>]+")
_APOSTROPHE = re.compile(r"['’‘ʼ`´]")
_SPACED_LETTERS = re.compile(r"\b(?:[a-z0-9] ){2,}[a-z0-9]\b")  # "b e s t" → "best" (letter-spacing evasion)
# Factual compounds whose parts would otherwise read as claims (kept narrow on purpose).
_FACTUAL_COMPOUNDS = re.compile(
    r"\b(?:free ?standing|hands ?free|top ?hung|top ?mounted|best ?fit ?hinge|leading ?edges?)\b"
)
# Narrow leetspeak, applied only inside words that mix letters with these characters, and only for claim detection
# (never to the stored text or to the money check): "b3st", "fr33", "$ale", "l1fetime".
_LEET = ({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"},
         {"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})  # fmt: skip
_LEET_WORD = re.compile(r"[a-z0-9@$]*[a-z][a-z0-9@$]*")
_SLASHES = str.maketrans({"⁄": "/", "∕": "/", "⧸": "/", "／": "/", "∖": "\\"})


def _invisible(ch: str) -> bool:
    cp = ord(ch)
    return (
        (unicodedata.category(ch) in ("Cf", "Cc", "Co", "Cs", "Cn") and ch not in "\t\n\r")
        or 0xFE00 <= cp <= 0xFE0F
        or 0xE0100 <= cp <= 0xE01EF
        or 0x180B <= cp <= 0x180F
        or cp == 0x034F
    )


def invisible_chars(text: str) -> list[str]:
    """The invisible or formatting characters in a text (zero-width, joiners, word joiner, BOM, soft hyphen,
    directional controls, variation selectors and other format or control characters). New customer text with any of
    them is refused."""
    return sorted({f"U+{ord(ch):04X}" for ch in text if _invisible(ch)})


def _script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    for script in ("LATIN", "CYRILLIC", "GREEK"):
        if name.startswith(script):
            return script
    return "OTHER"


def mixed_script_words(text: str) -> list[str]:
    """Words that mix Latin, Cyrillic or Greek letters (a lookalike spoof such as "Bеst"). New customer text with any
    is refused; detection maps them to Latin either way."""
    out = []
    for word in re.findall(r"\w+", unicodedata.normalize("NFKC", text)):
        scripts = {_script(ch) for ch in word} - {None}
        if len(scripts) > 1:
            out.append(word)
    return out


def _base(text: str) -> str:
    s = unicodedata.normalize("NFKC", text)  # fullwidth and compatibility forms, ligatures, superscripts, spaces
    s = "".join(ch for ch in s if not _invisible(ch))
    # Combining marks are dropped for comparison ("Bést", "B̲e̲s̲t̲"); the stored display text keeps them.
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if unicodedata.category(ch) not in ("Mn", "Me"))
    s = unicodedata.normalize("NFKC", s).casefold().translate(_CONFUSABLES)
    return "".join(" " if unicodedata.category(ch) in ("Zs", "Zl", "Zp") else ch for ch in s)


def numeric_form(text: str) -> str:
    """Canonical form that keeps digits and punctuation (for money, rates and measurements)."""
    s = "".join("-" if unicodedata.category(ch) == "Pd" else ch for ch in _base(text)).translate(_SLASHES)
    s = re.sub(r"\bpercent\b|\bpct\b|\bper cent\b", "%", s)
    return re.sub(r"\s+", " ", s).strip()


def canonical(text: str) -> str:
    """The comparison form: NFKC, invisible characters and combining marks removed, case-folded, lookalikes and small
    capitals mapped, every separator (space, underscore, any dash, slash, backslash, dot, colon, pipe, punctuation) a
    single space, letter-spaced runs joined. Detection matches whole words and phrases, never substrings."""
    s = "".join(" " if unicodedata.category(ch) == "Pd" else ch for ch in _base(text))
    s = _APOSTROPHE.sub("", s)
    s = _SEPARATOR.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _SPACED_LETTERS.sub(lambda m: m.group(0).replace(" ", ""), s)
    return re.sub(r"\s+", " ", _FACTUAL_COMPOUNDS.sub(" ", s)).strip()


def _detection_forms(text: str) -> list[str]:
    """The canonical form and its narrow leetspeak readings (claim detection only)."""
    form = canonical(text)
    forms = [form]
    for table in _LEET:

        def read(m: re.Match[str], table: dict[str, str] = table) -> str:
            word = m.group(0)
            return "".join(table.get(ch, ch) for ch in word) if any(ch in table for ch in word) else word

        leet = _LEET_WORD.sub(read, form)
        if leet != form:
            forms.append(leet)
    return forms


def canonical_digest(text: str) -> str:
    return hashlib.sha256(canonical(text).encode()).hexdigest()


def display_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --- governed claims (matched on the canonical forms) ----------------------------------------------------------------
def _words(*alternatives: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alternatives) + r")(?![a-z0-9])")


# Promise wording (R2/R3) that factual catalog text may not use: technical grades, brands, inclusions and durations
# are stated only by a promise copy record linked to its confirmed promise-matrix row.
PROMISE = _words(
    r"warrant\w*", r"guarantee\w*", r"assur\w*", r"certif\w*", r"lifetime", r"life ?long", r"free", r"complimentary",
    r"no cost", r"includ\w*", r"inclusive", r"exclud\w*", r"install\w*", r"deliver\w*", r"dispatch\w*", r"timeline\w*",
    r"on ?time", r"deadline\w*", r"\d+ ?(?:days?|weeks?|months?|years?|hours?|hrs?)", r"within \w+ (?:days?|hours?)",
    r"grade\w*", r"bwr", r"bwp", r"mr", r"e[0-2]", r"is ?\d+", r"marine", r"water ?proof", r"\w+ ?proof",
    r"termite\w*", r"borer\w*", r"brand\w*", r"genuine", r"original", r"hettich", r"hafele", r"blum", r"ebco",
    r"century", r"greenply", r"merino", r"greenlam", r"airolam", r"servic\w*", r"support\w*", r"after ?sales",
    r"maintenance(?: free)?", r"repair\w*", r"replac\w*", r"soft ?clos\w*", r"call ?back\w*", r"one ?day",
    r"24 ?(?:x ?)?7",
)  # fmt: skip

# Every category below is a governed claim: it may be shown only through an approved claim record (or, for
# warranty, service and durability promises, a promise record linked to its confirmed promise-matrix row).
# "Premium" and "Luxury" are package tier names: alone, or followed by "package" or "tier", they are facts; as an
# adjective ("premium laminate") they are quality claims.
_TIER = r"(?:premium|luxur\w*)(?! (?:packages?|tiers?)\b)"
CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ranking", _words(r"best", r"finest", r"no ?1", r"number ?(?:one|1)", r"# ?1", r"first choice",
                       r"top (?:rated|ranked|\d+|ten|five|three)", r"leading", r"(?:market|industry|category) leaders?",
                       r"leaders? in", r"unbeatable", r"unmatched", r"unrivall?ed", r"unparall?ell?ed", r"world class",
                       r"best in class", r"second to none", r"ultimate", r"the very best",
                       r"(?:india|hyderabad|bengaluru|bangalore|indias|the citys) (?:best|leading|favou?rite|top)")),
    ("price", _words(r"cheapest", r"lowest(?: price| cost| rates?)?", r"budget friendly", r"affordabl\w*",
                     r"best price", r"price match\w*", r"most economical", r"unbeatable price")),
    ("popularity", _words(r"best ?sell\w*", r"most (?:popular|chosen|loved|ordered|wanted|requested|booked|trusted)",
                          r"popular", r"trending", r"favou?rite\w*", r"top (?:choice|seller|selling)", r"in demand",
                          r"hot ?selling", r"highly (?:rated|recommended|reviewed)", r"(?:five|5|four|4) ?stars?",
                          r"\d(?:\.\d)? ?star rated", r"rated \d", r"trusted by", r"loved by", r"most trusted",
                          r"thousands of (?:happy )?customers", r"customer favou?rite")),
    ("recommendation", _words(r"recommend\w*", r"(?:our|editors|staff|designers|experts?) (?:premium )?(?:pick|choice)",
                              r"premium (?:pick|choice)", r"luxury (?:pick|choice)", r"must ?have", r"top pick")),
    ("quality", _words(r"(?:high|highest|best|top|superior|finest|great|excellent|premium|world class|supreme) quality",
                       r"superior", r"flawless", r"perfect\w*", r"top notch", r"impeccable", r"high end",
                       r"finest", r"exquisite", _TIER)),
    ("certification", _words(r"certif\w*", r"accredit\w*", r"iso ?\d+", r"isi(?: mark\w*)?", r"bis (?:certified|mark)",
                             r"approved by", r"lab tested", r"tested (?:to|and approved|for)", r"compliant",
                             r"conforms? to")),
    ("award", _words(r"award\w*", r"prize\w*", r"winners?", r"winning")),
    ("warranty", _words(r"lifetime", r"warrant\w*", r"guarantee\w*", r"assured", r"assurance")),
    ("service", _words(r"deliver\w*", r"on ?time", r"one ?day call ?back", r"call ?back\w*", r"24 ?(?:x ?)?7",
                       r"round the clock", r"same day", r"next day", r"within \d+ (?:hours?|days?|weeks?)",
                       r"after ?sales", r"servic\w*", r"dedicated (?:support|manager)",
                       r"free (?:service|consultation|visit|design)")),
    ("durability", _words(r"maintenance free", r"low maintenance", r"durab\w*", r"long lasting", r"lasts? (?:a )?life ?time",
                          r"\w+ ?proof", r"\w+ resistant", r"resistance", r"never (?:fades?|rusts?|warps?|peels?)",
                          r"(?:rust|stain|fade|scratch) ?free", r"unbreakable", r"indestructible", r"forever")),
    ("environmental", _words(r"eco ?friendly", r"environment(?:ally)? friendly", r"sustainab\w*", r"non ?toxic",
                             r"toxin ?free", r"(?:low|zero) voc", r"voc free", r"formaldehyde free", r"child ?safe",
                             r"(?:fire|flame) retardant", r"safe for (?:kids|children|family|families|food)",
                             r"food safe", r"hygienic", r"anti ?bacterial", r"zero emissions?", r"emission free")),
    ("promotional", _words(r"free", r"complimentary", r"at no (?:extra )?(?:cost|charge)", r"no (?:extra|hidden|additional) (?:costs?|charges?|fees?)",
                           r"great value", r"best value", r"value for money", r"bargain\w*", r"discount\w*", r"sale",
                           r"deals?", r"(?:special|exclusive|festive|launch|introductory|seasonal|limited) offers?",
                           r"on offer", r"offer price", r"bonus", r"gift\w*", r"save (?:up to|\d+(?:\.\d+)? ?%?|on|big|more|money)",
                           r"savings", r"cash ?back", r"coupon\w*", r"promo\w*", r"\d+ ?% ?off", r"% ?off",
                           r"flat \d+ ?%", r"up ?to \d+ ?%", r"new arrivals?", r"exclusiv\w*")),
    ("urgency", _words(r"only today", r"today only", r"act (?:now|fast|quickly)", r"hurry", r"limited (?:time|period|stock|edition|slots?|availability)",
                       r"offer ends?(?: soon| today)?", r"ends (?:soon|today|tonight)", r"last chance",
                       r"while stocks? lasts?", r"few (?:left|remaining)", r"selling fast", r"(?:book|order|buy) now",
                       r"don ?t miss", r"now or never", r"before (?:its|it is) gone")),
)  # fmt: skip
CATEGORIES = tuple(c for c, _ in CLAIMS)
# Categories a promise record (linked to its confirmed promise-matrix row) may carry instead of a claim record.
PROMISE_CATEGORIES = ("warranty", "service", "durability")
# Claims that also need independent substantiation and a backup owner.
ABSOLUTE = _words(r"best", r"no ?1", r"number ?(?:one|1)", r"# ?1", r"first choice", r"cheapest", r"lowest",
                  r"guarantee\w*", r"unbeatable", r"unmatched", r"unrivall?ed", r"finest", r"highest quality", r"leading",
                  r"(?:market|industry) leaders?", r"top \d+", r"lifetime", r"most trusted")  # fmt: skip
_TIER_NAME = re.compile(r"^(?:premium|luxury|essential)(?: (?:package|tier))?$")


def claims_in(text: str) -> list[str]:
    """The claim categories a text makes (empty for factual text), detected on its canonical and leetspeak forms."""
    forms = _detection_forms(text)
    if _TIER_NAME.match(forms[0]):
        return []  # a package tier's own name is a fact
    return sorted({category for category, pattern in CLAIMS for form in forms if pattern.search(form)})


def marketing_claims_in(text: str) -> list[str]:
    """Kept for callers of the earlier interface: every claim category is governed."""
    return claims_in(text)


def promise_in(text: str) -> bool:
    return any(PROMISE.search(form) for form in _detection_forms(text))


def absolute_in(text: str) -> bool:
    return any(ABSOLUTE.search(form) for form in _detection_forms(text))


# --- money in prose: category-level classification (B1) --------------------------------------------------------------
# The primary control is structural: public money appears only in typed, engine-generated amount fields, and no
# customer prose field may carry money. Prose is checked by classifying every number it contains, whatever its value
# and however it is written (digits, grouping, decimals, magnitudes, spelled-out words), by the role its context gives
# it. Only allowlisted roles are permitted: a MEASUREMENT (a number with a length, area, volume, weight or angle
# unit), a DURATION (with a time unit), a QUANTITY (counting a thing: "3 rooms"), a RANGE of those, a DATE or YEAR, or
# a LABEL INDEX ("Bedroom 2"). Every other number is money and is classified as:
#   RATE              an amount per anything ("per", "/", "each", "every", "a/an <unit>"), or under rate wording
#   DISCOUNT          a percentage, or an amount with saving, discount, off or cashback wording
#   COMMISSION        commission, brokerage or referral wording
#   PROMOTIONAL PRICE a currency amount, a magnitude (k, lakh, crore), a price qualifier ("only", "extra",
#                     "starting at"), or a number with no allowlisted role
# Commercial vocabulary is classified by category whether or not a number is present.
RATE, DISCOUNT, COMMISSION, PROMOTIONAL_PRICE = "RATE", "DISCOUNT", "COMMISSION", "PROMOTIONAL PRICE"
MONEY_CATEGORIES = (RATE, DISCOUNT, COMMISSION, PROMOTIONAL_PRICE)
_LABELS = {RATE: "a rate", DISCOUNT: "a discount", COMMISSION: "a commission", PROMOTIONAL_PRICE: "a promotional price"}

# Unit spellings folded to one token first, so "sq-ft", "s.ft", "ft²", "square feet" and "running foot" read alike.
_UNIT_FOLDS = (
    (re.compile(r"\b(?:sq(?:uare)?\.?\s*-?\s*f(?:ee|oo)?t\.?|s\.\s*ft\.?|ft\s*\^?\s*2|sqft|sft)(?![a-z])"), " sqft "),
    (re.compile(r"\b(?:sq(?:uare)?\.?\s*-?\s*(?:m|mtrs?|met(?:er|re)s?)|m\s*\^?\s*2|sqm)(?![a-z])"), " sqm "),
    (re.compile(r"\b(?:running|linear|lin\.?)\s*(?:f(?:ee|oo)?t|ft|met(?:er|re)s?|m)(?![a-z])|\br\.?\s*f\.?\s*t\b|\brft\b"), " rft "),
    (re.compile(r"\b(?:cu(?:bic)?\.?\s*-?\s*f(?:ee|oo)?t|cft)(?![a-z])"), " cft "),
)  # fmt: skip
MEASUREMENT_UNITS = frozenset({
    "mm", "cm", "m", "km", "in", "inch", "inches", "ft", "feet", "foot", "yd", "yds", "yard", "yards", "metre",
    "metres", "meter", "meters", "mtr", "mtrs", "sqft", "sqm", "rft", "cft", "rmt", "kg", "kgs", "g", "gm", "gsm",
    "litre", "litres", "liter", "liters", "ltr", "ml", "deg", "degree", "degrees", "w", "watt", "watts", "v", "volt",
    "volts", "amp", "amps", "hp", "bhk", "°", "′", "″", "'", '"', "x", "×",
})  # fmt: skip
DURATION_UNITS = frozenset({
    "sec", "secs", "second", "seconds", "min", "mins", "minute", "minutes", "hr", "hrs", "hour", "hours", "day", "days",
    "week", "weeks", "fortnight", "fortnights", "month", "months", "year", "years", "yr", "yrs", "working", "business",
    "calendar",
})  # fmt: skip
_CURRENCY_WORDS = frozenset(
    {"rs", "inr", "usd", "rupee", "rupees", "dollar", "dollars", "paise", "bucks", "grand", "eur"}
)
_CURRENCY_SIGNS = frozenset("₹$€£¥")
_MAGNITUDES = frozenset({"k", "l", "lac", "lacs", "lakh", "lakhs", "cr", "crore", "crores", "mn", "million", "thousand",
                         "hundred", "bn", "billion"})  # fmt: skip
# The approved countable business entities a number may count (QUANTITY is proven, never inferred): the catalog's
# rooms (kinds.RoomCode and the engine's room names), the furniture and joinery it prices, and site visits. Singular
# and plural forms. Extend this lookup, not the classifier, when the catalog adds an entity.
_ENTITIES = (
    "room", "bedroom", "bathroom", "kitchen", "utility", "living", "dining", "study", "pooja", "home", "house",
    "apartment", "villa", "floor", "wall", "ceiling", "drawer", "wardrobe", "panel", "door", "shutter", "shelf",
    "shelves", "cabinet", "cupboard", "unit", "module", "partition", "window", "bed", "storage", "box", "carcass",
    "counter", "countertop", "loft", "basket", "hinge", "handle", "channel", "mirror", "light", "sensor", "pelmet",
    "accessory", "accessories", "item", "piece", "product", "extra", "option", "set", "sheet", "visit", "seater",
    "tier", "section", "compartment", "rack", "sink", "tap", "chimney", "hob", "appliance", "socket", "point",
)  # fmt: skip
QUANTITY_NOUNS = frozenset(
    {e for e in _ENTITIES} | {e + "s" for e in _ENTITIES if not e.endswith(("s", "x"))} | {"boxes", "carcasses",
     "wardrobes", "nos", "pcs", "pieces"} | {"cupboards", "lofts", "benches"}
)  # fmt: skip
# Descriptive words allowed between a number and its entity ("2 extra drawers", "3 base units", "4 soft-close hinges").
QUANTITY_DESCRIPTORS = frozenset({
    "extra", "additional", "more", "base", "wall", "tall", "loft", "sliding", "hinged", "open", "closed", "glass",
    "soft", "soft-close", "close", "top", "bottom", "side", "corner", "overhead", "standard", "new", "selected",
    "small", "large", "medium", "full", "half", "single", "double", "built-in", "fitted", "matching", "storage",
    "kitchen", "tv", "pull-out", "-",
})  # fmt: skip
PERIODIC_WORDS = frozenset({"daily", "weekly", "fortnightly", "monthly", "quarterly", "yearly", "annually", "annual",
                            "hourly", "nightly", "apiece", "pa", "p.a", "pm", "pw"})  # fmt: skip
_TAX_LEADS = frozenset({"plus", "+", "including", "incl", "inclusive", "excluding", "excl", "exclusive", "with",
                        "without", "inc", "ex"})  # fmt: skip
_TAX_WORDS = frozenset({"gst", "tax", "taxes", "vat", "cess", "duty", "duties", "levies"})
_MONEY_MAGNITUDES = frozenset({"k", "l", "lac", "lacs", "lakh", "lakhs", "cr", "crore", "crores", "mn", "million",
                               "bn", "billion"})  # fmt: skip
_RATE_CONNECTORS = frozenset({"per", "/", "each", "every", "pp", "p"})
_RATE_ABBREVIATIONS = frozenset({"psf", "psm", "prft"})  # per sq ft, per sq m, per running foot
_RANGE_JOINERS = frozenset({"to", "-", "–", "—", "or", "/", "and", "by", "x", "×"})
_QUALIFIERS_AFTER = frozenset({"only", "extra", "onwards", "upwards", "additional", "net", "flat", "inclusive",
                               "payable", "all-inclusive", "nett", "plus", "+"})  # fmt: skip
_QUALIFIERS_BEFORE = ("only", "just", "starting at", "starting from", "from just", "at just", "for just", "for only",
                      "@", "at only", "worth", "costs", "cost", "priced at", "price", "for rs", "pay")  # fmt: skip
# Series labels a number may index ("Bedroom 2", "Option 3", "Specification 1.1"); never ordinary nouns, so
# "Door 1200" or "Shutter: 1200" is still an unattached amount.
_LABEL_WORDS = frozenset({"package", "bedroom", "bathroom", "option", "step", "phase", "stage", "version", "v", "specification",
                          "spec", "type", "model", "series", "level", "floor", "block", "tower", "wing", "section",
                          "page", "zone", "release", "grade", "class", "iso", "is", "e", "batch"})  # fmt: skip
_RANK_LABELS = frozenset({"no", "number", "top", "rank", "ranked", "rated"})
_DATE_LEAD = frozenset({"in", "since", "from", "until", "till", "by", "of", "year", "est", "established", "founded",
                        "©", "before", "after", "during", "fy"})  # fmt: skip
DISCOUNT_WORDS = frozenset({"save", "saving", "savings", "saved", "discount", "discounts", "discounted", "off",
                            "cashback", "cash-back", "rebate", "rebates", "deal", "deals", "offer", "offers", "sale",
                            "reduction", "reduced", "slashed", "markdown"})  # fmt: skip
COMMISSION_WORDS = frozenset({"commission", "commissions", "commissioned", "brokerage", "kickback", "kickbacks",
                              "referral", "finder's", "finders"})  # fmt: skip
RATE_WORDS = frozenset({"rate", "rates", "mrp", "margin", "margins", "markup", "markups", "mark-up", "procurement",
                        "supplier", "suppliers", "wholesale", "dealer", "dealers", "tariff", "emi", "emis"})  # fmt: skip
# Commercial phrases that are money whatever follows (multi-word; matched on the numeric form).
_COMMERCIAL_PHRASES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (RATE, re.compile(r"\b(?:trade|list|net|basic|base|unit|buying|purchase|cost|landed|vendor|dealer|distributor|"
                      r"supplier|wholesale|ex-?factory|ex-?showroom)\s*(?:price|rate|cost)s?\b|\bprice\s*(?:cap|ceiling|"
                      r"list|band|per)\b|\bceiling\s*price\b|\brate\s*card\b|\bper\s*(?:unit|item|piece)\s*(?:cost|"
                      r"price|rate)\b|\bvendor\s*cost\b")),
    (COMMISSION, re.compile(r"\breferral\s*(?:fees?|bonus|amount)\b|\bfinder'?s?\s*fees?\b")),
)  # fmt: skip
_NUMBER_WORDS = frozenset({"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                           "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
                           "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
                           "hundred", "thousand", "lakh", "lakhs", "crore", "crores", "million", "dozen"})  # fmt: skip
_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?|\.\d+|[a-z]+(?:'[a-z]+)?|[₹$€£¥%/′″'\"@+×°\-–—]|[^\s\w]")
_CODE = re.compile(r"\b([a-z]+)-?\d[a-z0-9]*(?:-[a-z0-9]+)*\b")  # "e1", "x1", "i-401", "tv-12b"
_DIGIT_CODE = re.compile(r"\b(\d+)([a-z]+)\b")
_DATE = re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b|\b\d{1,2}:\d{2}(?::\d{2})?\b")


def _tokens(text: str) -> list[str]:
    form = numeric_form(text)
    form = _DATE.sub(" ⟨date⟩ ", form)
    for pattern, unit in _UNIT_FOLDS:
        form = pattern.sub(unit, form)
    # A code glued to letters ("x1", "e1", "r2d2") is an identifier, unless the letters are a currency ("rs1200").
    form = _CODE.sub(lambda m: m.group(0) if m.group(1) in _CURRENCY_WORDS else " ⟨code⟩ ", form)
    # A digit-led code ("3d", "2a", "5g") is an identifier unless its letters are a unit, magnitude, duration or
    # currency ("18mm", "12k", "3days", "1200rs" keep their roles).
    form = _DIGIT_CODE.sub(
        lambda m: (
            m.group(0)
            if m.group(2) in MEASUREMENT_UNITS | DURATION_UNITS | _MAGNITUDES | _CURRENCY_WORDS | PERIODIC_WORDS
            else " ⟨code⟩ "
        ),
        form,
    )
    return [t for t in _TOKEN.findall(form) if t.strip()]


def _is_number(token: str) -> bool:
    return token[0].isdigit() or token[0] == "." and token[1:2].isdigit() or token in _NUMBER_WORDS


def _word(token: str | None) -> bool:
    return token is not None and token != "" and token[0].isalpha()


def _role(toks: list[str], i: int) -> str | None:
    """The role of the number at toks[i]: an allowlisted role (None) or a money category."""
    j = i + 1
    while j < len(toks) and toks[j] in _NUMBER_WORDS:  # "twelve hundred", "two lakh"
        j += 1
    before = toks[max(0, i - 4) : i]
    prev = toks[i - 1] if i else None
    if set(toks[i + 1 : j]) & _MONEY_MAGNITUDES or (toks[i] in _MONEY_MAGNITUDES and i + 1 == j):
        return _price_kind(toks, j, set(toks[max(0, i - 4) : min(len(toks), j + 4)]))  # "1.2 lakh monthly"
    near = set(toks[max(0, i - 4) : min(len(toks), j + 4)])
    # Currency on either side, or a /- suffix: a stated price.
    if (prev in _CURRENCY_SIGNS or prev in _CURRENCY_WORDS or (j < len(toks) and (toks[j] in _CURRENCY_SIGNS
            or toks[j] in _CURRENCY_WORDS)) or toks[j : j + 2] == ["/", "-"]):  # fmt: skip
        return _price_kind(toks, j, near)
    nxt = toks[j] if j < len(toks) else None
    after = toks[j + 1] if j + 1 < len(toks) else None
    if nxt == "%":
        if near & COMMISSION_WORDS:
            return COMMISSION
        return DISCOUNT if near & DISCOUNT_WORDS else RATE  # a percentage in prose is a rate unless it is a saving
    if nxt in _MAGNITUDES and not (after == "-" or (nxt == "l" and after and after.startswith("shape"))):
        return _price_kind(toks, j + 1, near)
    if nxt in COMMISSION_WORDS or (before and set(before) & COMMISSION_WORDS):
        return COMMISSION
    if nxt in DISCOUNT_WORDS or (prev in DISCOUNT_WORDS):
        return DISCOUNT
    if nxt in _RATE_CONNECTORS and (nxt in ("each", "every") or _word(after) or after in _CURRENCY_SIGNS):
        return RATE
    if nxt in _RATE_ABBREVIATIONS or (nxt == "for" and after in ("each", "every", "one", "a", "an", "per")):
        return RATE  # "1200 psf", "1200 for every square foot"
    if (
        nxt in ("a", "an")
        and after
        and (after in MEASUREMENT_UNITS or after in DURATION_UNITS or _word(after))
        and (after not in _NUMBER_WORDS)
    ):
        return RATE  # "1200 a shutter", "1200 an hour"
    if nxt in _QUALIFIERS_AFTER and not _word(after):
        return PROMOTIONAL_PRICE  # "1200 extra", "1200 only"
    if nxt in RATE_WORDS:
        return RATE
    # Allowlisted roles: a measurement, a duration, a quantity of a named thing, a range of those.
    if nxt in MEASUREMENT_UNITS or nxt in DURATION_UNITS:
        return _after_measure(toks, j + 1)
    if nxt in _RANGE_JOINERS and after is not None and _is_number(after):
        return None  # "3 to 20 feet", "16/18 mm", "8-10 days": the second number carries the role
    if nxt == "-" and after in MEASUREMENT_UNITS | DURATION_UNITS:
        return _after_measure(toks, j + 2)  # "8-ft wall", "one-day visit"
    if nxt in PERIODIC_WORDS or (nxt == "a" and after == "piece"):
        return RATE  # "1200 monthly", "1200 apiece", "1200 a piece"
    if nxt in ("on", "at", "for", "in") and after in ("every", "each", "per", "a", "an", "all"):
        return RATE  # "1200 on every door", "1200 for each shutter"
    if nxt in _TAX_LEADS and set(toks[j + 1 : j + 4]) & _TAX_WORDS:
        return PROMOTIONAL_PRICE  # "1200 plus GST", "1200 including GST"
    # QUANTITY must be proven: the number counts an approved business entity (QUANTITY_NOUNS), possibly after
    # approved descriptive words. A word after a number does not make it a quantity.
    counted = _quantity(toks, j)
    if counted is not None:
        return _after_measure(toks, counted)
    # No following role: rate wording before it, else a series label index or a year, else an unattached amount.
    if before and set(before) & (_RATE_CONNECTORS | RATE_WORDS):
        return RATE  # "per sqft 1200", "rate: 1200", "per door 5"
    if prev in _LABEL_WORDS:
        return None
    if prev in _RANK_LABELS or prev == "#" or (prev == "." and i >= 2 and toks[i - 2] in _RANK_LABELS):
        return None  # "No. 1", "#1", "Top 10": a ranking label, which the claim rules govern (never money)
    if re.fullmatch(r"(?:19|20)\d\d", toks[i]) and prev in _DATE_LEAD:
        return None
    if prev in _MONEY_LEADS or " ".join(toks[max(0, i - 2) : i]) in _QUALIFIERS_BEFORE:
        return PROMOTIONAL_PRICE
    return PROMOTIONAL_PRICE  # a number with no allowlisted role is never shown as prose


_MONEY_LEADS = frozenset(q for q in _QUALIFIERS_BEFORE if " " not in q) | {"for", "at", "fee", "fees", "charge",
                                                                           "charges", "amount", "budget", "total"}  # fmt: skip


def _price_kind(toks: list[str], j: int, near: set[str]) -> str:
    """A stated amount: a rate when a rate connector follows, otherwise its wording decides."""
    k = j
    while k < len(toks) and (toks[k] in _MAGNITUDES or toks[k] in _CURRENCY_WORDS or toks[k] in _CURRENCY_SIGNS
                             or toks[k] in ("/", "-") and k + 1 < len(toks) and toks[k + 1] == "-"):  # fmt: skip
        k += 1
    nxt = toks[k] if k < len(toks) else None
    if nxt in _RATE_CONNECTORS or nxt in ("a", "an") or nxt in RATE_WORDS:
        return RATE
    if near & COMMISSION_WORDS:
        return COMMISSION
    if near & DISCOUNT_WORDS:
        return DISCOUNT
    return PROMOTIONAL_PRICE


def _quantity(toks: list[str], j: int) -> int | None:
    """The index after the counted entity when toks[j:] proves a quantity ("3 rooms", "2 extra drawers",
    "1 L-shaped counter", "2-door wardrobe"), else None."""
    k = j
    if k < len(toks) and toks[k] == "-":
        k += 1  # "2-door"
    for _ in range(3):
        if k < len(toks) and toks[k] in QUANTITY_DESCRIPTORS:
            k += 1
        elif (
            k + 2 < len(toks)
            and len(toks[k]) == 1
            and toks[k].isalpha()
            and toks[k + 1] == "-"
            and toks[k + 2] in ("shaped", "shape")
        ):
            k += 3  # "L-shaped", "U-shaped"
        else:
            break
    return k + 1 if k < len(toks) and toks[k] in QUANTITY_NOUNS else None


def _after_measure(toks: list[str], k: int) -> str | None:
    """A measurement, duration or quantity is allowed unless a rate connector or money word follows it directly
    ("900 sqft" is allowed; "900 sqft per room" and "3 visits at 1200" are not)."""
    nxt = toks[k] if k < len(toks) else None
    after = toks[k + 1] if k + 1 < len(toks) else None
    if (
        nxt in ("per", "/")
        and after is not None
        and (after in _CURRENCY_SIGNS or after in _CURRENCY_WORDS or _is_number(after))
    ):
        return RATE
    return None


def money_categories(text: str) -> list[str]:
    """The money categories a prose text contains (empty when it contains none): every number is classified by its
    role, and commercial vocabulary by its category."""
    toks = _tokens(text)
    found: list[str] = []
    for i, tok in enumerate(toks):
        if tok in _CURRENCY_SIGNS:
            found.append(PROMOTIONAL_PRICE)
        elif tok in COMMISSION_WORDS:
            found.append(COMMISSION)
        elif tok in RATE_WORDS:
            found.append(RATE)
        elif tok in ("discount", "discounts", "discounted", "cashback", "cash-back", "rebate", "rebates"):
            found.append(DISCOUNT)
        elif _is_number(tok) and not (i and toks[i - 1] in _NUMBER_WORDS and tok in _NUMBER_WORDS):
            if tok in _NUMBER_WORDS and not _spelled_amount(toks, i):
                continue  # "one-day", "two rooms": a spelled count reads as a word unless it states money
            role = _role(toks, i)
            if role:
                found.append(role)
    form = numeric_form(text)
    found += [category for category, pattern in _COMMERCIAL_PHRASES if pattern.search(form)]
    return sorted(set(found), key=MONEY_CATEGORIES.index)


def _spelled_amount(toks: list[str], i: int) -> bool:
    """A spelled-out number states money when its role would be money ("twelve hundred per shutter")."""
    return _role(toks, i) is not None


def money_in(text: str) -> str | None:
    """Why a text carries money (None when it does not): the first money category found, as a phrase."""
    found = money_categories(text)
    return _LABELS[found[0]] if found else None


RATES = MONEY_CATEGORIES  # the earlier name
rate_in = money_in


def forbidden_in(text: str) -> str | None:
    """Content never allowed in factual text: money and rates, pricing words, durations, contact details. Checked on
    the original, numeric and canonical forms, so lookalikes and invisible characters do not hide it."""
    for candidate in (text, numeric_form(text), canonical(text)):
        for pattern, what in customer_spec._FORBIDDEN:
            if pattern.search(candidate):
                return what
    return money_in(text)


def leak_in(text: str) -> str | None:
    """Content never allowed in any customer text, even controlled or structured copy that may state a timeline or
    the word price: money, a rate or internal commercial wording, an email address or a phone number."""
    money, _words_, _duration, email, phone = customer_spec._FORBIDDEN
    for candidate in (text, numeric_form(text), canonical(text)):
        for pattern, what in (money, email, phone):
            if pattern.search(candidate):
                return what
    return money_in(text)


# --- field inventory ----------------------------------------------------------------------------------------------
FACTUAL, STATEMENT, STAFF, IDENTIFIER = "factual", "statement", "staff", "identifier"
# (model that declares the field, field) -> class. Inherited fields are keyed by the declaring base (Described).
FIELD_CLASSES: dict[tuple[str, str], str] = {
    # Described: every customer-facing record
    ("Described", "name"): FACTUAL, ("Described", "description"): FACTUAL,
    ("Described", "what_is_this"): FACTUAL, ("Described", "typically_used_for"): FACTUAL,
    ("Described", "staff_note"): STAFF, ("Described", "visibility"): IDENTIFIER,
    ("Availability", "markets"): IDENTIFIER, ("Availability", "property_types"): IDENTIFIER,
    ("Availability", "home_sizes"): IDENTIFIER, ("Availability", "project_kinds"): IDENTIFIER,
    ("PropertyType", "code"): IDENTIFIER,
    ("RoomSlot", "room_template"): IDENTIFIER,
    ("HomeConfig", "property_type"): IDENTIFIER, ("HomeConfig", "home_size"): IDENTIFIER,
    ("HomeConfig", "packages"): IDENTIFIER,
    ("ProductSlot", "product"): IDENTIFIER, ("ProductSlot", "variant"): IDENTIFIER, ("ProductSlot", "options"): IDENTIFIER,
    ("RoomTemplate", "room_code"): IDENTIFIER, ("RoomTemplate", "image"): IDENTIFIER,
    ("RoomTemplate", "gallery"): IDENTIFIER, ("RoomTemplate", "extras"): IDENTIFIER,
    ("ProductFamily", "category"): IDENTIFIER,
    ("MeasurementPrompt", "input"): IDENTIFIER, ("MeasurementPrompt", "label"): FACTUAL,
    ("MeasurementPrompt", "unit"): IDENTIFIER, ("MeasurementPrompt", "hint"): FACTUAL,
    ("Choice", "key"): IDENTIFIER, ("Choice", "engine_options"): IDENTIFIER, ("Choice", "materials"): IDENTIFIER,
    ("Choice", "hardware"): IDENTIFIER, ("Choice", "media"): IDENTIFIER,
    ("OptionGroup", "key"): IDENTIFIER, ("OptionGroup", "name"): FACTUAL, ("OptionGroup", "description"): FACTUAL,
    ("OptionGroup", "default"): IDENTIFIER,
    ("Variant", "key"): IDENTIFIER, ("Variant", "engine_product"): IDENTIFIER, ("Variant", "engine_options"): IDENTIFIER,
    ("Variant", "materials"): IDENTIFIER, ("Variant", "hardware"): IDENTIFIER, ("Variant", "media"): IDENTIFIER,
    ("Product", "family"): IDENTIFIER, ("Product", "default_variant"): IDENTIFIER, ("Product", "rooms"): IDENTIFIER,
    ("Product", "packages"): IDENTIFIER, ("Product", "media"): IDENTIFIER,
    ("AddSelection", "engine_product"): IDENTIFIER, ("AddSelection", "engine_options"): IDENTIFIER,
    ("SetOption", "product"): IDENTIFIER, ("SetOption", "group"): IDENTIFIER, ("SetOption", "choice"): IDENTIFIER,
    ("Extra", "kind"): IDENTIFIER, ("Extra", "quantity"): IDENTIFIER, ("Extra", "rooms"): IDENTIFIER,
    ("Extra", "products"): IDENTIFIER, ("Extra", "media"): IDENTIFIER, ("Extra", "materials"): IDENTIFIER,
    ("Extra", "hardware"): IDENTIFIER,
    ("Material", "category"): IDENTIFIER, ("Material", "grade"): STAFF, ("Material", "thickness"): STAFF,
    ("Material", "finish"): FACTUAL, ("Material", "colour_family"): FACTUAL, ("Material", "texture"): FACTUAL,
    ("Material", "brands"): STAFF, ("Material", "wet_area"): IDENTIFIER, ("Material", "rooms"): IDENTIFIER,
    ("Material", "products"): IDENTIFIER, ("Material", "statements"): IDENTIFIER, ("Material", "warranty_source"): STAFF,
    ("Hardware", "category"): IDENTIFIER, ("Hardware", "compatible_families"): STAFF, ("Hardware", "brands"): STAFF,
    ("Hardware", "statements"): IDENTIFIER, ("Hardware", "warranty_source"): STAFF,
    ("Rights", "owner"): FACTUAL,  # shown as the attribution when the media has none
    ("Rights", "licence"): STAFF, ("Rights", "usage"): STAFF, ("Rights", "consent_reference"): STAFF,
    ("Objects", "source"): STAFF, ("Objects", "variants"): IDENTIFIER,
    ("Hotspot", "key"): IDENTIFIER, ("Hotspot", "label"): FACTUAL,
    ("CameraPreset", "key"): IDENTIFIER, ("CameraPreset", "label"): FACTUAL, ("CameraPreset", "orbit"): FACTUAL,
    ("CameraPreset", "target"): FACTUAL,
    ("ThreeD", "model_version"): IDENTIFIER, ("ThreeD", "preview_image"): IDENTIFIER,
    ("ThreeD", "fallback_gallery"): IDENTIFIER, ("ThreeD", "supported_devices"): IDENTIFIER,
    ("ThreeD", "dimensions_mm"): IDENTIFIER, ("ThreeD", "materials"): IDENTIFIER, ("ThreeD", "variant_map"): FACTUAL,
    ("ThreeD", "finish_map"): FACTUAL,
    ("Media", "type"): IDENTIFIER, ("Media", "title"): FACTUAL, ("Media", "alt"): FACTUAL, ("Media", "caption"): FACTUAL,
    ("Media", "label"): IDENTIFIER, ("Media", "attribution"): FACTUAL, ("Media", "items"): IDENTIFIER,
    ("Media", "embed_url"): IDENTIFIER, ("Media", "tags"): IDENTIFIER, ("Media", "rooms"): IDENTIFIER,
    ("Media", "products"): IDENTIFIER, ("Media", "materials"): IDENTIFIER, ("Media", "packages"): IDENTIFIER,
    ("Package", "engine_package"): IDENTIFIER, ("Package", "public_summary"): IDENTIFIER,
    ("Package", "included_products"): IDENTIFIER, ("Package", "optional_products"): IDENTIFIER,
    ("Package", "included_extras"): IDENTIFIER, ("Package", "excluded_extras"): IDENTIFIER,
    ("Package", "material_promise"): IDENTIFIER, ("Package", "hardware_promise"): IDENTIFIER,
    ("Package", "warranty_copy"): IDENTIFIER, ("Package", "badge"): IDENTIFIER,
    ("Pricing", "scope"): STAFF, ("Pricing", "engine_product"): STAFF, ("Pricing", "body"): STAFF, ("Pricing", "note"): STAFF,
    ("Condition", "property_types"): IDENTIFIER, ("Condition", "home_sizes"): IDENTIFIER,
    ("Condition", "project_kinds"): IDENTIFIER, ("Condition", "packages"): IDENTIFIER, ("Condition", "markets"): IDENTIFIER,
    ("Rule", "type"): IDENTIFIER, ("Rule", "subject"): IDENTIFIER, ("Rule", "objects"): IDENTIFIER,
    ("Rule", "input"): IDENTIFIER, ("Rule", "message"): IDENTIFIER, ("Rule", "note"): STAFF,
    ("Governance", "owner"): STAFF, ("Governance", "backup"): STAFF, ("Governance", "quotation_mapping"): STAFF,
    ("Governance", "verification"): STAFF, ("Governance", "warranty_source"): STAFF, ("Governance", "status"): STAFF,
    ("AppliesTo", "products"): IDENTIFIER, ("AppliesTo", "rooms"): IDENTIFIER, ("AppliesTo", "packages"): IDENTIFIER,
    ("Copy", "content_policy"): IDENTIFIER, ("ClaimGovernance", "categories"): STAFF, ("ClaimGovernance", "status"): STAFF,
    ("ClaimGovernance", "source"): STAFF, ("ClaimGovernance", "evidence_reference"): STAFF,
    ("ClaimGovernance", "evidence_period"): STAFF, ("ClaimGovernance", "owner"): STAFF,
    ("ClaimGovernance", "backup_owner"): STAFF, ("ClaimGovernance", "approver"): STAFF,
    ("ClaimGovernance", "non_expiring_policy"): STAFF, ("ClaimGovernance", "environments"): STAFF,
    ("ClaimGovernance", "substantiation"): STAFF, ("ClaimGovernance", "canonical_sha256"): STAFF,
    ("Copy", "statement"): STATEMENT, ("Copy", "category"): IDENTIFIER, ("Copy", "matrix_row"): STAFF,
}  # fmt: skip
# Fields the remediation instruction names that the catalog does not have (and so cannot carry text).
NOT_IN_SCHEMA = ("product short name", "product subtitle", "recommendation label", "ribbon", "promotional label",
                 "customer confirmation message")  # fmt: skip


def _has_str(annotation: object) -> bool:
    origin = typing.get_origin(annotation)
    if annotation is str:
        return True
    if origin is typing.Literal:
        return any(isinstance(a, str) for a in typing.get_args(annotation))
    if origin in (typing.Annotated,):
        return _has_str(typing.get_args(annotation)[0])
    return (
        any(_has_str(a) for a in typing.get_args(annotation))
        if origin is not None or isinstance(annotation, types.UnionType)
        else False
    )


def _models(annotation: object) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for arg in typing.get_args(annotation):
        yield from _models(arg)


def declaring_class(cls: type[BaseModel], field: str) -> str:
    for klass in cls.__mro__:
        if field in klass.__dict__.get("__annotations__", {}):
            return klass.__name__
    return cls.__name__


def string_fields(roots: typing.Iterable[type[BaseModel]]) -> set[tuple[str, str]]:
    """Every (declaring model, field) holding text anywhere under the given models, found by type."""
    found: set[tuple[str, str]] = set()
    seen: set[type[BaseModel]] = set()
    pending = list(roots)
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        for name, info in cls.model_fields.items():
            if _has_str(info.annotation):
                found.add((declaring_class(cls, name), name))
            pending.extend(_models(info.annotation))
    return found


def field_class(model: BaseModel, field: str) -> str:
    key = (declaring_class(type(model), field), field)
    if key not in FIELD_CLASSES:
        raise KeyError(f"customer-text field {key} is not classified")  # fails closed; the inventory test catches it
    return FIELD_CLASSES[key]


def _strings(value: object) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield "", value
    elif isinstance(value, (tuple, list)):
        for i, v in enumerate(value):
            for sub, text in _strings(v):
                yield f"[{i}]{sub}", text
    elif isinstance(value, dict):
        for k, v in value.items():
            for sub, text in _strings(v):
                yield f".{k}{sub}", text


def visible_text(model: BaseModel, prefix: str = "") -> Iterator[tuple[str, str, str]]:
    """(path, text, class) for every factual or statement string a customer can read in this document, walking nested
    models; staff-only records, variants and choices are skipped (no customer sees them)."""
    if getattr(model, "visibility", "customer") == "staff":
        return
    for name in type(model).model_fields:
        value = getattr(model, name)
        if value is None:
            continue
        path = f"{prefix}{name}"
        nested = [v for v in (value if isinstance(value, (tuple, list)) else [value]) if isinstance(v, BaseModel)]
        if nested:
            for i, child in enumerate(nested):
                yield from visible_text(child, f"{path}[{i}]." if isinstance(value, (tuple, list)) else f"{path}.")
            continue
        if isinstance(value, dict) and any(isinstance(v, BaseModel) for v in value.values()):
            for k, child in value.items():
                if isinstance(child, BaseModel):
                    yield from visible_text(child, f"{path}.{k}.")
            continue
        if not _has_str(type(model).model_fields[name].annotation):
            continue
        cls = field_class(model, name)
        if cls in (FACTUAL, STATEMENT):
            for sub, text in _strings(value):
                yield f"{path}{sub}", text, cls
