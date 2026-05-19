import defusedxml.ElementTree as ET
def parse_xml(xml_bytes):
    tree = ET.fromstring(xml_bytes)
    return tree.find("item").text
