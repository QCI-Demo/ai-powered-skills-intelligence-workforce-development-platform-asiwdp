"""v2 controller exports."""

from asiwdp_integration_api.controllers.v2.content import ContentV2Controller
from asiwdp_integration_api.controllers.v2.hris import HrisV2Controller
from asiwdp_integration_api.controllers.v2.lms import LmsV2Controller

__all__ = [
    "ContentV2Controller",
    "HrisV2Controller",
    "LmsV2Controller",
]
