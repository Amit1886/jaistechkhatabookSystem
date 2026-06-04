class DynamicFieldMeta {
  final String name;
  final String label;
  final String widget;
  final bool required;
  final bool readOnly;
  final String? relation;
  final List<dynamic> choices;

  DynamicFieldMeta({
    required this.name,
    required this.label,
    required this.widget,
    required this.required,
    required this.readOnly,
    required this.choices,
    this.relation,
  });

  factory DynamicFieldMeta.fromJson(Map<String, dynamic> json) {
    return DynamicFieldMeta(
      name: json['name']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      widget: json['widget']?.toString() ?? 'text',
      required: json['required'] == true,
      readOnly: json['read_only'] == true,
      relation: json['relation']?.toString(),
      choices: (json['choices'] as List?) ?? const [],
    );
  }
}

class DynamicScreenMeta {
  final String key;
  final String model;
  final String title;
  final String listEndpoint;
  final String formEndpoint;
  final List<String> columns;
  final List<DynamicFieldMeta> fields;

  DynamicScreenMeta({
    required this.key,
    required this.model,
    required this.title,
    required this.listEndpoint,
    required this.formEndpoint,
    required this.columns,
    required this.fields,
  });

  factory DynamicScreenMeta.fromJson(Map<String, dynamic> json) {
    final list = (json['list'] as Map?)?.cast<String, dynamic>() ?? {};
    final form = (json['form'] as Map?)?.cast<String, dynamic>() ?? {};
    return DynamicScreenMeta(
      key: json['key']?.toString() ?? '',
      model: json['model']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      listEndpoint: list['endpoint']?.toString() ?? '',
      formEndpoint: form['endpoint']?.toString() ?? '',
      columns: ((list['columns'] as List?) ?? const []).map((e) => e.toString()).toList(),
      fields: ((form['fields'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => DynamicFieldMeta.fromJson(e.cast<String, dynamic>()))
          .toList(),
    );
  }
}
