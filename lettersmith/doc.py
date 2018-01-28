from os import path
from pathlib import PurePath
from datetime import date as Date

import frontmatter

from lettersmith.date import parse_iso_8601, read_file_times, EPOCH
from lettersmith.file import write_file_deep
from lettersmith.stringtools import truncate, strip_html
from lettersmith import path as pathtools
from lettersmith.util import put, merge, unset, pick


def load(pathlike, relative_to=""):
    """
    Loads a basic doc dictionary from a file path. This dictionary
    contains content string, the meta (headmatter) of the doc and some
    basic information about the file.

    Returns a dictionary.
    """
    file_created_time, file_modified_time = read_file_times(pathlike)
    with open(pathlike) as f:
        raw = f.read()
        meta, content = frontmatter.parse(raw)
        input_path = PurePath(pathlike)
        simple_path = input_path.relative_to(relative_to)
        output_path = pathtools.to_nice_path(simple_path)

        return {
            "file_created_time": file_created_time,
            "file_modified_time": file_modified_time,
            "input_path": str(input_path),
            "simple_path": str(simple_path),
            "output_path": str(output_path),
            "meta": meta,
            "content": content
        }


def rm_content(doc):
    """
    Remove the content field.
    Useful if you need to collect a lot of docs into memory and the content
    field is huge. Pairs well with `reload_content`.

    Returns a new doc.
    """
    return unset(doc, ("content",))


def reload_content(doc):
    """
    Reload the content field, if missing.

    Returns a new doc.
    """
    if doc.get("content"):
        return doc
    else:
        try:
            with open(doc["input_path"]) as f:
                raw = f.read()
                meta, content = frontmatter.parse(raw)
                return put(doc, "content", content)
        except KeyError:
            return put(doc, "content", "")


def write(doc, output_dir):
    """
    Write a doc to the filesystem.

    Uses `doc["output_path"]` and `output_dir` to construct the output path.
    """
    write_file_deep(path.join(output_dir, doc["output_path"]), doc["content"])


def read_summary(doc, max_len=250, suffix="..."):
    """
    Read or generate a summary for a doc.
    Returns a string.
    """
    try:
        return doc["meta"]["summary"]
    except KeyError:
        return truncate(strip_html(doc.get("content", "")), max_len, suffix)


def read_title(doc):
    """
    Generate a title for the doc. Use either doc.meta.title, or
    derive a title from the filename.
    """
    try:
        return doc["meta"]["title"]
    except KeyError:
        return pathtools.to_title(doc["input_path"])


def read_date(doc):
    """
    Parse date from headmatter, or use file created time.
    """
    try:
        return parse_iso_8601(doc["meta"]["date"])
    except (ValueError, TypeError, KeyError):
        return doc.get("file_created_time", EPOCH)


def read_modified(doc):
    """
    Parse modified date from headmatter, or use file created time.
    """
    try:
        return parse_iso_8601(doc["meta"]["modified"])
    except (ValueError, TypeError, KeyError):
        return doc.get("file_modified_time", EPOCH)


def decorate_smart_items(doc):
    """
    Decorate doc with a variety of derived items, like automatic
    title, summary, etc.

    These are mostly computed properties that rely on logic or more than
    one value of the doc. Useful to have around in the template, where
    it's awkward to derive values with functions.
    """
    return merge(doc, {
        "title": read_title(doc),
        "summary": read_summary(doc),
        "section": pathtools.tld(doc["simple_path"]),
        "date": read_date(doc),
        "modified": read_modified(doc)
    })


# Whitelist of keys to keep for li objects
_LI_KEYS = (
    "title",
    "date",
    "modified",
    "file_created_time",
    "file_modified_time",
    "simple_path",
    "output_path",
    "section",
    "meta",
    "summary"
)


def to_li(doc):
    """
    Return a "list item" version of the doc... a small dictionary
    with a handful of whitelisted fields. This is typically what is
    used for indexes.
    """
    return pick(doc, _LI_KEYS)


def change_ext(doc, ext):
    """Change the extention on a doc's output_path, returning a new doc."""
    updated_path = PurePath(doc["output_path"]).with_suffix(ext)
    return put(doc, "output_path", updated_path)


def with_path(glob):
    """
    Check if a path matches glob pattern.
    """
    def has_path(doc):
        return fnmatch(doc["simple_path"], glob)
    return has_path