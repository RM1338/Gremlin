"""Pulling the OTP out of a verification email: the part that runs without a
network. mail.tm itself is exercised by `python -m gremlin.mailbox`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin.mailbox import _extract_code


def test_prefers_a_six_digit_run():
    assert _extract_code("Your Scribe code is 481920 — expires in 10 min") == "481920"
    assert _extract_code("Ref #12 shipped. Security PIN: 903117") == "903117"


def test_falls_back_to_shorter_runs():
    assert _extract_code("Enter 4821 to continue") == "4821"
    assert _extract_code("code 12345678") == "12345678"


def test_none_when_no_digits():
    assert _extract_code("Welcome! Click the link to verify.") is None
    assert _extract_code("") is None


if __name__ == "__main__":
    test_prefers_a_six_digit_run()
    test_falls_back_to_shorter_runs()
    test_none_when_no_digits()
    print("ok")
