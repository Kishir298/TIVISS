"""Tool abstraction: interface, registry, results, and safe mock tools."""

from .ascs_integration import (
    AscsHandoverTool,
    AscsIntegrationTool,
    AscsStatusTool,
    build_ascs_tools,
    register_ascs_tools,
)
from .calculator_tools import (
    CalculateTool,
    build_calculator_tools,
    register_calculator_tools,
)
from .core_tools import (
    CoreAgentRequestTool,
    CoreDataRequestTool,
    CoreDeviceInfoTool,
    CoreDiscoverDevicesTool,
    CoreSendToDeviceTool,
    CoreServiceRequestTool,
    CoreStatusTool,
    build_core_tools,
    register_core_tools,
)
from .interface import Tool, ToolError, ToolResult, ToolStatus
from .mock_tools import EchoTool, FailingTool, SumTool
from .registry import ToolRegistry, UnknownToolError
from .translation_tools import (
    TranslateTextTool,
    build_translation_tools,
    register_translation_tools,
)
from .voice_tools import (
    VoiceListenTool,
    VoiceSpeakTool,
    VoiceStatusTool,
    build_voice_tools,
    register_voice_tools,
)
from .web_tools import WebFetchTool, WebSearchTool, build_web_tools, register_web_tools

__all__ = [
    "Tool",
    "ToolError",
    "ToolResult",
    "ToolStatus",
    "ToolRegistry",
    "UnknownToolError",
    "EchoTool",
    "SumTool",
    "FailingTool",
    "CalculateTool",
    "build_calculator_tools",
    "register_calculator_tools",
    "WebSearchTool",
    "WebFetchTool",
    "build_web_tools",
    "register_web_tools",
    "TranslateTextTool",
    "build_translation_tools",
    "register_translation_tools",
    "VoiceListenTool",
    "VoiceSpeakTool",
    "VoiceStatusTool",
    "build_voice_tools",
    "register_voice_tools",
    "AscsIntegrationTool",
    "AscsHandoverTool",
    "AscsStatusTool",
    "build_ascs_tools",
    "register_ascs_tools",
    "CoreDiscoverDevicesTool",
    "CoreDeviceInfoTool",
    "CoreStatusTool",
    "CoreServiceRequestTool",
    "CoreAgentRequestTool",
    "CoreDataRequestTool",
    "CoreSendToDeviceTool",
    "build_core_tools",
    "register_core_tools",
]
