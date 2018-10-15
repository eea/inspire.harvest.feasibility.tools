from urllib.parse import urlparse, urlunparse, urlencode

import logme
from lxml import etree
import requests

from qa.common import check, check_list_errors


log = logme.log(scope='module', name='inspire_qa')


N2K_DATASET_LABELS = (
    "Natura 2000 sites (Birds Directive)",
    "Natura 2000 sites (Habitats Directive)",
)


WFS_PROTO = "OGC:WFS"
ATOM_PROTO = "OGC:Atom"

SUPPORTED_DL_SERVICES = (
    WFS_PROTO,
)

OGC_PROTOCOLS = (
    WFS_PROTO,
    ATOM_PROTO,
)

N2K_QUERY_ID = "http://inspire.ec.europa.eu/operation/download/GetNatura2000"

DEFAULT_TIMEOUT = 30


@check("Natura 2000 priority dataset keywords", log)
def check_n2k_keywords(tree, keywords=N2K_DATASET_LABELS, nsmap=None):
    nsmap = nsmap or tree.getroot().nsmap
    descriptive_kw_sections = tree.xpath(
        "//gmd:identificationInfo/gmd:MD_DataIdentification/gmd:descriptiveKeywords",
        namespaces=nsmap
    )

    found = {k: False for k in keywords}

    for section in descriptive_kw_sections:
        md_keywords = section.findall(
            "gmd:MD_Keywords/gmd:keyword/gco:CharacterString",
            namespaces=nsmap
        )

        for kw in md_keywords:
            if kw.text in keywords:
                found[kw.text] = True

    if all(found.values()):
        return True

    return False


@check_list_errors("Online resource protocols & linkage", log)
def get_online_resources(tree, valid_protocols=OGC_PROTOCOLS, nsmap=None):
    nsmap = nsmap or tree.getroot().nsmap
    urls = {p: None for p in valid_protocols}
    online_resources = tree.xpath(
        "//gmd:transferOptions/gmd:MD_DigitalTransferOptions/gmd:onLine/gmd:CI_OnlineResource",
        namespaces=nsmap
    )

    errors = []

    for res in online_resources:
        try:
            proto = res.xpath("gmd:protocol/gco:CharacterString", namespaces=nsmap)[0].text
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
        with requests.get(
                url, timeout=timeout, stream=True, allow_redirects=True
        ) as r:
            response = r.content

        tree = etree.fromstring(response)
        nsmap = tree.nsmap  # this is an element, no getroot() needed/supported
        try:
            lsq_op = [
                op for op in
                tree.findall("ows:OperationsMetadata/ows:Operation", namespaces=nsmap)
                if op.attrib["name"] == "ListStoredQueries"
            ][0]
        except IndexError:
            return None, ["ListStoredQueries not supported"]

        link_el = lsq_op.find("ows:DCP/ows:HTTP/ows:Get", namespaces=nsmap)
        if link is None:
            return None, ["ListStoredQueries GET link not found"]

        link = link_el.attrib["xlink:href"]

    except requests.exceptions.Timeout:
        errors.append("Timed out getting stored queries list")
    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
        errors.append("Connection error getting stored queries list")

    return link, errors


def get_stored_queries(base_url, timeout=DEFAULT_TIMEOUT):
    url = base_url + "?service=WFS&version=2.0.0&request=ListStoredQueries"
    errors = []
    query_ids = []
    try:
        log.info(f"Getting Stored Queries list from {url}")
        with requests.get(
                url, timeout=timeout, stream=True, allow_redirects=True
        ) as r:
            response = r.content

        tree = etree.fromstring(response)
        nsmap = tree.nsmap  # this is an element, no getroot() needed/supported
        queries = tree.findall("wfs:StoredQuery", namespaces=nsmap)
        query_ids = [el.attrib["id"] for el in queries]
    except requests.exceptions.Timeout:
        errors.append("Timed out getting stored queries list")
    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
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
    n2k_url = urlunparse([parts.scheme, parts.netloc, parts.path, parts.params, query, None])
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
    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
        errors.append("Connection error getting stored queries list")

    return path, errors

