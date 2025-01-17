# -*- coding: utf-8 -*-

import json
import os
from unittest import mock
from zipfile import BadZipFile

import pytest
import requests
import responses
from taskcluster.exceptions import TaskclusterRestFailure

from code_coverage_bot import taskcluster
from conftest import FIXTURES_DIR


def test_get_task_status(mock_taskcluster, LINUX_TASK_ID, LINUX_TASK_STATUS):
    responses.add(
        responses.GET,
        f"http://taskcluster.test/api/queue/v1/task/{LINUX_TASK_ID}/status",
        json=LINUX_TASK_STATUS,
        status=200,
    )
    assert taskcluster.get_task_status(LINUX_TASK_ID) == LINUX_TASK_STATUS


def test_get_task_details(mock_taskcluster, LINUX_TASK_ID, LINUX_TASK):
    responses.add(
        responses.GET,
        f"http://taskcluster.test/api/queue/v1/task/{LINUX_TASK_ID}",
        json=LINUX_TASK,
        status=200,
    )
    assert taskcluster.get_task_details(LINUX_TASK_ID) == LINUX_TASK


def test_get_task(
    mock_taskcluster, LINUX_TASK_ID, LATEST_LINUX, WIN_TASK_ID, LATEST_WIN
):
    responses.add(
        responses.GET,
        "http://taskcluster.test/api/index/v1/task/gecko.v2.mozilla-central.revision.b2a9a4bb5c94de179ae7a3f52fde58c0e2897498.firefox.linux64-ccov-debug",
        json=LATEST_LINUX,
        status=200,
    )  # noqa
    assert (
        taskcluster.get_task(
            "mozilla-central", "b2a9a4bb5c94de179ae7a3f52fde58c0e2897498", "linux"
        )
        == LINUX_TASK_ID
    )

    responses.add(
        responses.GET,
        "http://taskcluster.test/api/index/v1/task/gecko.v2.mozilla-central.revision.916103b8675d9fdb28b891cac235d74f9f475942.firefox.win64-ccov-debug",
        json=LATEST_WIN,
        status=200,
    )  # noqa
    assert (
        taskcluster.get_task(
            "mozilla-central", "916103b8675d9fdb28b891cac235d74f9f475942", "windows"
        )
        == WIN_TASK_ID
    )


def test_get_task_not_found(mock_taskcluster, TASK_NOT_FOUND):
    responses.add(
        responses.GET,
        "http://taskcluster.test/api/index/v1/task/gecko.v2.mozilla-central.revision.b2a9a4bb5c94de179ae7a3f52fde58c0e2897498.firefox.linux64-ccov-debug",
        json=TASK_NOT_FOUND,
        status=404,
    )  # noqa

    assert (
        taskcluster.get_task(
            "mozilla-central", "b2a9a4bb5c94de179ae7a3f52fde58c0e2897498", "linux"
        )
        is None
    )


def test_get_task_failure(mock_taskcluster, TASK_NOT_FOUND):
    err = TASK_NOT_FOUND.copy()
    err["code"] = "RandomError"
    responses.add(
        responses.GET,
        "http://taskcluster.test/api/index/v1/task/gecko.v2.mozilla-central.revision.b2a9a4bb5c94de179ae7a3f52fde58c0e2897498.firefox.linux64-ccov-debug",
        json=err,
        status=500,
    )  # noqa

    with pytest.raises(TaskclusterRestFailure, match="Indexed task not found"):
        taskcluster.get_task(
            "mozilla-central", "b2a9a4bb5c94de179ae7a3f52fde58c0e2897498", "linux"
        )


def test_get_task_artifacts(mock_taskcluster, LINUX_TASK_ID, LINUX_TASK_ARTIFACTS):
    responses.add(
        responses.GET,
        f"http://taskcluster.test/api/queue/v1/task/{LINUX_TASK_ID}/artifacts",
        json=LINUX_TASK_ARTIFACTS,
        status=200,
    )
    assert (
        taskcluster.get_task_artifacts(LINUX_TASK_ID)
        == LINUX_TASK_ARTIFACTS["artifacts"]
    )


def test_get_tasks_in_group(mock_taskcluster, GROUP_TASKS_1, GROUP_TASKS_2):
    responses.add(
        responses.GET,
        "http://taskcluster.test/api/queue/v1/task-group/aPt9FbIdQwmhwDIPDYLuaw/list?limit=200",
        json=GROUP_TASKS_1,
        status=200,
        match_querystring=True,
    )  # noqa
    responses.add(
        responses.GET,
        "http://taskcluster.test/api/queue/v1/task-group/aPt9FbIdQwmhwDIPDYLuaw/list?continuationToken=1%2132%21YVB0OUZiSWRRd21od0RJUERZTHVhdw--~1%2132%21ZnJVcGRRT0VTalN0Nm9Ua1Ztcy04UQ--&limit=200",  # noqa
        json=GROUP_TASKS_2,
        status=200,
        match_querystring=True,
    )  # noqa

    assert (
        list(taskcluster.get_tasks_in_group("aPt9FbIdQwmhwDIPDYLuaw"))
        == GROUP_TASKS_1["tasks"] + GROUP_TASKS_2["tasks"]
    )


@pytest.mark.parametrize(
    "task_name, expected",
    [
        ("test-linux64-ccov/debug-mochitest-1", True),
        ("test-linux64-ccov/debug-mochitest-e10s-7", True),
        ("test-linux64-ccov/debug-cppunit", True),
        ("test-linux64-ccov/debug-firefox-ui-functional-remote-e10s", True),
        ("test-windows10-64-ccov/debug-mochitest-1", True),
        ("test-windows10-64-ccov/debug-mochitest-e10s-7", True),
        ("test-windows10-64-ccov/debug-cppunit", True),
        ("build-linux64-ccov/debug", True),
        ("build-android-test-ccov/opt", True),
        ("build-win64-ccov/debug", True),
        ("test-linux64/debug-mochitest-1", False),
        ("test-windows10-64/debug-cppunit", False),
        ("build-win64/debug", False),
    ],
)
def test_is_coverage_task(task_name, expected):
    task = json.load(open(os.path.join(FIXTURES_DIR, f"{task_name}.json")))
    assert taskcluster.is_coverage_task(task) is expected


@pytest.mark.parametrize(
    "task_name, expected",
    [
        ("test-linux64-ccov/debug-mochitest-1", "mochitest-1"),
        ("test-linux64-ccov/debug-mochitest-e10s-7", "mochitest-7"),
        ("test-linux64-ccov/debug-cppunit", "cppunit"),
        (
            "test-linux64-ccov/debug-firefox-ui-functional-remote-e10s",
            "firefox-ui-functional-remote",
        ),
        ("test-windows10-64-ccov/debug-mochitest-1", "mochitest-1"),
        ("test-windows10-64-ccov/debug-mochitest-e10s-7", "mochitest-7"),
        ("test-windows10-64-ccov/debug-cppunit", "cppunit"),
        ("build-linux64-ccov/debug", "build"),
        ("build-android-test-ccov/opt", "build"),
        ("build-win64-ccov/debug", "build"),
    ],
)
def test_name_to_chunk(task_name, expected):
    assert taskcluster.name_to_chunk(task_name) == expected


@pytest.mark.parametrize(
    "chunk, expected",
    [
        ("mochitest-1", "mochitest"),
        ("mochitest-7", "mochitest"),
        ("cppunit", "cppunit"),
        ("firefox-ui-functional-remote", "firefox-ui-functional-remote"),
        ("build", "build"),
    ],
)
def test_chunk_to_suite(chunk, expected):
    assert taskcluster.chunk_to_suite(chunk) == expected


@pytest.mark.parametrize(
    "task_name, expected",
    [
        ("test-linux64-ccov/debug-mochitest-1", "mochitest-1"),
        ("test-linux64-ccov/debug-mochitest-e10s-7", "mochitest-plain-chunked-7"),
        ("test-linux64-ccov/debug-cppunit", "cppunittest-1"),
        (
            "test-linux64-ccov/debug-firefox-ui-functional-remote-e10s",
            "firefox-ui-functional-remote-1",
        ),
        ("test-windows10-64-ccov/debug-mochitest-1", "mochitest-1"),
        ("test-windows10-64-ccov/debug-mochitest-e10s-7", "mochitest-plain-chunked-7"),
        ("test-windows10-64-ccov/debug-cppunit", "cppunittest-1"),
        ("build-linux64-ccov/debug", "build"),
        ("build-android-test-ccov/opt", "build"),
        ("build-win64-ccov/debug", "build"),
    ],
)
def test_get_chunk(task_name, expected):
    task = json.load(open(os.path.join(FIXTURES_DIR, f"{task_name}.json")))
    assert taskcluster.get_chunk(task) == expected


@pytest.mark.parametrize(
    "task_name, expected",
    [
        ("test-linux64-ccov/debug-mochitest-1", "mochitest"),
        ("test-linux64-ccov/debug-mochitest-e10s-7", "mochitest-plain-chunked"),
        ("test-linux64-ccov/debug-cppunit", "cppunittest"),
        (
            "test-linux64-ccov/debug-firefox-ui-functional-remote-e10s",
            "firefox-ui-functional-remote",
        ),
        ("test-windows10-64-ccov/debug-mochitest-1", "mochitest"),
        ("test-windows10-64-ccov/debug-mochitest-e10s-7", "mochitest-plain-chunked"),
        ("test-windows10-64-ccov/debug-cppunit", "cppunittest"),
        ("build-linux64-ccov/debug", "build"),
        ("build-android-test-ccov/opt", "build"),
        ("build-win64-ccov/debug", "build"),
    ],
)
def test_get_suite(task_name, expected):
    task = json.load(open(os.path.join(FIXTURES_DIR, f"{task_name}.json")))
    assert taskcluster.get_suite(task) == expected


@pytest.mark.parametrize(
    "task_name, expected",
    [
        ("test-linux64-ccov/debug-mochitest-1", "linux"),
        ("test-linux64-ccov/debug-mochitest-e10s-7", "linux"),
        ("test-linux64-ccov/debug-cppunit", "linux"),
        ("test-linux64-ccov/debug-firefox-ui-functional-remote-e10s", "linux"),
        ("test-windows10-64-ccov/debug-mochitest-1", "windows"),
        ("test-windows10-64-ccov/debug-mochitest-e10s-7", "windows"),
        ("test-windows10-64-ccov/debug-cppunit", "windows"),
        ("build-linux64-ccov/debug", "linux"),
        ("build-android-test-ccov/opt", "android"),
        ("build-win64-ccov/debug", "windows"),
    ],
)
def test_get_platform(task_name, expected):
    task = json.load(open(os.path.join(FIXTURES_DIR, f"{task_name}.json")))
    assert taskcluster.get_platform(task) == expected


@mock.patch("time.sleep")
def test_download_artifact_forbidden(mocked_sleep, mock_taskcluster, tmpdir):
    responses.add(
        responses.GET,
        "https://queue.taskcluster.net/v1/task/FBdocjnAQOW_GJDOfmgjxw/artifacts/public%2Ftest_info%2Fcode-coverage-grcov.zip",  # noqa
        body="xml error...",
        status=403,
    )

    with pytest.raises(
        requests.exceptions.HTTPError,
        match="403 Client Error: Forbidden for url: https://queue.taskcluster.net/v1/task/FBdocjnAQOW_GJDOfmgjxw/artifacts/public%2Ftest_info%2Fcode-coverage-grcov.zip",  # noqa
    ):
        taskcluster.download_artifact(
            os.path.join(tmpdir.strpath, "windows_reftest-6_code-coverage-grcov.zip"),
            "FBdocjnAQOW_GJDOfmgjxw",
            "public/test_info/code-coverage-grcov.zip",
        )

    assert mocked_sleep.call_count == 4


@mock.patch("time.sleep")
def test_download_artifact_badzip(mocked_sleep, mock_taskcluster, tmpdir):
    responses.add(
        responses.GET,
        "https://queue.taskcluster.net/v1/task/FBdocjnAQOW_GJDOfmgjxw/artifacts/public%2Ftest_info%2Fcode-coverage-grcov.zip",  # noqa
        body="NOT A ZIP FILE",
        status=200,
        stream=True,
    )

    with pytest.raises(BadZipFile, match="File is not a zip file"):
        taskcluster.download_artifact(
            os.path.join(tmpdir.strpath, "windows_reftest-6_code-coverage-grcov.zip"),
            "FBdocjnAQOW_GJDOfmgjxw",
            "public/test_info/code-coverage-grcov.zip",
        )

    assert mocked_sleep.call_count == 4
