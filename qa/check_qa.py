import argparse
from collections import defaultdict
import logging
from json import dumps
from lxml import etree
from pprint import pprint


DESIGNATION_SCHEME = "http://inspire.ec.europa.eu/codelist/DesignationSchemeValue/natura2000"

DESIGNATIONS = (
    "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/proposedSiteOfCommunityImportance",
    "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/proposedSpecialProtectionArea",
    "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/siteOfCommunityImportance",
    "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/specialAreaOfConservation",
    "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/specialProtectionArea",
)

SPA_DESIGNATION = "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/specialProtectionArea"
SCI_DESIGNATION = "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/siteOfCommunityImportance"


class LocalIdNotFound(Exception):
    pass


class DesignationValueError(Exception):
    pass


class DesignationSchemeValueError(Exception):
    pass


def make_serializable(data):
    serializable_data = {}
    for k, v in data.items():
        if isinstance(v, set):
            serializable_data[k] = list(v)
        elif isinstance(v, defaultdict):
            serializable_data[k] = make_serializable(dict(v))
        else:
            serializable_data[k] = v
    return serializable_data


def main():
    logging.basicConfig()
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("files", type=argparse.FileType("r"), nargs="+")
    args = parser.parse_args()

    errors = {
        "no_protected_sites": set(),
        "spa_not_found": True,
        "sci_not_found": True,
        "duplicate_local_ids": defaultdict(set),
        "non_n2k_designation_scheme": set(),
        "non_n2k_designation": set(),
    }

    local_ids = defaultdict(set)

    try:
        for f in args.files:
            log.info(f"Processing {f.name}")
            doc = etree.parse(f)
            root = doc.getroot()
            nsmap = {k: v for k, v in root.nsmap.items() if k}
            doc_sites = doc.xpath("//ps:ProtectedSite", namespaces=nsmap)
            if not doc_sites:
                errors["no_protected_sites"].add(f.name)
                continue

            for site in doc_sites:
                site_id = site.attrib[f"{{{nsmap['gml']}}}id"]

                try:
                    local_id_el = site.xpath(
                        ".//ps:inspireID/base:Identifier/base:localId", namespaces=nsmap
                    )[0]
                except IndexError:
                    raise LocalIdNotFound

                local_id = local_id_el.text
                if local_id in local_ids:                    
                    errors["duplicate_local_ids"][local_id].add(
                        (f.name, site_id)
                    )
                    errors["duplicate_local_ids"][local_id].update(local_ids[local_id])
                    continue
                else:
                    local_ids[local_id].add((f.name, site_id))

                try:
                    designation_scheme_el = site.xpath(
                        ".//ps:siteDesignation/ps:DesignationType/ps:designationScheme",
                        namespaces=nsmap,
                    )[0]
                except IndexError:
                        errors["non_n2k_designation_scheme"].add(
                            (f.name, site_id, None)
                        )
                        continue

                try:
                    designation_scheme = designation_scheme_el.attrib[
                        f"{{{nsmap['xlink']}}}href"
                    ]
                    if designation_scheme != DESIGNATION_SCHEME:
                        errors["non_n2k_designation_scheme"].add(
                            (f.name, site_id, designation_scheme)
                        )
                        continue
                except KeyError:
                    raise DesignationSchemeValueError

                try:
                    designation_el = site.xpath(
                        ".//ps:siteDesignation/ps:DesignationType/ps:designation",
                        namespaces=nsmap,
                    )[0]
                except IndexError:
                        errors["non_n2k_designation"].add(
                            (f.name, site_id, None)
                        )
                        continue

                try:
                    designation = designation_el.attrib[f"{{{nsmap['xlink']}}}href"]
                    if designation not in DESIGNATIONS:
                        errors["non_n2k_designation"].add(
                            (f.name, site_id, designation)
                        )
                        continue
                except KeyError:
                    raise DesignationValueError

                if designation == SPA_DESIGNATION:
                    errors.pop("spa_not_found", None)
                elif designation == SCI_DESIGNATION:
                    errors.pop("sci_not_found", None)

    except Exception as err:
        log.exception(err)

    serializable_errors = make_serializable(errors)

    with open("qa.json", "w") as f:
        f.write(dumps(serializable_errors))


if __name__ == "__main__":
    main()
