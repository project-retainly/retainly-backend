from typing import Any, Dict

from pydantic import AfterValidator, WrapValidator
from typing_extensions import Annotated

from app.core.validations.validation_logic import (
    length,
    not_empty,
    reject_null,
)
from app.posts.utils import PostStatus

# ---------- TITLE ----------

TitleRequired = Annotated[
    str,
    AfterValidator(not_empty("Title")),
    AfterValidator(length("Title", 3, 200)),
]

TitleOptional = Annotated[
    str | None,
    WrapValidator(reject_null("Title")),
    AfterValidator(not_empty("Title")),
    AfterValidator(length("Title", 3, 200)),
]


SummaryOptionalAllowNull = Annotated[
    str | None,
    AfterValidator(not_empty("Summary")),
    AfterValidator(length("Summary", 3, 500)),
]


FeaturedImageOptionalAllowNull = Annotated[
    str | None,
    AfterValidator(not_empty("Featured image")),
    AfterValidator(length("Featured image", 3, 500)),
]


ContentOptionalAllowNull = Annotated[
    Dict[str, Any] | None,
    AfterValidator(not_empty("Content")),
]

StatusRequired = Annotated[
    PostStatus,
    WrapValidator(reject_null("Status")),
]

StatusOptional = Annotated[
    PostStatus | None,
    WrapValidator(reject_null("Status")),
]
