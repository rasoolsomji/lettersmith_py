"""
Tools for parsing and rendering `[[wikilinks]]`

To render wikilinks, I need:

- An index of all doc urls (to know if they exist)
- A regular expression to match links
- A base URL to root links to (optional, could just root to "/" and absolutize
  with another plugin)
"""
import re
from pathlib import PurePath
from os import path
from lettersmith import doc as Doc
from lettersmith.path import to_slug, to_url
from lettersmith.util import replace


WIKILINK = r'\[\[([^\]]+)\]\]'
LINK_TEMPLATE = '<a href="{url}" class="wikilink">{text}</a>'
NOLINK_TEMPLATE = '<span class="nolink">{text}</span>'


def index_slug_to_url(stubs, base_url="/"):
    """
    Reduce an iterator of docs to a slug-to-url index.
    """
    return {
        to_slug(stub.title): to_url(stub.output_path, base=base_url)
        for stub in stubs
    }


def doc_renderer(stubs,
    base_url="",
    link_template=LINK_TEMPLATE, nolink_template=NOLINK_TEMPLATE):
    """
    Given a tuple of stubs, returns a doc rendering function that will
    render all `[[wikilinks]]` to HTML links.

    `[[wikilink]]` is replaced with a link to a stub with the same title
    (case insensitive), using the `link_template`.
    If no stub exists with that title it will be rendered
    using `nolink_template`.
    """
    slug_to_url = index_slug_to_url(stubs, base_url)
    def render_inner_match(match):
        inner = match.group(1)
        text = inner.strip()
        try:
            url = slug_to_url[to_slug(text)]
            return link_template.format(url=url, text=text)
        except KeyError:
            return nolink_template.format(text=text)

    def render_doc(doc):
        """
        Render a doc's wikilinks to HTML links.

        If a `[[wikilink]]` exists in the index, it will be rendered as an
        HTML link. However, if it doesn't exist, it will be rendered
        using `nolink_template`.
        """
        content = re.sub(
            WIKILINK,
            render_inner_match,
            doc.content
        )
        return replace(doc, content=content)

    return render_doc


def strip_doc_wikilinks(doc):
    """
    Strip wikilinks from doc content field.
    Useful for making stubs with a clean summary.
    """
    content = re.sub(WIKILINK, r'\1', doc.content)
    return replace(doc, content=content)


def uplift_wikilinks(doc):
    """
    Find all wikilinks in doc and assign them to a wikilinks property of doc.
    """
    matches = re.finditer(WIKILINK, doc.content)
    wikilinks = (match.group(1) for match in matches)
    slugs = tuple(to_slug(wikilink) for wikilink in wikilinks)
    return Doc.replace_meta(doc, wikilinks=slugs)


def index_links(stubs):
    """
    Index all link in an iterable of stubs. This assumes you have
    already uplifted wikilinks from content with `uplift_wikilinks`.
    """
    # Create an index of `slug: [slugs]`
    wikilink_index = {
        to_slug(stub.title): stub
        for stub in stubs
        if "wikilinks" in stub.meta
    }
    link_index = {}
    for stub in wikilink_index.values():
        if stub.id_path not in link_index:
            link_index[stub.id_path] = []
        for slug in frozenset(stub.meta["wikilinks"]):
            try:
                link_index[stub.id_path].append(wikilink_index[slug])
            except KeyError:
                pass
    return link_index


def index_backlinks(stubs):
    """
    Index all backlinks in an iterable of docs. This assumes you have
    already uplifted wikilinks from content with `uplift_wikilinks`.
    """
    # Create an index of `slug: [slugs]`
    wikilink_index = {
        to_slug(stub.title): stub
        for stub in stubs
        if "wikilinks" in stub.meta
    }
    backlink_index = {}
    for stub in wikilink_index.values():
        for slug in frozenset(stub.meta["wikilinks"]):
            try:
                to_path = wikilink_index[slug].id_path
                if to_path not in backlink_index:
                    backlink_index[to_path] = []
                backlink_index[to_path].append(stub)
            except KeyError:
                pass
    return backlink_index