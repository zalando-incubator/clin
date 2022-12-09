from pathlib import Path
from unittest.mock import patch, MagicMock

from clin.clinfile import calculate_scope, Process
from clin.models.shared import Kind, Envelope
from clin.yamlops import YamlLoader

CLINFILE = {
    "process": [
        {
            "id": "Staging",
            "target": "staging",
            "paths": ["./apply_staging"],
            "env": {"POSTFIX": ""}
        },
        {
            "id": "Live",
            "target": "live",
            "paths": ["./apply_live"],
            "env": {"POSTFIX": ""}
        }
    ]
}

MANIFESTS = {
        "/path/to/clinfile/apply_staging/2_subquery.yaml":
        """
            kind: sql-query
            spec:
              name: clin.test_subquery
              sql: "SELECT * from clin.test_query;"
              auth:
                teams:
                  admins: 
                    - my_team
                anyToken:
                  read: false
        """,
        "/path/to/clinfile/apply_staging/1_query.yaml":
        """
            kind: sql-query
            spec:
                name: clin.test_query
                sql: "SELECT 1"
                auth:
                    teams:
                        admins:
                        - my_team
                    anyToken:
                        read: false
        """,
        "/path/to/clinfile/apply_live/1_query.yml":
        """
            kind: sql-query
            spec:
                name: clin.test_query2
                sql: "SELECT 2"
                auth:
                    teams:
                        admins:
                        - my_team
                    anyToken:
                        read: false
        """,
        "/path/to/clinfile/apply_live/README.txt": "README file"
}


@patch.object(Path, "read_text", autospec=True)
@patch.object(Path, "is_file", autospec=True)
@patch.object(Path, "exists", autospec=True)
@patch.object(Path, "glob", autospec=True)
def test_load_manifest_files(m_glob: MagicMock, m_path_exists: MagicMock, m_isfile: MagicMock, m_readtext: MagicMock):
    m_readtext.side_effect = lambda path: MANIFESTS[str(path)]
    m_isfile.side_effect = lambda path: str(path) in MANIFESTS
    m_path_exists.return_value = True
    m_glob.side_effect = lambda path, glob: [
        Path(key)
        for key in MANIFESTS.keys()
        if Path(key).parent == path and Path(key).suffix == Path(glob).suffix
    ]

    scope = calculate_scope(
        master=CLINFILE,
        base_path=Path("/path/to/clinfile/"),
        loader=YamlLoader(),
        filter_id=(),
        filter_env=()
    )

    assert not scope[Kind.SUBSCRIPTION]
    assert not scope[Kind.EVENT_TYPE]
    assert scope[Kind.SQL_QUERY] == [
        Process(
            id='Staging',
            path='/path/to/clinfile/apply_staging/1_query.yaml',
            envelope=Envelope(
                kind=Kind.SQL_QUERY,
                spec={
                    'name': 'clin.test_query',
                    'sql': 'SELECT 1',
                    'auth': {'teams': {'admins': ['my_team']}, 'anyToken': {'read': False}}}
            ),
            target='staging'
        ),
        Process(
            id='Staging',
            path='/path/to/clinfile/apply_staging/2_subquery.yaml',
            envelope=Envelope(
                kind=Kind.SQL_QUERY,
                spec={
                    'name': 'clin.test_subquery',
                    'sql': 'SELECT * from clin.test_query;',
                    'auth': {'teams': {'admins': ['my_team']}, 'anyToken': {'read': False}}}
            ),
            target='staging'
        ),
        Process(
            id='Live',
            path='/path/to/clinfile/apply_live/1_query.yml',
            envelope=Envelope(
                kind=Kind.SQL_QUERY,
                spec={
                    'name': 'clin.test_query2',
                    'sql': 'SELECT 2',
                    'auth': {'teams': {'admins': ['my_team']}, 'anyToken': {'read': False}}}
            ),
            target='live'
        ),
    ]

@patch.object(Path, "read_text", autospec=True)
@patch.object(Path, "is_file", autospec=True)
@patch.object(Path, "exists", autospec=True)
@patch.object(Path, "glob", autospec=True)
def test_filter_id(m_glob: MagicMock, m_path_exists: MagicMock, m_isfile: MagicMock, m_readtext: MagicMock):
    m_readtext.side_effect = lambda path: MANIFESTS[str(path)]
    m_isfile.side_effect = lambda path: str(path) in MANIFESTS
    m_path_exists.return_value = True
    m_glob.side_effect = lambda path, glob: [
        Path(key)
        for key in MANIFESTS.keys()
        if Path(key).parent == path and Path(key).suffix == Path(glob).suffix
    ]

    scope = calculate_scope(
        master=CLINFILE,
        base_path=Path("/path/to/clinfile/"),
        loader=YamlLoader(),
        filter_id=("Live",),
        filter_env=()
    )

    assert not scope[Kind.SUBSCRIPTION]
    assert not scope[Kind.EVENT_TYPE]
    assert scope[Kind.SQL_QUERY] == [
        Process(
            id='Live',
            path='/path/to/clinfile/apply_live/1_query.yml',
            envelope=Envelope(
                kind=Kind.SQL_QUERY,
                spec={
                    'name': 'clin.test_query2',
                    'sql': 'SELECT 2',
                    'auth': {'teams': {'admins': ['my_team']}, 'anyToken': {'read': False}}}
            ),
            target='live'
        )
    ]

@patch.object(Path, "read_text", autospec=True)
@patch.object(Path, "is_file", autospec=True)
@patch.object(Path, "exists", autospec=True)
@patch.object(Path, "glob", autospec=True)
def test_filter_env(m_glob: MagicMock, m_path_exists: MagicMock, m_isfile: MagicMock, m_readtext: MagicMock):
    m_readtext.side_effect = lambda path: MANIFESTS[str(path)]
    m_isfile.side_effect = lambda path: str(path) in MANIFESTS
    m_path_exists.return_value = True
    m_glob.side_effect = lambda path, glob: [
        Path(key)
        for key in MANIFESTS.keys()
        if Path(key).parent == path and Path(key).suffix == Path(glob).suffix
    ]

    scope = calculate_scope(
        master=CLINFILE,
        base_path=Path("/path/to/clinfile/"),
        loader=YamlLoader(),
        filter_id=(),
        filter_env=("live",)
    )

    assert not scope[Kind.SUBSCRIPTION]
    assert not scope[Kind.EVENT_TYPE]
    assert scope[Kind.SQL_QUERY] == [
        Process(
            id='Live',
            path='/path/to/clinfile/apply_live/1_query.yml',
            envelope=Envelope(
                kind=Kind.SQL_QUERY,
                spec={
                    'name': 'clin.test_query2',
                    'sql': 'SELECT 2',
                    'auth': {'teams': {'admins': ['my_team']}, 'anyToken': {'read': False}}}
            ),
            target='live'
        )
    ]
