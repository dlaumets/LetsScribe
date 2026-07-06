"""Domain errors for transcription jobs."""


class JobCancelled(Exception):
    """Raised when a job is cancelled while processing."""
