import re
import unicodedata

# C0/C1 control characters, and bidi overrides that can disguise an extension
# ("invoice‮fdp.exe" displays as "invoiceexe.pdf").
_UNSAFE = re.compile(r"[\x00-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩﻿]")


def safe_filename(name: str | None, fallback: str, limit: int = 200) -> str:
    """A client-supplied filename, fit for display: last path segment only (either slash
    style), no control or direction-override characters, collapsed whitespace, bounded length.

    Only ever used as a label. Storage keys are generated server-side, never from this.
    """
    name = unicodedata.normalize("NFC", name or "")
    name = re.split(r"[\\/]", name)[-1]
    name = " ".join(_UNSAFE.sub("", name).split()).strip(" .")
    return name[:limit] or fallback
