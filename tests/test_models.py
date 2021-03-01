import pytest
import yaml

from clin.models.auth import Auth
from clin.models.shared import Kind, Envelope


def test_loads_auth_as_flat_lists_without_duplicates():
    yml = """
    auth:
      users:
        admins:         # single item
          - hammond
        writers:        # nested list
          - - carter
            - jackson
          - - o'neill
            - teal'c
        readers:        # flat list
          - quinn
          - mitchell
          - mal doran
      services:
        admins:         # flat list with duplicates
          - one
          - two
          - one
          - two
          - one
        writers:        # mixed list with duplicates
          - one
          - two
          - three
          - - four
            - three  # duplicate
            - five
          - - three  # duplicate
            - six
        readers:        # empty list
      anyToken:
        read: true
        write: true
    """

    spec = yaml.safe_load(yml)
    auth = Auth.from_spec(spec["auth"])

    assert auth.users.admins == ["hammond"]
    assert set(auth.users.writers) == {"o'neill", "carter", "jackson", "teal'c"}
    assert set(auth.users.readers) == {"quinn", "mitchell", "mal doran"}

    assert len(auth.services.admins) == 2
    assert set(auth.services.admins) == {"one", "two"}
    assert len(auth.services.writers) == 6
    assert set(auth.services.writers) == {"one", "two", "three", "four", "five", "six"}
    assert auth.services.readers == []

    assert auth.any_token_write is True
    assert auth.any_token_read is True


@pytest.mark.parametrize("kind_spec,expected_kind", [
    ("event-type", Kind.EVENT_TYPE),
    ("sql-query", Kind.SQL_QUERY),
    ("subscription", Kind.SUBSCRIPTION),
])
def test_parses_envelope_from_valid_manifest(kind_spec: str, expected_kind: Kind):
    manifest = {
        "kind": kind_spec,
        "spec": {},
    }

    envelope = Envelope.from_manifest(manifest)
    assert envelope.kind == expected_kind
    assert envelope.spec == {}
