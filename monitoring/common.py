import attr


@attr.s
class HTTPCheckResult:
    """
    Stores the results of a HTTP check.
    """
    status_code = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(int)),
        default=None,
    )
    content_length = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(int)),
        default=None,
    )
    content_type = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )
    duration = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(float)),
        default=None,
    )
    last_modified = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )
    timeout = attr.ib(validator=attr.validators.instance_of(bool), default=False)
    connection_error = attr.ib(
        validator=attr.validators.instance_of(bool), default=False
    )
