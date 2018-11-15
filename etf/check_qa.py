import argparse
from collections import defaultdict
import logging
from lxml import etree


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
PSCI_DESIGNATION = "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/proposedSiteOfCommunityImportance"
PSPA_DESIGNATION = "http://inspire.ec.europa.eu/codelist/Natura2000DesignationValue/proposedSpecialProtectionArea"


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


def process_file(f):
    local_ids = defaultdict(set)
    doc = etree.parse(f)
    root = doc.getroot()
    nsmap = {k: v for k, v in root.nsmap.items() if k}
    doc_sites = doc.xpath("//ps:ProtectedSite", namespaces=nsmap)
    no_spa = True
    no_sci = True

    if not doc_sites:
        return "no_protected_sites"

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
            return "duplicate_local_ids"
            # errors["duplicate_local_ids"][local_id].add(
            #     (f.name, site_id)
            # )
            # errors["duplicate_local_ids"][local_id].update(local_ids[local_id])
            # continue
        else:
            local_ids[local_id].add((f, site_id))

        try:
            designation_scheme_el = site.xpath(
                ".//ps:siteDesignation/ps:DesignationType/ps:designationScheme",
                namespaces=nsmap,
            )[0]
        except IndexError:
            return "non_n2k_designation_scheme"
                # errors["non_n2k_designation_scheme"].add(
                #     (f.name, site_id, None)
                # )
                # continue

        try:
            designation_scheme = designation_scheme_el.attrib[f"{{{nsmap['xlink']}}}href"]
            if designation_scheme != DESIGNATION_SCHEME:
                return "non_n2k_designation_scheme"
                # errors["non_n2k_designation_scheme"].add(
                #     (f.name, site_id, designation_scheme)
                # )
                # continue
        except KeyError:
            raise DesignationSchemeValueError

        try:
            designation_el = site.xpath(
                ".//ps:siteDesignation/ps:DesignationType/ps:designation",
                namespaces=nsmap,
            )[0]
        except IndexError:
            return "non_n2k_designation"
                # errors["non_n2k_designation"].add(
                #     (f.name, site_id, None)
                # )
                # continue

        try:
            designation = designation_el.attrib[f"{{{nsmap['xlink']}}}href"]
            if designation not in DESIGNATIONS:
                return "non_n2k_designation"
                # errors["non_n2k_designation"].add(
                #     (f.name, site_id, designation)
                # )
                # continue
        except KeyError:
            raise DesignationValueError

        if designation == SPA_DESIGNATION:
            no_spa = False
        elif designation == SCI_DESIGNATION:
            no_sci = False

    return " spa_not_found" if no_spa else " " + "sci_not_found" if no_sci else ""


def count_proposed(f):
    pspa = 0
    psci = 0
    doc = etree.parse(f)
    root = doc.getroot()
    nsmap = {k: v for k, v in root.nsmap.items() if k}
    doc_sites = doc.xpath("//ps:ProtectedSite", namespaces=nsmap)
    for site in doc_sites:

        try:
            designation_el = site.xpath(
                ".//ps:siteDesignation/ps:DesignationType/ps:designation",
                namespaces=nsmap,
            )[0]
        except IndexError:
            continue

        try:
            designation = designation_el.attrib[f"{{{nsmap['xlink']}}}href"]
            if designation == PSPA_DESIGNATION:
                pspa += 1
            elif designation == PSCI_DESIGNATION:
                psci += 1

        except KeyError:
            continue

    return [pspa, psci]

#
# def main():
#     logging.basicConfig()
#     log = logging.getLogger()
#     log.setLevel(logging.INFO)
#     parser = argparse.ArgumentParser()
#     parser.add_argument("files", type=argparse.FileType("r"), nargs="+")
#     args = parser.parse_args()
#
#
#
#
#
#     try:
#         for f in args.files:
#             log.info(f"Processing {f.name}")
#
#
#     except Exception as err:
#         log.exception(err)
#
#     serializable_errors = make_serializable(errors)

#
# if __name__ == "__main__":
# main()