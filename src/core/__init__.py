"""通用工具模块"""
from .network_capture import network_capture
from .screenshot import ScreenshotHelper
from .selector import SelectorHelper
from .visual_validator import VisualValidator
from .allure_attachment import attach_json,attach_file,attach_image,attach_jpg,attach_png,attach_text,attach_xml

__all__ = [
    "network_capture",
    'ScreenshotHelper',
    'SelectorHelper',
    'VisualValidator',
    'attach_json','attach_file','attach_image','attach_jpg','attach_png','attach_text','attach_xml'
]