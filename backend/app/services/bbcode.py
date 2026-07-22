"""Tiny BBCode → HTML / plain-text converter for outgoing replies.

Supported tags: [b] [i] [u] [url]/[url=…] [list]/[*]. Everything else is passed
through as text. HTML is escaped first, so user input can never inject markup.
"""

import html as htmllib
import re


def _list_to_html(match: re.Match) -> str:
    items = re.findall(r"\[\*\]\s*(.+?)(?=\[\*\]|$)", match.group(1), flags=re.S | re.I)
    lis = "".join(f"<li>{i.strip()}</li>" for i in items if i.strip())
    return f"<ul>{lis}</ul>"


def to_html(text: str) -> str:
    s = htmllib.escape(text or "", quote=False)
    s = re.sub(r"\[url=([^\]\s]+)\](.+?)\[/url\]",
               r'<a href="\1">\2</a>', s, flags=re.S | re.I)
    s = re.sub(r"\[url\]([^\[]+?)\[/url\]",
               r'<a href="\1">\1</a>', s, flags=re.S | re.I)
    s = re.sub(r"\[b\](.+?)\[/b\]", r"<strong>\1</strong>", s, flags=re.S | re.I)
    s = re.sub(r"\[i\](.+?)\[/i\]", r"<em>\1</em>", s, flags=re.S | re.I)
    s = re.sub(r"\[u\](.+?)\[/u\]", r"<u>\1</u>", s, flags=re.S | re.I)
    s = re.sub(r"\[list\](.+?)\[/list\]", _list_to_html, s, flags=re.S | re.I)
    # Remaining newlines become <br>, but not the ones we just wrapped in <ul>.
    s = re.sub(r"\s*<ul>", "<ul>", s)
    s = re.sub(r"</ul>\s*", "</ul>", s)
    s = s.replace("\n", "<br>\n")
    return s


def to_plain(text: str) -> str:
    s = text or ""
    s = re.sub(r"\[url=([^\]\s]+)\](.+?)\[/url\]", r"\2 (\1)", s, flags=re.S | re.I)
    s = re.sub(r"\[url\]([^\[]+?)\[/url\]", r"\1", s, flags=re.S | re.I)
    s = re.sub(r"\[\*\]\s*", "- ", s)
    s = re.sub(r"\[/?(b|i|u|list)\]", "", s, flags=re.I)
    return s.strip()
