import logging
import multiprocessing

import pytest

import stores.index_utils as utils

logging.basicConfig()
logger = logging.getLogger("stores.test_index.test_multiprocessing")
logger.setLevel(logging.INFO)


def test_run_mp_process_helper(sample_tool):
    sample_text = "hello world"
    parent_conn, child_conn = multiprocessing.Pipe()
    result = utils.run_mp_process_helper(
        fn=sample_tool["function"],
        kwargs={
            "bar": sample_text,
        },
        conn=child_conn,
    )
    assert result == sample_text
    pipe_result = parent_conn.recv()
    assert pipe_result == sample_text


def test_run_mp_process_helper_error(buggy_tool):
    parent_conn, child_conn = multiprocessing.Pipe()
    with pytest.raises(buggy_tool["error"]):
        utils.run_mp_process_helper(
            fn=buggy_tool["function"],
            conn=child_conn,
        )
        # In case of error, pipe will receive error
        pipe_result = parent_conn.recv()
        raise pipe_result


def test_run_mp_process(sample_tool):
    sample_text = "hello world"
    result = utils.run_mp_process(
        fn=sample_tool["function"],
        kwargs={
            "bar": sample_text,
        },
    )
    assert result == sample_text
