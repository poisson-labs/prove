"""A fake of botocore, as far as resolving credentials goes, for Prove's cloud readiness probe.

What the fake keeps: ``botocore.exceptions.MissingDependencyException`` is what botocore raises
while resolving a session made by ``aws login`` when its ``crt`` extra is missing (its text names
``botocore[crt]``), and ``NoCredentialsError`` what a signing call raises with no credentials.
The fake's behaviour is the state folder's ``sdk.json`` (``boto3/__init__.py``).
"""

__version__ = "1.42.39"
