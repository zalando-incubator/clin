import yaml

from clin.models.auth import Auth


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
