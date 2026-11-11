"""A fake of the AWS CLI version 2, for Prove's cloud readiness checks: no network, no file read.

A test copies this file into a folder of its own on ``PATH`` as ``aws`` (with a shebang naming the
test's interpreter), beside ``aws-state.json``:

    {"account": "603052864933", "signed_in": true | false | "expired",
     "quota": 40 | "denied" | null, "hangs": ["sts"] | ["service-quotas"],
     "answers_after": 2.0}

Every call is appended to ``aws-calls.jsonl`` beside it: its arguments, its whole environment, its
pid, its process group and its session. A call whose service is in ``hangs`` is recorded and then
never answers (a CLI waiting on a network that does not); with ``answers_after`` every call
waits that many seconds before it answers.
The two read-only calls it answers, as the real CLI answers them:

- ``aws sts get-caller-identity --output json``: ``{"UserId", "Account", "Arn"}``; signed out,
  exit 253 and botocore's "Unable to locate credentials" on stderr; an expired session, exit 255.
- ``aws service-quotas get-service-quota --service-code ec2 --quota-code L-1216C47A --region R
  --output json``: ``{"Quota": {..., "Value": 40.0}}``; ``"denied"``, exit 254 and an
  ``AccessDeniedException`` on stderr.

Anything else is recorded and refused, exit 252: a check must not write, sign in or create.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    args = sys.argv[1:]
    with open(os.path.join(HERE, "aws-calls.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": args, "env": dict(os.environ), "time": time.time(),
                             "pid": os.getpid(), "pgid": os.getpgid(0), "sid": os.getsid(0)}) + "\n")
    with open(os.path.join(HERE, "aws-state.json"), encoding="utf-8") as fh:
        state = json.load(fh)
    if args and args[0] in state.get("hangs", []):
        while True:
            time.sleep(0.5)
    time.sleep(float(state.get("answers_after", 0) or 0))
    account = state.get("account", "603052864933")
    if args[:2] == ["sts", "get-caller-identity"]:
        signed_in = state.get("signed_in", True)
        if signed_in is True:
            print(json.dumps({"UserId": "AIDAFAKEUSERID000000", "Account": account,
                              "Arn": f"arn:aws:iam::{account}:user/reader"}, indent=4))
            return 0
        if signed_in == "expired":
            print("\nError when retrieving token from sso: Token has expired and refresh failed",
                  file=sys.stderr)
            return 255
        print("\nUnable to locate credentials. You can configure credentials by running "
              '"aws login".', file=sys.stderr)
        return 253
    if args[:2] == ["service-quotas", "get-service-quota"]:
        quota = state.get("quota")
        if quota == "denied":
            print("\nAn error occurred (AccessDeniedException) when calling the GetServiceQuota "
                  f"operation: User: arn:aws:iam::{account}:user/reader is not authorized to "
                  "perform: servicequotas:GetServiceQuota", file=sys.stderr)
            return 254
        print(json.dumps({"Quota": {"ServiceCode": "ec2", "QuotaCode": "L-1216C47A",
                                    "QuotaName": "Running On-Demand Standard (A, C, D, H, I, M, R, "
                                    "T, Z) instances", "Value": float(quota), "Unit": "None",
                                    "Adjustable": True, "GlobalQuota": False}}, indent=4))
        return 0
    print(f"fake aws: {' '.join(args)} is not a call Prove's checks may make", file=sys.stderr)
    return 252


if __name__ == "__main__":
    sys.exit(main())
