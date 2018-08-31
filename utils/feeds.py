import feedparser
import xlwt
import logging

logging.basicConfig(format="%(message)s")
log = logging.getLogger()
log.setLevel(logging.INFO)

COUNTRY_COL = 0
TOPLEVEL_FEED_TITLE_COL = 1
TOPLEVEL_FEED_LINK_COL = 2
DATASET_FEED_TITLE_COL = 3
DATASET_FEED_LINK_COL = 4
DATASET_TITLE_COL = 5
DATASET_LINK_COL = 6

FEED_URLS = (
    "https://gis.tirol.gv.at/inspire/downloadservice/DownloadServiceFeed.xml",
    "http://vogis.cnv.at/inspire-download/natura_2000_epsg_3035_uuid_d18f358a-26fe-4144-8feb-7f805485f90a_atom.xml",
    "http://geoservices.wallonie.be/inspire/atom/PS_Service.xml",
    "http://wwwd3.ymparisto.fi/d3/INSPIREAtom/PS_natura2000.xml",
    "https://geodata.nationaalgeoregister.nl/natura2000/atom/natura2000.xml",
    "https://www.mapama.gob.es/ide/inspire/atom/CategBiodiversidad/downloadservice.xml",
)


def parse_feed(url, sheet, last_row, top_level=True):
    fd = feedparser.parse(url)
    row = last_row + 1
    log.info(f"Feed: {fd.feed.title} ({url})")
    if top_level:
        sheet.write(row, TOPLEVEL_FEED_TITLE_COL, fd.feed.title)
        sheet.write(row, TOPLEVEL_FEED_LINK_COL, url)
    else:
        sheet.write(row, DATASET_FEED_TITLE_COL, fd.feed.title)
        sheet.write(row, DATASET_FEED_LINK_COL, url)
    for e in fd.entries:
        log.info(f"-> Entry: {e.title}")
        for l in [l for l in e.links if l.rel == "alternate" and l.type != "text/html"]:
            log.info(f"   -> Link {l.href}")
            if l.href.endswith(".xml"):
                row = parse_feed(l.href, sheet, row, False)
            else:
                row += 1
                sheet.write(row, DATASET_TITLE_COL, e.title)
                sheet.write(row, DATASET_LINK_COL, l.href)

    return row


def prep_workbook():
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("INSPIRE Atom Feeds")
    sheet.write_merge(0, 1, COUNTRY_COL, COUNTRY_COL, "Country")
    sheet.write_merge(
        0, 0, TOPLEVEL_FEED_TITLE_COL, TOPLEVEL_FEED_LINK_COL, "Top Level Feed"
    )
    sheet.write(1, TOPLEVEL_FEED_TITLE_COL, "Title")
    sheet.write(1, TOPLEVEL_FEED_LINK_COL, "Link")
    sheet.write_merge(
        0, 0, DATASET_FEED_TITLE_COL, DATASET_FEED_LINK_COL, "Dataset Feed"
    )
    sheet.write(1, DATASET_FEED_TITLE_COL, "Title")
    sheet.write(1, DATASET_FEED_LINK_COL, "Link")
    sheet.write_merge(0, 0, DATASET_TITLE_COL, DATASET_LINK_COL, "Dataset")
    sheet.write(1, DATASET_TITLE_COL, "Title")
    sheet.write(1, DATASET_LINK_COL, "Link")
    return book, sheet, 1  # last written row


if __name__ == "__main__":
    book, sheet, last_row = prep_workbook()
    for url in FEED_URLS:
        last_row = parse_feed(
            url, sheet, last_row
    )
    book.save("inspire_atom_feeds.xls")
