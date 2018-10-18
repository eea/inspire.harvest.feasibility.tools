from urllib.parse import urlparse, urlunparse, urlencode

import logme
from lxml import etree
import requests

from qa.common import check, check_list_errors


log = logme.log(scope="module", name="inspire_qa")


PRIORITY_DS_THESAURUS_NAME = "INSPIRE priority data set"
PRIORITY_DS_THESAURUS_LINK = (
    "http://inspire.ec.europa.eu/metadata-codelist/PriorityDataset"
)

N2K_DATASETS = {
    "Natura 2000 sites (Birds Directive)": "http://inspire.ec.europa.eu/metadata-codelist/PriorityDataset/Natura2000Sites-dir-2009-147",
    "Natura 2000 sites (Habitats Directive)": "http://inspire.ec.europa.eu/metadata-codelist/PriorityDataset/Natura2000Sites-dir-1992-43",
}


WFS_PROTO = "OGC:WFS"
ATOM_PROTO = "OGC:Atom"

SUPPORTED_DL_SERVICES = (
    WFS_PROTO,
    # TODO: Atom support
)

OGC_PROTOCOLS = (WFS_PROTO, ATOM_PROTO)

N2K_QUERY_ID = "http://inspire.ec.europa.eu/operation/download/GetNatura2000"

DEFAULT_TIMEOUT = 30


@check("Natura 2000 priority dataset keywords", log)
def check_n2k_keywords(tree, keywords=None, nsmap=None):
    nsmap = nsmap or tree.getroot().nsmap
    keywords = keywords or N2K_DATASETS
    reversed_keywords = {v: k for k, v in keywords.items()}

    try:
        keyword_els = tree.xpath(
            "//gmd:identificationInfo/gmd:MD_DataIdentification/gmd:descriptiveKeywords/gmd:MD_Keywords/gmd:keyword",
            namespaces=nsmap,
        )
    except (etree.XPathEvalError, TypeError):
        keyword_els = []

    found = {k: False for k in keywords.keys()}

    for kw in keyword_els:
        try:
            string_el = kw.find("gco:CharacterString", namespaces=nsmap)

            if string_el is not None and string_el.text in keywords.keys():
                found[string_el.text] = True
        except SyntaxError:
            pass

    if all(found.values()):
        return True

    if any(found.values()):
        log.info(
            "Natura 2000 priority dataset keywords as strings partially found, also looking for anchors."
        )
    else:
        log.info(
            "Natura 2000 priority dataset keywords as strings not found, looking for anchors."
        )

    for kw in keyword_els:
        try:
            anchor_el = kw.find("gmx:Anchor", namespaces=nsmap)
        except SyntaxError:  # handle missing gmx namespace
            anchor_el = None

        if anchor_el is not None and anchor_el.attrib[f"{{{nsmap['xlink']}}}href"] in keywords.values():
            found[reversed_keywords[anchor_el.text]] = True

    if all(found.values()):
        return True

    return False


@check("INSPIRE Priority Dataset thesaurus reference", log)
def check_priority_ds_thesaurus(tree, nsmap=None):
    nsmap = nsmap or tree.getroot().nsmap
    try:
        thesaurus_names = tree.xpath(
            "//gmd:descriptiveKeywords/gmd:MD_Keywords/gmd:thesaurusName/gmd:CI_Citation/gmd:title/gco:CharacterString",
            namespaces=nsmap,
        )
    except (etree.XPathEvalError, TypeError):
        thesaurus_names = []

    try:
        thesaurus_anchors = tree.xpath(
            "//gmd:descriptiveKeywords/gmd:MD_Keywords/gmd:thesaurusName/gmd:CI_Citation/gmd:title/gmx:Anchor",
            namespaces=nsmap,
        )
    except (etree.XPathEvalError, TypeError, SyntaxError):
        thesaurus_anchors = []

    for name in thesaurus_names:
        if name.text == PRIORITY_DS_THESAURUS_NAME:
            return True

    log.info(
        "INSPIRE Priority dataset thesaurus reference as string not found, looking for anchor."
    )

    for anchor in thesaurus_anchors:
        if anchor.attrib[f"{{{nsmap['xlink']}}}href"] == PRIORITY_DS_THESAURUS_LINK:
            return True

    return False


@check_list_errors("Online resource protocols & linkage", log)
def get_online_resources(tree, valid_protocols=OGC_PROTOCOLS, nsmap=None):
    nsmap = nsmap or tree.getroot().nsmap
    urls = {p: None for p in valid_protocols}
    online_resources = tree.xpath(
        "//gmd:transferOptions/gmd:MD_DigitalTransferOptions/gmd:onLine/gmd:CI_OnlineResource",
        namespaces=nsmap,
    )

    errors = []

    for res in online_resources:
        try:
            proto = res.xpath("gmd:protocol/gco:CharacterString", namespaces=nsmap)[
                0
            ].text
        except IndexError:
            continue

        if proto in valid_protocols:
            try:
                url = res.xpath("gmd:linkage/gmd:URL", namespaces=nsmap)[0].text
            except IndexError:
                errors.append(f"No linkage for found protocol {proto}")
                continue
            if urls[proto] is not None:
                errors.append(f"Multiple online resources for protocol {proto}")
            urls[proto] = url

    resources = {p: u for p, u in urls.items() if u}
    if not resources:
        errors.append(f"No online resource found for any of protocols: {OGC_PROTOCOLS}")

    return resources, errors


@check("Supported Download Service protocol", log)
def check_supported_protocols(protocols):
    return any([p in SUPPORTED_DL_SERVICES for p in protocols])


@check_list_errors("ListStoredQueries operation support", log)
def check_list_stored_queries_support(url, timeout=DEFAULT_TIMEOUT):
    link = None
    errors = []
    try:
        with requests.get(url, timeout=timeout, stream=True, allow_redirects=True) as r:
            response = r.content

        tree = etree.fromstring(response)
        nsmap = tree.nsmap  # this is an element, no getroot() needed/supported
        try:
            lsq_op = [
                op
                for op in tree.findall(
                    "ows:OperationsMetadata/ows:Operation", namespaces=nsmap
                )
                if op.attrib["name"] == "ListStoredQueries"
            ][0]
        except IndexError:
            return None, ["ListStoredQueries not supported"]

        link_el = lsq_op.find("ows:DCP/ows:HTTP/ows:Get", namespaces=nsmap)
        if link_el is None:
            return None, ["ListStoredQueries GET link not found"]

        link = link_el.attrib[f"{{{nsmap['xlink']}}}href"]

    except requests.exceptions.Timeout:
        errors.append("Timed out getting stored queries list")
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    ):
        errors.append("Connection error getting stored queries list")

    return link, errors


def get_stored_queries(base_url, timeout=DEFAULT_TIMEOUT):
    url = base_url + "?service=WFS&version=2.0.0&request=ListStoredQueries"
    errors = []
    query_ids = []
    try:
        log.info(f"Getting Stored Queries list from {url}")
        with requests.get(url, timeout=timeout, stream=True, allow_redirects=True) as r:
            response = r.content

        tree = etree.fromstring(response)
        nsmap = tree.nsmap  # this is an element, no getroot() needed/supported
        queries = tree.findall("wfs:StoredQuery", namespaces=nsmap)
        query_ids = [el.attrib["id"] for el in queries]
    except requests.exceptions.Timeout:
        errors.append("Timed out getting stored queries list")
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    ):
        errors.append("Connection error getting stored queries list")

    return query_ids, errors


@check_list_errors("Natura 2000 Stored Query Id exists", log)
def check_n2k_stored_query_exists(url):
    stored_query_ids, errors = get_stored_queries(url)
    found = N2K_QUERY_ID in stored_query_ids
    return found, errors


@check_list_errors("Spatial data download", log)
def get_n2k_spatial_data(country_code, url, timeout=DEFAULT_TIMEOUT, path=None):
    parts = urlparse(url)
    stored_query_param = urlencode({"storedqueryID": N2K_QUERY_ID})
    query = f"service=WFS&version=2.0.0&request=GetFeature&{stored_query_param}"
    n2k_url = urlunparse(
        [parts.scheme, parts.netloc, parts.path, parts.params, query, None]
    )
    errors = []
    path = path or f"{country_code}_N2K.gml"
    try:
        with requests.get(
            n2k_url, timeout=timeout, stream=True, allow_redirects=True
        ) as response:
            with open(path, "wb") as f:
                f.write(response.content)

    except requests.exceptions.Timeout:
        errors.append("Timed out getting stored queries list")
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    ):
        errors.append("Connection error getting stored queries list")

    return path, errors
