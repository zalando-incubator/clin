import pytest
import yaml

from clin.models.auth import ReadWriteAuth, ReadOnlyAuth
from clin.models.shared import Kind, Envelope


yml = """
auth:
  teams:
    admins:
      - your_team
    readers:
      - sibling_team
      - - other_team_1
        - other_team_2
    writers:
      - your_upstream_team_1
      - your_upstream_team_2
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


def test_loads_full_auth_as_flat_lists_without_duplicates():
    spec = yaml.safe_load(yml)
    auth = ReadWriteAuth.from_spec(spec["auth"])

    assert auth.teams["admins"] == ["your_team"]
    assert set(auth.teams["writers"]) == {"your_upstream_team_1", "your_upstream_team_2"}
    assert set(auth.teams["readers"]) == {"sibling_team", "other_team_1", "other_team_2"}

    assert auth.users["admins"] == ["hammond"]
    assert set(auth.users["writers"]) == {"o'neill", "carter", "jackson", "teal'c"}
    assert set(auth.users["readers"]) == {"quinn", "mitchell", "mal doran"}

    assert len(auth.services["admins"]) == 2
    assert set(auth.services["admins"]) == {"one", "two"}
    assert len(auth.services["writers"]) == 6
    assert set(auth.services["writers"]) == {"one", "two", "three", "four", "five", "six"}
    assert auth.services["readers"] == []

    assert auth.any_token["write"] is True
    assert auth.any_token["read"] is True


def test_loads_readonly_auth_as_flat_lists_without_duplicates():
    spec = yaml.safe_load(yml)
    auth = ReadOnlyAuth.from_spec(spec["auth"])

    assert auth.teams["admins"] == ["your_team"]
    assert set(auth.teams["readers"]) == {"sibling_team", "other_team_1", "other_team_2"}

    assert auth.users["admins"] == ["hammond"]
    assert set(auth.users["readers"]) == {"quinn", "mitchell", "mal doran"}

    assert len(auth.services["admins"]) == 2
    assert set(auth.services["admins"]) == {"one", "two"}
    assert auth.services["readers"] == []

    assert auth.any_token["read"] is True

    assert "writers" not in auth.users
    assert "writers" not in auth.services
    assert "write" not in auth.any_token


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
