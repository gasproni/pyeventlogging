# Logs As Structured Events In Python

This is a small framework to support logs as structured events in Python.
It supports Python 3.8+. It has also support for correlation ids to be used
when creating a service-based system.

## Getting Started

All the code is in the eventlogging.py module.

A log event is a subclass of `eventlogging.Event`, e.g. 
the following declaration:

```python
from eventlogging import Event
from datetime import datetime

class PaymentMade(Event):
    def __init__(self, paid_at: datetime, paid_by: str):
        self.paid_at = paid_at
        self.paid_by = paid_by

```

creates an event of type `PaymentMade` with two fields `paidAt` and `paidBy`.
If we use an instance of `TextStreamEventLogger` to log an instance of that event, e.g.: 

```python
from eventlogging import TextStreamEventLogger
from datetime import datetime
import PaymentMade

...

logEvent = TextStreamEventLogger()

...

logEvent(PaymentMade(paid_at=datetime.now(), paid_by="MrCustomer"))

```
the corresponding log entry will be
```json
{
  "metadata": {
    "timestamp": "<ISO format of UTC time at which the log was produced>",
    "type": "PaymentMade"
  },
  "event": {
    "paid_at": "<ISO time format of paidAt field>",
    "paid_by": "MrCustomer"
  }
}
```

## Supported Field Types

The framework currently supports the following types for event fields:
 
  * All numeric types
  * `str`
  * `bool`
  * `datetime.datetime` (rendered as an ISO time string)
  * `Exception` and its subclasses. Exceptions will be transformed in a string containing the entire stack trace.