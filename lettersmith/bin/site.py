#!/usr/bin/env python3
import tempfile
from datetime import datetime
from pathlib import PurePath, Path
from itertools import chain
from subprocess import CalledProcessError

from lettersmith.util import get_deep
from lettersmith.argparser import lettersmith_argparser
from lettersmith import path as pathtools
from lettersmith import docs as Docs
from lettersmith import doc as Doc
from lettersmith import stub as Stub
from lettersmith import markdowntools
from lettersmith import wikilink
from lettersmith import absolutize
from lettersmith.permalink import map_permalink
from lettersmith import templatetools
from lettersmith import paging
from lettersmith import taxonomy
from lettersmith import jinjatools
from lettersmith import rss
from lettersmith import sitemap
from lettersmith.data import load_data_files
from lettersmith.file import copy_all

def main():
    parser = lettersmith_argparser(
        description="""Generates a blog-aware site with Lettersmith""")
    args = parser.parse_args()
    config = args.config
    input_path = Path(config.get("input_path", "content"))
    output_path = config.get("output_path", "public")
    theme_path = config.get("theme_path", "theme")
    base_url = config.get("base_url", "/")
    build_drafts = config.get("build_drafts", False)
    data_path = config.get("data_path", "data")
    static_paths = config.get("static_paths", [])
    permalink_templates = config.get("permalink_templates", {})
    taxonomies = config.get("taxonomies", [])
    site_title = get_deep(config, ("site", "title"), "Untitled")
    site_description = get_deep(config, ("site", "description"), "")
    site_author = get_deep(config, ("site", "author"), "")
    now = datetime.now()

    data = load_data_files(data_path)

    paths = (
        x for x in input_path.glob("**/*.md")
        if pathtools.should_pub(x, build_drafts)
    )

    # Filter out special files
    paths = (x for x in paths if pathtools.is_doc_file(x))

    docs = (Doc.load(path, relative_to=input_path) for path in paths)

    docs = (wikilink.uplift_wikilinks(doc) for doc in docs)
    # Render markdown in docs so that stub will correctly strip
    # HTML for summaries.
    docs = markdowntools.map_markdown(docs)

    stubs = tuple(Doc.to_stub(doc) for doc in docs)

    # Collect stubs into index. We'll use this for cross-referencing
    # stubs, and also as an index accessible in templates.
    index = {stub.id_path: stub for stub in stubs}

    wikilink_index = wikilink.index_wikilinks(stubs, base_url=base_url)
    backlink_index = wikilink.index_backlinks(stubs)
    taxonomy_index = taxonomy.index_by_taxonomy(stubs, taxonomies)

    paging_docs = paging.gen_paging(
        stubs,
        templates=get_deep(config, ("paging", "templates")),
        output_path_template=get_deep(config, ("paging", "output_path_template")),
        per_page=get_deep(config, ("paging", "per_page"))
    )

    most_recent_stubs = rss.most_recent_n(
        stubs,
        nitems=get_deep(config, ("rss", "nitems"), 24)
    )

    rss_doc = rss.gen_rss(most_recent_stubs, "rss.xml",
        base_url=base_url,
        last_build_date=now,
        title=site_title,
        description=site_description,
        author=site_author,
        read_more=get_deep(config, "rss", "read_more")
    )

    sitemap_doc = sitemap.gen_sitemap(stubs, base_url=base_url)

    # Reload docs
    docs = (
        Stub.load_doc(stub, relative_to=input_path)
        for stub in stubs
    )

    docs = markdowntools.map_markdown(docs)
    docs = absolutize.map_absolutize(docs, base_url=base_url)
    docs = (Doc.change_ext(doc, ".html") for doc in docs)
    docs = templatetools.map_templates(docs)
    docs = map_permalink(docs, permalink_templates)
    docs = wikilink.map_wikilinks(docs, wikilink_index)
    docs = chain(docs, paging_docs, (rss_doc, sitemap_doc))

    # Set up template globals
    context = {
        "rss_docs": (rss_doc,),
        "index": index,
        "taxonomy_index": taxonomy_index,
        "backlink_index": backlink_index,
        "wikilink_index": wikilink_index,
        "site": config.get("site", {}),
        "data": data,
        "base_url": base_url,
        "now": now
    }

    docs = jinjatools.map_jinja(docs, context=context, theme_path=theme_path)

    stats = Docs.write(docs, output_path=output_path)

    try:
        static_paths = config.get("static_paths", [])
        static_paths.append(PurePath(theme_path, "static"))
        copy_all(static_paths, output_path)
    except CalledProcessError:
        pass

    print('Done! Generated {sum} files in "{output_path}"'.format(
        output_path=output_path,
        sum=stats["written"]
    ))


if __name__ == "__main__":
    main()