"""
Agent Tools and Registry for Voice Dialogue Agent.
"""
from __future__ import annotations
import json
from typing import Dict, Any, Callable


class VoiceAgentTool:
    def __init__(self, name: str, description: str, func: Callable[..., str], schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.func = func
        self.schema = schema

    def execute(self, **kwargs) -> str:
        try:
            return self.func(**kwargs)
        except Exception as e:
            return f"Error executing {self.name}: {e}"


def get_weather(city: str = "北京") -> str:
    return f"{city}当前天气：晴朗，气温21摄氏度，北风2级，空气质量优，非常适合外出活动。"


def check_calendar(date: str = "今天") -> str:
    return f"{date}下午3:00在第二会议室有“全双工语音系统架构评审会”；下午5:00有代码提交评审。"


def control_smart_device(device: str, action: str) -> str:
    return f"已成功执行：将{device}设置为{action}状态。"


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, VoiceAgentTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        self.tools["get_weather"] = VoiceAgentTool(
            name="get_weather",
            description="查询指定城市的天气状况与气温",
            func=get_weather,
            schema={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
        )
        self.tools["check_calendar"] = VoiceAgentTool(
            name="check_calendar",
            description="查询用户的日程安排与会议清单",
            func=check_calendar,
            schema={"type": "object", "properties": {"date": {"type": "string"}}},
        )
        self.tools["control_smart_device"] = VoiceAgentTool(
            name="control_smart_device",
            description="控制智能家居与办公设备开关",
            func=control_smart_device,
            schema={"type": "object", "properties": {"device": {"type": "string"}, "action": {"type": "string"}}, "required": ["device", "action"]},
        )

    def dispatch(self, tool_name: str, **kwargs) -> str:
        tool = self.tools.get(tool_name)
        if not tool:
            return f"Tool '{tool_name}' not found."
        return tool.execute(**kwargs)
