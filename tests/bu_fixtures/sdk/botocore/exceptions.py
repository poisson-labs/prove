"""``botocore.exceptions``, the two the probe can meet."""


class BotoCoreError(Exception):
    fmt = "An unspecified error occurred"

    def __init__(self, **kwargs):
        super().__init__(self.fmt.format(**kwargs))
        self.kwargs = kwargs


class MissingDependencyException(BotoCoreError):
    fmt = "Missing Dependency: {msg}"


class NoCredentialsError(BotoCoreError):
    fmt = "Unable to locate credentials"
