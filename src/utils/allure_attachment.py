import json
import os
from functools import wraps
from typing import Any, Optional, Union
from xml.etree import ElementTree as ET

import allure


class AllureAttachment:
    """
    Allure attachment wrapper, providing unified methods for adding attachments.
    Supports: plain text, JSON, XML, files, images.
    """

    # Extension to Allure attachment type mapping
    EXT_TO_TYPE = {
        ".txt": allure.attachment_type.TEXT,
        ".log": allure.attachment_type.TEXT,
        ".json": allure.attachment_type.JSON,
        ".xml": allure.attachment_type.XML,
        ".html": allure.attachment_type.HTML,
        ".htm": allure.attachment_type.HTML,
        ".csv": allure.attachment_type.CSV,
        ".png": allure.attachment_type.PNG,
        ".jpg": allure.attachment_type.JPG,
        ".gif": allure.attachment_type.GIF,
        ".bmp": allure.attachment_type.BMP,
        ".pdf": allure.attachment_type.PDF,
        ".mp4": allure.attachment_type.MP4,
        ".webm": allure.attachment_type.WEBM,
    }

    # Image type to Allure attachment type mapping
    IMG_TYPE_TO_TYPE = {
        "png": allure.attachment_type.PNG,
        "jpg": allure.attachment_type.JPG,
        "gif": allure.attachment_type.GIF,
        "bmp": allure.attachment_type.BMP,
    }

    @staticmethod
    def _attach_error(error_msg: str, name: str) -> None:
        """Unified error attachment"""
        allure.attach(f"Attachment failed: {error_msg}", name=f"{name}_error", attachment_type=allure.attachment_type.TEXT)

    @staticmethod
    def text(content: str, name: str = "Text") -> None:
        """
        Attach plain text.

        :param content: Text content
        :param name: Attachment display name
        """
        try:
            allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)
        except Exception as e:
            AllureAttachment._attach_error(str(e), name)

    @staticmethod
    def json(data: Any, name: str = "JSON", indent: int = 2, ensure_ascii: bool = False) -> None:
        """
        Attach JSON data. If data is a string, it is attached as-is (assumed valid JSON).
        Otherwise, the data is serialized with formatting.

        :param data: Python object or JSON string
        :param name: Attachment display name
        :param indent: JSON indentation spaces
        :param ensure_ascii: Whether to escape non-ASCII characters
        """
        try:
            if isinstance(data, str):
                # Assume it's already a valid JSON string, attach directly
                json_str = data
            else:
                json_str = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
            allure.attach(json_str, name=name, attachment_type=allure.attachment_type.JSON)
        except Exception as e:
            AllureAttachment._attach_error(f"JSON serialization failed: {e}", name)

    @staticmethod
    def xml(xml_data: Union[str, bytes, ET.Element], name: str = "XML", pretty_print: bool = True) -> None:
        """
        Attach XML data with optional pretty-printing.

        :param xml_data: XML string, bytes, or ElementTree Element
        :param name: Attachment display name
        :param pretty_print: Whether to format output (add indentation)
        """
        try:
            if isinstance(xml_data, ET.Element):
                # Use ElementTree's built-in pretty-print if available (Python 3.9+)
                if pretty_print:
                    ET.indent(xml_data, space="  ")
                xml_str = ET.tostring(xml_data, encoding="unicode")
            elif isinstance(xml_data, bytes):
                xml_str = xml_data.decode("utf-8")
            else:
                xml_str = str(xml_data)

            # Fallback pretty-print using minidom for strings when ElementTree.indent not used
            if pretty_print and not isinstance(xml_data, ET.Element):
                try:
                    import xml.dom.minidom
                    dom = xml.dom.minidom.parseString(xml_str)
                    xml_str = dom.toprettyxml(indent="  ")
                    # Remove extra blank lines after XML declaration
                    lines = xml_str.splitlines()
                    if lines and lines[0].startswith("<?xml"):
                        xml_str = "\n".join(lines)
                except Exception:
                    pass  # Keep original if formatting fails

            allure.attach(xml_str, name=name, attachment_type=allure.attachment_type.XML)
        except Exception as e:
            AllureAttachment._attach_error(f"XML attachment failed: {e}", name)

    @staticmethod
    def file(file_path: str, name: Optional[str] = None, attachment_type: Optional[allure.attachment_type] = None) -> None:
        """
        Attach a file. Type is auto-detected from extension if not provided.

        :param file_path: Path to the file
        :param name: Display name (default: basename of file)
        :param attachment_type: Explicit attachment type (overrides auto-detection)
        """
        if not os.path.exists(file_path):
            AllureAttachment._attach_error(f"File not found: {file_path}", name or "file")
            return

        try:
            with open(file_path, "rb") as f:
                file_data = f.read()

            display_name = name if name is not None else os.path.basename(file_path)

            if attachment_type is None:
                ext = os.path.splitext(file_path)[1].lower()
                attachment_type = AllureAttachment.EXT_TO_TYPE.get(ext, allure.attachment_type.TEXT)

            allure.attach(file_data, name=display_name, attachment_type=attachment_type)
        except Exception as e:
            AllureAttachment._attach_error(f"Failed to read file: {e}\nPath: {file_path}", name or "file")

    @staticmethod
    def image(data: Union[bytes, str], name: str = "Image", img_type: str = "png") -> None:
        """
        Attach an image. Supports raw bytes or file path.

        :param data: Image bytes or path to image file
        :param name: Display name
        :param img_type: Image type (png, jpg, jpeg, gif, bmp)
        """
        try:
            if isinstance(data, str):
                if not os.path.exists(data):
                    raise FileNotFoundError(f"Image file not found: {data}")
                with open(data, "rb") as f:
                    img_bytes = f.read()
            else:
                img_bytes = data

            attach_type = AllureAttachment.IMG_TYPE_TO_TYPE.get(img_type.lower(), allure.attachment_type.PNG)
            allure.attach(img_bytes, name=name, attachment_type=attach_type)
        except Exception as e:
            AllureAttachment._attach_error(f"Image attachment failed: {e}", name)

    # Convenience methods
    @staticmethod
    def png(data: Union[bytes, str], name: str = "Screenshot") -> None:
        """Attach a PNG image."""
        AllureAttachment.image(data, name=name, img_type="png")

    @staticmethod
    def jpg(data: Union[bytes, str], name: str = "Image") -> None:
        """Attach a JPG/JPEG image."""
        AllureAttachment.image(data, name=name, img_type="jpg")


# Public functions for convenient use
def attach_text(content: str, name: str = "Text") -> None:
    AllureAttachment.text(content, name)


def attach_json(data: Any, name: str = "JSON", indent: int = 2, ensure_ascii: bool = False) -> None:
    AllureAttachment.json(data, name, indent, ensure_ascii)


def attach_xml(xml_data: Union[str, bytes, ET.Element], name: str = "XML", pretty_print: bool = True) -> None:
    AllureAttachment.xml(xml_data, name, pretty_print)


def attach_file(file_path: str, name: Optional[str] = None) -> None:
    AllureAttachment.file(file_path, name)


def attach_image(data: Union[bytes, str], name: str = "Image", img_type: str = "png") -> None:
    AllureAttachment.image(data, name, img_type)


def attach_png(data: Union[bytes, str], name: str = "Screenshot") -> None:
    AllureAttachment.png(data, name)


def attach_jpg(data: Union[bytes, str], name: str = "Image") -> None:
    AllureAttachment.jpg(data, name)