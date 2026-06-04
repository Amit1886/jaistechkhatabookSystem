class AppUser {
  final String id;
  final String email;
  final String name;
  final String passwordHash;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;

  AppUser({
    required this.id,
    required this.email,
    required this.name,
    required this.passwordHash,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'email': email,
        'name': name,
        'password_hash': passwordHash,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'is_synced': isSynced ? 1 : 0,
      };

  static AppUser fromMap(Map<String, Object?> map) => AppUser(
        id: map['id'] as String,
        email: map['email'] as String,
        name: map['name'] as String,
        passwordHash: map['password_hash'] as String,
        createdAt: DateTime.parse(map['created_at'] as String),
        updatedAt: DateTime.parse(map['updated_at'] as String),
        isSynced: (map['is_synced'] as int) == 1,
      );
}

