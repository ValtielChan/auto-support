from app.services.imap_client import _junk_folder


class FakeConn:
    def __init__(self, lines):
        self.lines = lines

    def list(self):
        return "OK", self.lines


assert _junk_folder(FakeConn([rb'(\HasNoChildren) "/" INBOX', rb'(\HasNoChildren \Junk) "/" "Courrier ind&AOk-sirable"'])) == "Courrier ind&AOk-sirable"
assert _junk_folder(FakeConn([rb'(\HasNoChildren) "." INBOX', rb'(\HasNoChildren) "." Spam'])) == "Spam"
print("JUNK FOLDER TEST PASSED")

from email import message_from_string  # noqa: E402

from app.services.imap_client import _parse_message  # noqa: E402

m = _parse_message(1, message_from_string(
    "From: BookWitch <contact@bookwitch.io>\nReply-To: jane@example.com\nSubject: Hi\n\nbody"))
assert m["from_email"] == "jane@example.com" and m["from_address"] == "jane@example.com", m
print("REPLY-TO TEST PASSED")
