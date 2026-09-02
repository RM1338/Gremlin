"""A login screen is a wall: coverage taps each field (which only focuses it)
and never types, so the run loops there until the step budget. With credentials
configured the explorer must fill every matching field and tap submit, once.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin.config import Config
from gremlin.explorer import Explorer, _SCROLL_TRIES
from gremlin.grounding import Element


class FakeDev:
    def __init__(self):
        self.calls = []

    def tap(self, x, y):
        self.calls.append(("tap", x, y))

    def type_text(self, text):
        self.calls.append(("type", text))

    def clear_text(self, n=80):
        self.calls.append(("clear",))

    def scroll(self, direction="down"):
        self.calls.append(("scroll", direction))

    def back(self):
        self.calls.append(("back",))


def _explorer(**login):
    cfg = Config(package="com.x", activity="com.x/.Main", platform="flutter")
    cfg.login = login
    exp = Explorer(cfg)
    exp.dev = FakeDev()
    return exp


EMAIL = Element(0, "Email address", 100, 200, clickable=True, bounds=(0, 0, 1, 1), editable=True)
OTP = Element(1, "Enter OTP", 100, 300, clickable=True, bounds=(0, 0, 1, 1), editable=True)
SUBMIT = Element(2, "Sign in", 100, 400, clickable=True, bounds=(0, 0, 1, 1))
JUNK = Element(3, "Forgot password?", 100, 500, clickable=True, bounds=(0, 0, 1, 1))


def _field(idx, label, y):
    return Element(idx, label, 100, y, clickable=True, bounds=(20, y - 10, 380, y + 10), editable=True)


def _btn(idx, label, y, wide=True):
    x2 = 380 if wide else 90
    return Element(idx, label, (20 + x2) // 2, y, clickable=True, bounds=(20, y - 10, x2, y + 10))


def test_fills_matching_fields_then_submits_once():
    exp = _explorer(email="gremlin@example.com", otp="000000")
    screen = [EMAIL, OTP, SUBMIT, JUNK]

    verbs = []
    for _ in range(6):
        act = exp._advance_login(screen, screen_id=1)
        if act is None:
            break
        verbs.append((act.verb, act.target_label, act.text))

    assert verbs == [
        ("type", "Email address", "gremlin@example.com"),
        ("type", "Enter OTP", "000000"),
        ("tap", "Sign in", None),
    ]
    # Each field is focused, cleared of any pre-fill, then typed; submit tapped.
    assert exp.dev.calls == [
        ("tap", 100, 200), ("clear",), ("type", "gremlin@example.com"),
        ("tap", 100, 300), ("clear",), ("type", "000000"),
        ("tap", 100, 400),
    ]
    # A second visit to the same screen does nothing (no re-loop).
    assert exp._advance_login(screen, screen_id=1) is None


def test_noop_without_credentials():
    exp = _explorer()  # nothing configured
    assert exp._advance_login([EMAIL, SUBMIT], screen_id=1) is None


def test_noop_when_no_field_matches():
    exp = _explorer(username="bob")  # app asks for email, not username
    assert exp._advance_login([EMAIL, SUBMIT], screen_id=1) is None


def test_submits_even_with_no_button():
    exp = _explorer(email="a@b.com")
    acts = []
    while (a := exp._advance_login([EMAIL], screen_id=7)) is not None:
        acts.append(a.verb)
    assert acts == ["type"]  # filled the field, nothing to submit


class FakeInbox:
    def __init__(self, code):
        self.code = code
        self.polls = 0

    def wait_for_code(self, **_):
        self.polls += 1
        return self.code


def test_otp_field_filled_from_the_inbox():
    exp = _explorer(email="gremlin@abc.test", otp="auto", code="auto")
    exp._mailbox = FakeInbox("481920")
    screen = [EMAIL, OTP, SUBMIT]

    filled = {}
    while (a := exp._advance_login(screen, screen_id=2)) is not None:
        if a.verb == "type":
            filled[a.target_label] = a.text
    assert filled == {"Email address": "gremlin@abc.test", "Enter OTP": "481920"}
    assert exp._mailbox.polls == 1


def test_no_code_leaves_otp_blank_but_still_submits():
    exp = _explorer(email="gremlin@abc.test", otp="auto")
    exp._mailbox = FakeInbox(None)  # nothing ever arrives
    verbs = []
    while (a := exp._advance_login([EMAIL, OTP, SUBMIT], screen_id=3)) is not None:
        verbs.append(a.verb)
    assert verbs == ["type", "tap"]  # email typed, OTP skipped, submit still tapped


def test_fresh_inbox_goes_to_signup_before_signing_in():
    exp = _explorer(email="gremlin@abc.test", password="Gr3mlin-abcd")
    exp._fresh_signup = True
    signin = [_field(0, "Email", 200), _field(1, "Password", 260),
              _btn(2, "Sign in", 340, wide=True), _btn(3, "Sign up", 400, wide=False)]

    a = exp._advance_login(signin, screen_id=1)
    assert a.verb == "tap" and a.target_label == "Sign up"
    assert a.reason == "login: go to sign-up"
    assert exp._fresh_signup is True  # still navigating

    # The sign-up screen: now it fills the form.
    signup = [_field(0, "Email", 200), _field(1, "Password", 260),
              _field(2, "Confirm password", 320), _btn(3, "Create account", 400)]
    verbs = []
    while (a := exp._advance_login(signup, screen_id=2)) is not None:
        verbs.append((a.verb, a.target_label, a.text))
    assert verbs == [
        ("type", "Email", "gremlin@abc.test"),
        ("type", "Password", "Gr3mlin-abcd"),
        ("type", "Confirm password", "Gr3mlin-abcd"),  # reuses the password
        ("tap", "Create account", None),
    ]
    assert exp._fresh_signup is False


def test_already_on_signup_does_not_bounce_to_signin():
    exp = _explorer(email="a@b.test", password="Gr3mlin-abcd")
    exp._fresh_signup = True
    # Sign-up screen whose only "sign in" text is the decoy link.
    screen = [_field(0, "Email", 200), _field(1, "Password", 260),
              _btn(2, "Sign up", 340, wide=True),
              _btn(3, "Already have an account? Sign in", 400, wide=False)]
    a = exp._advance_login(screen, screen_id=1)
    assert a.verb == "type" and a.target_label == "Email"  # filled, not navigated


def test_name_field_is_filled_on_signup():
    exp = _explorer(email="a@b.test", name="Gremlin QA", password="Gr3mlin-x")
    fields = [_field(0, "Full name", 180), _field(1, "Email", 240), _field(2, "Password", 300)]
    got = {e.label: v for e, _n, v in exp._assign_fields(fields)}
    assert got == {"Full name": "Gremlin QA", "Email": "a@b.test", "Password": "Gr3mlin-x"}


def test_username_field_not_stolen_by_name_credential():
    exp = _explorer(username="bob", name="Gremlin QA")
    fields = [_field(0, "Username", 180), _field(1, "Display name", 240)]
    got = {e.label: v for e, _n, v in exp._assign_fields(fields)}
    assert got == {"Username": "bob", "Display name": "Gremlin QA"}


def test_unlabelled_extra_field_gets_positional_fill():
    exp = _explorer(email="a@b.test", password="pw")
    fields = [_field(0, "Email", 200), _field(1, "(unlabeled)", 260)]
    got = [(e.label, v) for e, _n, v in exp._assign_fields(fields)]
    assert got == [("Email", "a@b.test"), ("(unlabeled)", "pw")]


def test_prefilled_email_field_is_still_matched_and_cleared():
    exp = _explorer(email="real@inbox.test")
    # field label carries a remembered value, not a hint
    prefilled = _field(0, "old@example.com", 200)
    got = [(e.label, v) for e, _n, v in exp._assign_fields([prefilled])]
    assert got == [("old@example.com", "real@inbox.test")]  # matched via "@"


def test_regrounds_after_keyboard_reflow_uses_fresh_coordinates():
    """The bug this replaces: a queued plan taps where the Email field WAS
    before the keyboard pushed the layout up — landing on the 'Sign in' link."""
    exp = _explorer(email="a@b.test", name="Gremlin QA", password="pw")
    down = [_field(0, "Full name", 300), _field(1, "Email", 360),
            _field(2, "Password", 420), _btn(3, "Create account", 500)]
    a = exp._advance_login(down, screen_id=9)
    assert (a.verb, a.target_label, a.y) == ("type", "Full name", 300)

    # Keyboard now up: every field has moved, and the name field shows its value.
    up = [_field(0, "Gremlin QA", 120), _field(1, "Email", 180),
          _field(2, "Password", 240), _btn(3, "Create account", 320)]
    a = exp._advance_login(up, screen_id=9)
    assert (a.verb, a.target_label, a.y) == ("type", "Email", 180)  # not the stale 360
    a = exp._advance_login(up, screen_id=9)
    assert (a.verb, a.target_label, a.y) == ("type", "Password", 240)


def test_auth_screen_never_lets_model_or_coverage_leave_the_flow():
    from gremlin.policy import Decision
    exp = _explorer(email="a@b.com", password="pw")
    exp._login_filled[5] = {"email", "password"}  # form done
    exp._login_submitted.add(5)                   # and submitted
    elements = [_field(0, "Email", 200), _field(1, "Password", 260), _btn(2, "Sign in", 340)]
    dec = Decision(verb="tap", index=2, text=None, direction=None,
                   reason="model wants to tap sign-in", screen_name="Login")

    act = exp._choose_and_execute(dec, elements, untapped=[elements[2]], screen_id=5)
    assert act.verb == "scroll"  # looked for more fields, did NOT tap the link
    for _ in range(_SCROLL_TRIES):
        act = exp._choose_and_execute(dec, elements, [elements[2]], 5)
    assert act.verb == "back"
    assert not any(c[0] == "tap" for c in exp.dev.calls)  # nothing was tapped


if __name__ == "__main__":
    test_fills_matching_fields_then_submits_once()
    test_noop_without_credentials()
    test_noop_when_no_field_matches()
    test_submits_even_with_no_button()
    test_otp_field_filled_from_the_inbox()
    test_no_code_leaves_otp_blank_but_still_submits()
    test_fresh_inbox_goes_to_signup_before_signing_in()
    test_already_on_signup_does_not_bounce_to_signin()
    test_name_field_is_filled_on_signup()
    test_username_field_not_stolen_by_name_credential()
    test_unlabelled_extra_field_gets_positional_fill()
    test_prefilled_email_field_is_still_matched_and_cleared()
    test_auth_screen_never_lets_model_or_coverage_leave_the_flow()
    print("ok")
