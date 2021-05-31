# noinspection PyUnresolvedReferences
#
# The noinspection comment above is to tell PyCharm that the import below
# is important, and cannot be deleted during import optimizations,
# even if it's not referenced within the code.
import testcontext  # This must be the first import.

import io
import json
import threading
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TextIO, Callable, List

import eventlogging


@dataclass(frozen=True)
class TestClock(eventlogging.Clock):
    datetime = datetime(2021, 5, 1, 11, 22, 33, 1234, tzinfo=timezone.utc)

    def now(self, tz: timezone = timezone.utc) -> datetime:
        return self.datetime


def read_text(output: TextIO) -> str:
    output.seek(0)
    return output.read()


def make_exception_with_stack_trace() -> Exception:
    try:
        raise Exception("first")
    except Exception:
        try:
            raise Exception("second")
        except:
            try:
                raise Exception("third")
            except Exception as e:
                return e


def extract_stacktrace(exception: Exception) -> str:
    return eventlogging.extract_stacktrace(exception).replace("\n", "\\n").replace('"', '\\"')


class TextStreamEventLoggerTest(unittest.TestCase):

    def setUp(self):
        self.event_stream = io.StringIO()
        self.clock = TestClock()
        self.event_logger = eventlogging.TextStreamEventLogger(clock=self.clock, output=self.event_stream)

    def test_logged_event_string_ends_with_newline(self):
        class TestEvent(eventlogging.Event):
            def __init__(self, value: str):
                self.value = value

        event = TestEvent("value")
        self.event_logger.log(event)

        created_json = read_text(self.event_stream)

        self.assertEqual(created_json[-1], "\n")

    def test_logs_primitive_types(self):
        class TestEvent(eventlogging.Event):
            def __init__(self, value_str: str, value_int: int, value_float: float, value_bool: bool):
                self.value_bool = value_bool
                self.value_float = value_float
                self.value_int = value_int
                self.value_str = value_str

        event = TestEvent("str", 1, 1.2, True)

        expected_json = f""" {{"metadata": {{"timestamp": "{self.clock.datetime.isoformat()}", 
                                             "type": "{event.type()}"
                                           }}, 
                               "event": {{"value_str": "{event.value_str}", 
                                          "value_int": {event.value_int},
                                          "value_float": {event.value_float}, 
                                          "value_bool": {str(event.value_bool).lower()} }}
                              }}
        """
        self.event_logger.log(event)

        self.assertLoggedEventEquals(expected_json)

    def test_logs_exception_stack_trace(self):
        class TestEvent(eventlogging.Event):
            def __init__(self, exc: Exception):
                self.exc = exc

        exception = make_exception_with_stack_trace()
        expected_stacktrace = extract_stacktrace(exception)
        event = TestEvent(exception)

        expected_json = f""" {{"metadata": {{"timestamp": "{self.clock.datetime.isoformat()}", 
                                             "type": "{event.type()}"
                                           }}, 
                               "event": {{"exc": "{expected_stacktrace}"}}
                              }}
        """

        self.event_logger.log(event)

        self.assertLoggedEventEquals(expected_json)

    def test_logs_datetime_in_iso_format(self):
        class TestEvent(eventlogging.Event):
            def __init__(self, timestamp: datetime):
                self.timestamp = timestamp

        timestamp = datetime.now()
        event = TestEvent(timestamp)

        expected_json = f""" {{"metadata": {{"timestamp": "{self.clock.datetime.isoformat()}", 
                                             "type": "{event.type()}"
                                           }}, 
                               "event": {{"timestamp": "{timestamp.isoformat()}"}}
                              }}
        """

        self.event_logger.log(event)

        self.assertLoggedEventEquals(expected_json)

    def test_adds_correlation_id_to_metadata(self):
        class TestEvent(eventlogging.Event):
            def __init__(self, int_value: int):
                self.int_value = int_value

        event = TestEvent(1)

        expected_correlation_id_value = "correlation id"
        correlation_id = eventlogging.CorrelationID(generate_id=lambda: expected_correlation_id_value)

        expected_json = f""" {{"metadata": {{"timestamp": "{self.clock.datetime.isoformat()}", 
                                             "type": "{event.type()}",
                                             "correlation_id": "{expected_correlation_id_value}"
                                           }}, 
                               "event": {{"int_value": {event.int_value}}}
                              }}
        """

        self.event_logger = eventlogging.TextStreamEventLogger(correlation_id=correlation_id, clock=self.clock,
                                                               output=self.event_stream)

        correlation_id.set(expected_correlation_id_value)
        self.event_logger.log(event)

        self.assertLoggedEventEquals(expected_json)

    def test_sets_correlation_id_to_null_in_metadata_if_correlation_id_is_never_set(self):
        class TestEvent(eventlogging.Event):
            def __init__(self, int_value: int):
                self.int_value = int_value

        event = TestEvent(1)

        correlation_id = eventlogging.CorrelationID(generate_id=lambda: "a correlation id")

        expected_json = f""" {{"metadata": {{"timestamp": "{self.clock.datetime.isoformat()}", 
                                             "type": "{event.type()}",
                                             "correlation_id": null
                                           }}, 
                               "event": {{"int_value": {event.int_value}}}
                              }}
        """

        self.event_logger = eventlogging.TextStreamEventLogger(correlation_id=correlation_id, clock=self.clock,
                                                               output=self.event_stream)

        self.event_logger.log(event)

        self.assertLoggedEventEquals(expected_json)

    def assertLoggedEventEquals(self, expected_json: str) -> None:
        created_json = read_text(self.event_stream)
        self.assertEqual(json.loads(expected_json), json.loads(created_json))


class CorrelationIDTest(unittest.TestCase):

    def setUp(self):
        self.generated_id = "test id"
        self.id_generator = lambda: self.generated_id
        self.correlation_id = eventlogging.CorrelationID(generate_id=self.id_generator)

    def test_value_is_thread_local(self):
        value_main_thread = "id_main_thread_something"
        value_other_thread = "id_other_thread_something_else"

        self.correlation_id.set(value_main_thread)

        self.set_correlation_id_in_other_thread_to(value_other_thread)

        self.assertEqual(self.correlation_id.get(), value_main_thread)

    def test_returns_none_when_not_set(self):
        self.assertIsNone(self.correlation_id.get())
        self.assertReturnsNoneInOtherThread()

    def test_resets_value_to_none(self):
        self.correlation_id.set("some value")
        self.correlation_id.reset()
        self.assertIsNone(self.correlation_id.get())

    def test_reset_value_is_thread_local(self):
        expected_id = "expected id"
        self.correlation_id.set(expected_id)
        self.reset_in_other_thread()
        self.assertEqual(expected_id, self.correlation_id.get())

    def test_generates_new_value_when_value_set_to_none(self):
        self.correlation_id.set(None)
        self.assertEqual(self.generated_id, self.correlation_id.get())

    def test_generates_id_when_value_set_to_empty_string(self):
        self.correlation_id.set("")
        self.assertEqual(self.generated_id, self.correlation_id.get())

    def test_default_id_generator_returns_uuid1(self):
        correlation_id = eventlogging.CorrelationID()
        correlation_id.set(None)
        self.assertRegex(correlation_id.get(),
                         "^[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-"
                         "[0-9a-z]{4}-[0-9a-z]{12}$")

    def set_correlation_id_in_other_thread_to(self, correlation_id_value: str) -> None:
        def func(result: List):
            self.correlation_id.set(correlation_id_value)
            result.append(self.correlation_id.get())

        func_result = []
        self.execute_in_other_thread(func, func_result)
        self.assertEqual(func_result[0], correlation_id_value)

    def assertReturnsNoneInOtherThread(self):
        def func(result: List):
            result.append(self.correlation_id.get())

        func_result = []
        self.execute_in_other_thread(func, func_result)
        self.assertIsNone(func_result[0])

    def reset_in_other_thread(self):
        def func(result: List):
            self.correlation_id.reset()
            result.append(self.correlation_id.get())

        func_result = []
        self.execute_in_other_thread(func, func_result)
        self.assertIsNone(func_result[0])

    def execute_in_other_thread(self, func: Callable[[List], None], func_result_holder: List) -> None:
        other_thread = threading.Thread(target=func, args=[func_result_holder])
        other_thread.start()
        other_thread.join()


if __name__ == "__main__":
    unittest.main()
