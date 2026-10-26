#!/usr/bin/env python3
"""Markdown の記事を note の「下書き」として保存する。公開はしない。

note には一般向けの公式APIがないため、note のエディタが内部で使う非公式APIを呼ぶ。
仕様変更で動かなくなることがあり、利用は自己責任。

使い方:
    python3 scripts/note_draft.py --account ai note/accounts/ai/drafts/2026-10-27-xxx.md   # 下書き保存
    python3 scripts/note_draft.py --account ai <ファイル> --dry-run                        # 変換結果だけ表示

認証（アカウントごと。<ID> は --account を大文字にしたもの。例: ai → AI）:
    NOTE_COOKIE_<ID>   ブラウザでそのアカウントにログインした状態の Cookie ヘッダー文字列（推奨）
    NOTE_EMAIL_<ID> / NOTE_PASSWORD_<ID>   ログインAPIで Cookie を取得する（reCAPTCHA で弾かれることがある）
    別アカウントへの誤投稿を防ぐため、共通の NOTE_COOKIE は読まない。

記事ファイルの形式:
    1行目 `# タイトル`、2行目以降が本文（## / ### 見出し、段落、**太字**、- 箇条書き、1. 番号付き、> 引用、---）。
    末尾の `ハッシュタグ:` 行は本文に含めず、標準出力に表示だけする（タグは note の画面で付ける）。
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookies import SimpleCookie

BASE = "https://note.com"
EDITOR = "https://editor.note.com"


# ---------- Markdown → note 用 HTML ----------

def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return text


def _attrs() -> str:
    # note のエディタは各ブロックに name/id を付けている
    u = str(uuid.uuid4())
    return f' name="{u}" id="{u}"'


def md_to_note_html(md: str) -> str:
    out, para, lst, lst_tag, quote = [], [], [], None, []

    def flush():
        nonlocal para, lst, lst_tag, quote
        if para:
            out.append(f"<p{_attrs()}>" + "<br>".join(_inline(x) for x in para) + "</p>")
            para = []
        if lst:
            items = "".join(f"<li><p{_attrs()}>{_inline(x)}</p></li>" for x in lst)
            out.append(f"<{lst_tag}{_attrs()}>{items}</{lst_tag}>")
            lst, lst_tag = [], None
        if quote:
            out.append(f"<blockquote{_attrs()}><p{_attrs()}>" + "<br>".join(_inline(x) for x in quote) + "</p></blockquote>")
            quote = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if m := re.match(r"^(#{2,3})\s+(.*)", line):
            flush()
            tag = "h2" if len(m.group(1)) == 2 else "h3"
            out.append(f"<{tag}{_attrs()}>{_inline(m.group(2))}</{tag}>")
        elif re.match(r"^(-{3,}|\*{3,})$", line.strip()):
            flush()
            out.append(f"<hr{_attrs()}>")
        elif m := re.match(r"^\s*[-*]\s+(.*)", line):
            if lst_tag not in (None, "ul") or para or quote:
                flush()
            lst_tag = "ul"
            lst.append(m.group(1))
        elif m := re.match(r"^\s*\d+[.)]\s+(.*)", line):
            if lst_tag not in (None, "ol") or para or quote:
                flush()
            lst_tag = "ol"
            lst.append(m.group(1))
        elif m := re.match(r"^>\s?(.*)", line):
            if para or lst:
                flush()
            quote.append(m.group(1))
        else:
            if lst or quote:
                flush()
            para.append(line.strip())
    flush()
    return "".join(out)


def parse_article(path: str):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()
    title, start = None, 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title, start = line[2:].strip(), i + 1
            break
    if not title:
        sys.exit("エラー: 1行目に `# タイトル` がありません")
    body_lines, tags = [], ""
    for line in lines[start:]:
        if re.match(r"^\s*ハッシュタグ\s*[:：]", line):
            tags = line.split(":", 1)[-1].split("：", 1)[-1].strip()
        else:
            body_lines.append(line)
    return title, "\n".join(body_lines).strip(), tags


# ---------- HTTP ----------

class Note:
    def __init__(self, cookie: str):
        self.jar = SimpleCookie()
        self.jar.load(cookie)

    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v.value}" for k, v in self.jar.items())

    def request(self, method, path, body=None):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": EDITOR,
            "Referer": EDITOR + "/",
            "User-Agent": "Mozilla/5.0 (compatible; note-draft-script)",
            "Cookie": self.cookie_header(),
        }
        if "XSRF-TOKEN" in self.jar:
            headers["X-XSRF-TOKEN"] = urllib.parse.unquote(self.jar["XSRF-TOKEN"].value)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                for h in res.headers.get_all("Set-Cookie") or []:
                    self.jar.load(h)
                raw = res.read().decode() or "{}"
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            sys.exit(f"エラー: {method} {path} が {e.code} を返しました。\n{detail}\n"
                     "Cookie の期限切れ、または note 側の仕様変更の可能性があります。")
        except urllib.error.URLError as e:
            sys.exit(f"エラー: note.com に接続できません（{e.reason}）。環境のネットワーク設定で note.com を許可してください。")


def login(account: str) -> Note:
    sfx = account.upper()
    cookie = os.environ.get(f"NOTE_COOKIE_{sfx}", "").strip()
    if cookie:
        return Note(cookie)
    email, password = os.environ.get(f"NOTE_EMAIL_{sfx}"), os.environ.get(f"NOTE_PASSWORD_{sfx}")
    if not (email and password):
        sys.exit(f"エラー: NOTE_COOKIE_{sfx}（または NOTE_EMAIL_{sfx} と NOTE_PASSWORD_{sfx}）が設定されていません。")
    n = Note("")
    n.request("POST", "/api/v1/sessions/sign_in", {"login": email, "password": password})
    if not any(k.startswith("_note_session") for k in n.jar):
        sys.exit(f"エラー: ログインに失敗しました。reCAPTCHA で弾かれた可能性があります。NOTE_COOKIE_{sfx} を使ってください。")
    return n


def save_draft(account: str, title: str, body_html: str) -> str:
    n = login(account)
    created = n.request("POST", "/api/v1/text_notes", {"body": body_html, "name": title, "template_key": None})
    data = created.get("data", {})
    note_id, key = data.get("id"), data.get("key")
    if not note_id:
        sys.exit(f"エラー: 下書きを作成できませんでした。応答: {json.dumps(created, ensure_ascii=False)[:500]}")
    n.request("POST", f"/api/v1/text_notes/draft_save?id={note_id}&is_temp_saved=true", {
        "body": body_html,
        "body_length": len(re.sub(r"<[^>]+>", "", body_html)),
        "name": title,
        "index": False,
        "is_lead_form": False,
    })
    return f"{EDITOR}/notes/{key}/edit/" if key else f"{BASE}/notes (id={note_id})"


def main():
    ap = argparse.ArgumentParser(description="Markdown 記事を note の下書きに保存する（公開はしない）")
    ap.add_argument("--account", required=True, help="note/accounts/ 以下のフォルダ名（love, beauty, travel, worktips, ai）")
    ap.add_argument("file")
    ap.add_argument("--dry-run", action="store_true", help="note に送らず、変換結果を表示する")
    args = ap.parse_args()

    title, body_md, tags = parse_article(args.file)
    body_html = md_to_note_html(body_md)
    if args.dry_run:
        print(json.dumps({"title": title, "tags": tags, "chars": len(body_md), "html": body_html}, ensure_ascii=False, indent=2))
        return
    if not re.fullmatch(r"[a-z0-9_]+", args.account):
        sys.exit("エラー: --account は英小文字・数字・_ だけにしてください")
    url = save_draft(args.account, title, body_html)
    print(f"[{args.account}] 下書きを保存しました: {title}\n編集画面: {url}")
    if tags:
        print(f"ハッシュタグ（公開時に付ける）: {tags}")


if __name__ == "__main__":
    main()
