from django.utils.dateparse import parse_date


class ReportFilterEngine:
    FILTER_MAP = {
        "date_from": "__gte",
        "date_to": "__lte",
        "tenant": "",
        "branch": "",
        "role": "",
        "warehouse": "",
        "product": "",
        "gst": "",
        "status": "",
        "q": "__icontains",
    }

    def normalize(self, raw_filters):
        filters = {}
        for key, value in (raw_filters or {}).items():
            if value in (None, ""):
                continue
            if key in {"date_from", "date_to"}:
                parsed = parse_date(str(value))
                if parsed:
                    filters[key] = parsed.isoformat()
            else:
                filters[key] = value
        return filters

    def apply(self, qs, template, filters):
        spec = template.query_spec or {}
        field_map = spec.get("filter_fields", {})
        for key, value in filters.items():
            field = field_map.get(key)
            if not field:
                continue
            lookup = ""
            if key == "date_from":
                lookup = "__gte"
            elif key == "date_to":
                lookup = "__lte"
            elif key == "q":
                lookup = "__icontains"
            qs = qs.filter(**{f"{field}{lookup}": value})
        return qs

