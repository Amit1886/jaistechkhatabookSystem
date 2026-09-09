import json


def generate_chart(chart_type: str, data: dict, options: dict) -> dict:
    return {
        "type": chart_type,
        "data": data,
        "options": options,
    }


def render_chart_to_svg(chart_config: dict) -> str:
    return "<svg></svg>"
