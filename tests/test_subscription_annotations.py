import json
import logging
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml
from click.testing import CliRunner

from clin.clients.nakadi import (
    Nakadi,
    NakadiError,
    event_type_to_payload,
    subscription_from_payload,
)
from clin.clients.nakadi_sql import sql_query_to_payload
from clin.models.event_type import EventType
from clin.models.sql_query import SqlQuery
from clin.models.subscription import Subscription
from clin.run import cli
from clin.yamlops import YamlLoader, load_manifest


ANNOTATIONS = {
    "nakadi.zalando.org/subscription-max-event-send-count": "3",
    "nakadi.zalando.org/subscription-unprocessable-event-policy": "DEAD_LETTER_QUEUE",
}


@pytest.fixture
def manifest():
    return {
        "kind": "subscription",
        "spec": {
            "owningApplication": "stups_example-consumer",
            "eventTypes": ["example.input"],
            "consumerGroup": "main",
            "auth": {
                "teams": {"admins": ["example-team"], "readers": ["example-team"]}
            },
        },
    }


@pytest.fixture
def nakadi_payload():
    return {
        "id": "example-id",
        "owning_application": "stups_example-consumer",
        "event_types": ["example.input"],
        "consumer_group": "main",
        "read_from": "end",
        "initial_cursors": [],
        "authorization": {
            "admins": [{"data_type": "team", "value": "example-team"}],
            "readers": [{"data_type": "team", "value": "example-team"}],
        },
        "annotations": {},
    }


def response(status, body=None):
    return SimpleNamespace(status_code=status, json=lambda: body, text="")


@pytest.fixture
def broker(monkeypatch, nakadi_payload):
    state = SimpleNamespace(subscription=deepcopy(nakadi_payload), writes=[])

    def get(url, headers, params):
        return response(
            200, {"items": [deepcopy(state.subscription)] if state.subscription else []}
        )

    def post(url, headers, data):
        payload = json.loads(data)
        state.writes.append(("POST", url, payload))
        state.subscription = dict(nakadi_payload, **payload)
        return response(201, deepcopy(state.subscription))

    def put(url, headers, data):
        payload = json.loads(data)
        state.writes.append(("PUT", url, payload))
        state.subscription.update(payload)
        return response(204)

    monkeypatch.setattr("clin.clients.nakadi.requests.get", get)
    monkeypatch.setattr("clin.clients.nakadi.requests.post", post)
    monkeypatch.setattr("clin.clients.nakadi.requests.put", put)
    return state


def apply_cli(tmp_path, manifest, caplog, execute=False):
    path = tmp_path / "subscription.yaml"
    path.write_text(yaml.safe_dump(manifest))
    caplog.clear()
    caplog.set_level(logging.INFO)
    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        Path(".clin").write_text(
            "environments:\n  test:\n    nakadi_url: https://example.invalid\n"
        )
        result = CliRunner().invoke(
            cli,
            ["apply", "-e", "test", "-d", "-p"]
            + (["-X"] if execute else [])
            + [str(path)],
        )
    return result


def test_manifest_parses_auto_dlq_and_omitted_annotations(tmp_path, manifest):
    path = tmp_path / "subscription.yaml"
    manifest["spec"]["annotations"] = ANNOTATIONS
    path.write_text(yaml.safe_dump(manifest))
    envelope = load_manifest(path, YamlLoader(), {})
    assert Subscription.from_spec(envelope.spec).annotations == ANNOTATIONS
    del envelope.spec["annotations"]
    assert Subscription.from_spec(envelope.spec).annotations is None


@pytest.mark.parametrize(
    "annotations",
    [
        None,
        [],
        "value",
        {"key": 3},
        {1: "value"},
        {"key": True},
        {"key": []},
        {"key": {}},
    ],
)
def test_invalid_manifest_annotations_fail_before_requests(
    manifest, annotations, broker, tmp_path, caplog
):
    manifest["spec"]["annotations"] = annotations
    result = apply_cli(tmp_path, manifest, caplog, execute=True)
    assert result.exit_code != 0
    assert (
        "annotations must be a map of string keys and string or null values"
        in caplog.text
    )
    assert broker.writes == []


@pytest.mark.parametrize(
    "annotations", [ANNOTATIONS, {"nullable": None, "text": "null"}]
)
def test_create_payload_includes_annotations_and_omits_unmanaged(
    manifest, broker, tmp_path, caplog, annotations
):
    broker.subscription = None
    manifest["spec"]["annotations"] = annotations
    assert apply_cli(tmp_path, manifest, caplog).exit_code == 0
    payload_output = next(
        record.getMessage()
        for record in caplog.records
        if "Nakadi payload" in record.getMessage()
    )
    shown_payload = json.loads(payload_output.split("\n", 1)[1])
    assert shown_payload["annotations"] == annotations
    assert broker.writes == []
    assert apply_cli(tmp_path, manifest, caplog, execute=True).exit_code == 0
    assert broker.writes[-1][0] == "POST"
    assert broker.writes[-1][2] == shown_payload
    assert broker.subscription["annotations"] == annotations
    assert apply_cli(tmp_path, manifest, caplog, execute=True).exit_code == 0
    assert "Up to date" in caplog.text
    assert len(broker.writes) == 1
    broker.subscription = None
    del manifest["spec"]["annotations"]
    assert apply_cli(tmp_path, manifest, caplog, execute=True).exit_code == 0
    assert "annotations" not in broker.writes[-1][2]


@pytest.mark.parametrize(
    "current,desired",
    [
        ({}, {"added": "yes"}),
        ({"key": "old"}, {"key": "new"}),
        ({"keep": "yes", "removed": "old"}, {"keep": "yes"}),
        ({"key": "old"}, {}),
        ({}, {"key": None}),
        ({"key": "old"}, {"key": None}),
        ({"key": None}, {"key": "new"}),
        ({"key": None}, {}),
    ],
)
def test_annotation_changes_dry_run_update_and_converge(
    manifest, broker, tmp_path, caplog, current, desired
):
    broker.subscription["annotations"] = current
    manifest["spec"]["annotations"] = desired
    assert apply_cli(tmp_path, manifest, caplog).exit_code == 0
    output = caplog.text
    assert (
        "Will update" in output
        and "annotations" in output
        and "Nakadi payload" in output
    )
    diff_output = next(
        record.getMessage()
        for record in caplog.records
        if "Found" in record.getMessage()
    )
    payload_output = next(
        record.getMessage()
        for record in caplog.records
        if "Nakadi payload" in record.getMessage()
    )
    shown_payload = json.loads(payload_output.split("\n", 1)[1])
    assert shown_payload["annotations"] == desired
    missing = object()
    for key in set(current) | set(desired):
        if current.get(key, missing) != desired.get(key, missing):
            assert key in diff_output
    shown_diff = yaml.safe_load(diff_output.split("\n", 1)[1])
    if "type_changes" in shown_diff:
        change = shown_diff["type_changes"]["root.annotations['key']"]
        assert change["old_value"] == current["key"]
        assert change["new_value"] == desired["key"]
    assert broker.writes == []
    assert apply_cli(tmp_path, manifest, caplog, execute=True).exit_code == 0
    assert broker.writes[-1][0] == "PUT"
    assert broker.writes[-1][2]["annotations"] == desired
    assert broker.writes[-1][2] == shown_payload
    assert apply_cli(tmp_path, manifest, caplog).exit_code == 0
    assert "Up to date" in caplog.text
    assert len(broker.writes) == 1


@pytest.mark.parametrize("external_value", ["keep", None])
def test_omission_preserves_annotations_and_immutable_cursors(
    manifest, broker, tmp_path, caplog, external_value
):
    broker.subscription["annotations"] = {"external": external_value}
    broker.subscription["read_from"] = "cursors"
    broker.subscription["initial_cursors"] = [
        {"event_type": "example.input", "partition": "0", "offset": "001"}
    ]
    original_cursors = deepcopy(broker.subscription["initial_cursors"])
    assert apply_cli(tmp_path, manifest, caplog).exit_code == 0
    assert "Up to date" in caplog.text and "annotations" not in caplog.text
    manifest["spec"]["auth"]["teams"]["readers"].append("another-team")
    assert apply_cli(tmp_path, manifest, caplog, execute=True).exit_code == 0
    sent = broker.writes[-1][2]
    assert "annotations" not in sent
    assert sent["read_from"] == "cursors"
    assert sent["initial_cursors"] == original_cursors
    assert broker.subscription["initial_cursors"] == original_cursors
    assert broker.subscription["annotations"] == {"external": external_value}


def test_managed_update_retains_non_default_cursors(manifest, broker, tmp_path, caplog):
    broker.subscription["read_from"] = "begin"
    manifest["spec"]["annotations"] = {"key": "value"}
    assert apply_cli(tmp_path, manifest, caplog, execute=True).exit_code == 0
    assert broker.writes[-1][2]["read_from"] == "begin"


def test_missing_and_null_response_annotations_converge(
    manifest, broker, tmp_path, caplog
):
    manifest["spec"]["annotations"] = {}
    broker.subscription["annotations"] = None
    assert apply_cli(tmp_path, manifest, caplog).exit_code == 0
    assert "Up to date" in caplog.text
    del broker.subscription["annotations"]
    assert apply_cli(tmp_path, manifest, caplog).exit_code == 0
    assert "Up to date" in caplog.text


def test_malformed_response_annotations_rejected(nakadi_payload):
    nakadi_payload["annotations"] = {"wrong": 4}
    with pytest.raises(ValueError, match="annotations must be a map"):
        subscription_from_payload(nakadi_payload)


@pytest.mark.parametrize("match_page", [1, 2])
@pytest.mark.parametrize("later_page", ["duplicate", "error"])
def test_lookup_stops_at_first_match(
    monkeypatch, nakadi_payload, match_page, later_page
):
    pages = []
    if match_page == 2:
        pages.append(
            response(
                200,
                {
                    "items": [dict(nakadi_payload, consumer_group="other")],
                    "_links": {"next": {"href": "/subscriptions?offset=1&limit=1"}},
                },
            )
        )
    pages.append(
        response(
            200,
            {
                "items": [nakadi_payload],
                "_links": {
                    "next": {"href": f"/subscriptions?offset={match_page}&limit=1"}
                },
            },
        )
    )
    pages.append(
        response(200, {"items": [nakadi_payload]})
        if later_page == "duplicate"
        else response(429)
    )
    get = Mock(side_effect=pages)
    monkeypatch.setattr("clin.clients.nakadi.requests.get", get)
    sub = Nakadi("https://example.invalid", None).get_subscription(
        ["example.input"], "stups_example-consumer", "main"
    )
    assert sub.id == "example-id"
    assert get.call_count == match_page


@pytest.mark.parametrize("pagination", [{"offset": "3"}, {"token": "Wnext-page"}])
def test_lookup_pages_and_matches_full_identity(
    monkeypatch, nakadi_payload, pagination
):
    event_types = ["example.input", "example.other"]
    match = dict(nakadi_payload, event_types=list(reversed(event_types)))
    other_subscriptions = [
        dict(match, id="expanded", event_types=event_types + ["extra"]),
        dict(match, id="other-app", owning_application="other-app"),
        dict(match, id="other-group", consumer_group="other-group"),
    ]
    pagination_query = "&".join(f"{key}={value}" for key, value in pagination.items())
    next_link = (
        "https://example.invalid/subscriptions?event_type=example.other"
        "&event_type=example.input&owning_application=stups_example-consumer"
        f"&limit=3&{pagination_query}"
    )
    get = Mock(
        side_effect=[
            response(
                200,
                {"items": other_subscriptions, "_links": {"next": {"href": next_link}}},
            ),
            response(200, {"items": [match]}),
        ]
    )
    monkeypatch.setattr("clin.clients.nakadi.requests.get", get)
    sub = Nakadi("https://example.invalid", None).get_subscription(
        event_types, "stups_example-consumer", "main"
    )
    assert sub.id == "example-id"
    assert get.call_count == 2
    assert get.call_args[0] == ("https://example.invalid/subscriptions",)
    assert get.call_args[1]["params"] == {
        "event_type": "example.input,example.other",
        "owning_application": "stups_example-consumer",
        "limit": "3",
        **pagination,
    }


def test_lookup_returns_none_after_exhausting_pages(monkeypatch, nakadi_payload):
    get = Mock(
        side_effect=[
            response(
                200,
                {
                    "items": [dict(nakadi_payload, consumer_group="other")],
                    "_links": {"next": {"href": "/subscriptions?offset=1&limit=1"}},
                },
            ),
            response(200, {"items": []}),
        ]
    )
    monkeypatch.setattr("clin.clients.nakadi.requests.get", get)
    assert (
        Nakadi("https://example.invalid", None).get_subscription(
            ["example.input"], "stups_example-consumer", "main"
        )
        is None
    )
    assert get.call_count == 2


def test_expanded_event_type_set_creates_a_different_subscription(
    manifest, broker, tmp_path, caplog
):
    broker.subscription["event_types"].append("extra")
    manifest["spec"]["annotations"] = ANNOTATIONS
    assert apply_cli(tmp_path, manifest, caplog, execute=True).exit_code == 0
    assert len(broker.writes) == 1
    method, url, payload = broker.writes[0]
    assert method == "POST"
    assert url == "https://example.invalid/subscriptions"
    assert payload["event_types"] == ["example.input"]
    assert payload["annotations"] == ANNOTATIONS


@pytest.mark.parametrize("query", ["offset=20", "token=Wnext-page", "limit=20"])
def test_lookup_rejects_invalid_pagination(monkeypatch, query):
    monkeypatch.setattr(
        "clin.clients.nakadi.requests.get",
        lambda *args, **kwargs: response(
            200, {"items": [], "_links": {"next": {"href": f"/subscriptions?{query}"}}}
        ),
    )
    client = Nakadi("https://example.invalid", None)
    with pytest.raises(NakadiError, match="Invalid subscription pagination"):
        client.get_subscription(["example.input"], "app", "main")


@pytest.mark.parametrize("failure_page", [1, 2])
def test_lookup_reports_http_failure_before_match(monkeypatch, failure_page):
    pages = []
    if failure_page == 2:
        pages.append(
            response(
                200,
                {
                    "items": [],
                    "_links": {"next": {"href": "/subscriptions?token=Wnext-page"}},
                },
            )
        )
    get = Mock(side_effect=pages + [response(503)])
    monkeypatch.setattr("clin.clients.nakadi.requests.get", get)
    with pytest.raises(NakadiError, match="503"):
        Nakadi("https://example.invalid", None).get_subscription(
            ["example.input"], "app", "main"
        )
    assert get.call_count == failure_page


def test_update_failure_is_reported(manifest, broker, monkeypatch, tmp_path, caplog):
    manifest["spec"]["annotations"] = {"key": "value"}
    monkeypatch.setattr(
        "clin.clients.nakadi.requests.put", lambda *args, **kwargs: response(403)
    )
    result = apply_cli(tmp_path, manifest, caplog, execute=True)
    assert result.exit_code != 0
    assert "403" in caplog.text


def test_existing_event_type_and_sql_annotation_payloads():
    examples = Path(__file__).resolve().parents[1] / "docs" / "examples" / "single"
    loader = YamlLoader()
    event_spec = load_manifest(
        examples / "event-type.yaml", loader, {"USER": "example"}
    ).spec
    sql_spec = load_manifest(
        examples / "sql-query.yaml", loader, {"USER": "example"}
    ).spec
    assert event_type_to_payload(EventType.from_spec(event_spec))["annotations"] == {
        "foo": "bar"
    }
    sql_payload = sql_query_to_payload(SqlQuery.from_spec(sql_spec))
    assert sql_payload["output_event_type"]["annotations"] == {"foo": "bar"}
    del sql_spec["outputEventType"]["annotations"]
    assert (
        "annotations"
        not in sql_query_to_payload(SqlQuery.from_spec(sql_spec))["output_event_type"]
    )
