import datetime
import json
import sys
import threading
import traceback
from abc import ABC, abstractmethod
from typing import TextIO, Any, Callable, Dict
from uuid import uuid1


class Clock(ABC):
    """Superclass for clock types used by the EventLogger"""

    @abstractmethod
    def now(self, tz: datetime.timezone = datetime.timezone.utc) -> datetime.datetime:
        """Returns the current datetime"""
        pass


class SystemClock(Clock):
    def now(self, tz: datetime.timezone = datetime.timezone.utc) -> datetime.datetime:
        return datetime.datetime.now(tz=tz)


def extract_stacktrace(exception: Exception) -> str:
    return "".join(traceback.TracebackException.from_exception(exception).format())


class CorrelationID:
    class LocalWithValueField(threading.local):
        def __init__(self):
            self.value = None

    def __init__(self, generate_id: Callable[[], str] = lambda: str(uuid1())):
        self.generate_id = generate_id
        self.correlation_id = CorrelationID.LocalWithValueField()

    def set(self, value: str or None) -> None:
        self.correlation_id.value = value or self.generate_id()

    def get(self) -> str:
        return self.correlation_id.value

    def reset(self) -> None:
        self.correlation_id.value = None


class Event(ABC):
    """Superclass for all log event types."""

    def type(self):
        return self.__class__.__name__


class JSONEncoder(json.JSONEncoder):
    """Encoder used to translate datetime to iso strings,
    and exceptions into their stack traces."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, Exception):
            return extract_stacktrace(obj)
        return json.JSONEncoder.default(self, obj)


class EventLogger(ABC):
    def __init__(self, correlation_id: CorrelationID, clock: Clock):
        self.correlation_id = correlation_id
        self.__clock = clock

    def asJson(self, event: Event) -> Dict:
        metadata = {"timestamp": self.__clock.now(),
                    "type": event.type()}
        if self.correlation_id:
            metadata.update({"correlation_id": self.correlation_id.get()})
        return {"metadata": metadata,
                "event": vars(event)}

    @abstractmethod
    def log(self, event: Event) -> None:
        pass


class TextStreamEventLogger(EventLogger):

    def __init__(self, correlation_id: CorrelationID = None,
                 clock: Clock = SystemClock(), output: TextIO = sys.stdout):
        super().__init__(correlation_id, clock)
        self.__output = output

    def log(self, event: Event) -> None:
        print(json.dumps(self.asJson(event), cls=JSONEncoder), file=self.__output)
