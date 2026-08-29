"""Validation engine — hard-constraint checks. Owner: sush.

budget <= limit, times don't overlap, check-in after arrival (readme.md section 9).
Failures feed back into negotiation, not a dead end.
"""


def validate(state) -> list[str]:
    errors: list[str] = []
    # TODO(sush): append a message for each violated hard constraint
    return errors
