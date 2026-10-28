"""Wire the ChangeEventRecorder to every ontology event it handles, as app.py does."""

import re

from adapters.events.change_recorder import ChangeEventRecorder
from domain.ontology import events as ontology_events


def wire_change_recorder(publisher, change_repo) -> None:
    """Subscribe the recorder's on_<event_name> handler for each ontology event class."""
    recorder = ChangeEventRecorder(change_repo)
    for name in dir(ontology_events):
        handler_name = "on_" + re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        handler = getattr(recorder, handler_name, None)
        if handler is not None:
            publisher.subscribe(getattr(ontology_events, name), handler)
