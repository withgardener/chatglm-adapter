from dataclasses import dataclass


@dataclass
class StreamState:
    started: bool = False
    finished: bool = False

    def mark_emitted(self) -> None:
        self.started = True

