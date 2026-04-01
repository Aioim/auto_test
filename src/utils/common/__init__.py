"""通用工具模块"""

from .screenshot_helper import ScreenshotHelper
from .selector_helper import SelectorHelper
from .visual_validator import VisualValidator
from .log_monitor import RealtimeLogMonitor
from .allure_attachment import attach_text,attach_image,attach_file,attach_jpg,attach_png,attach_json,attach_xml

__all__ = [
    'ScreenshotHelper',
    'SelectorHelper',
    'VisualValidator',
    'RealtimeLogMonitor',
    'attach_text',
    'attach_image',
    'attach_file',
    'attach_jpg',
    'attach_png',
    'attach_json',
    'attach_xml'
]
