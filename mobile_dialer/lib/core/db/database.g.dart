// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'database.dart';

// ignore_for_file: type=lint
class $SyncEventsTable extends SyncEvents
    with TableInfo<$SyncEventsTable, SyncEventRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SyncEventsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _seqMeta = const VerificationMeta('seq');
  @override
  late final GeneratedColumn<int> seq = GeneratedColumn<int>(
    'seq',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _typeMeta = const VerificationMeta('type');
  @override
  late final GeneratedColumn<String> type = GeneratedColumn<String>(
    'type',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _payloadMeta = const VerificationMeta(
    'payload',
  );
  @override
  late final GeneratedColumn<String> payload = GeneratedColumn<String>(
    'payload',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<int> createdAt = GeneratedColumn<int>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [seq, type, payload, createdAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'sync_events';
  @override
  VerificationContext validateIntegrity(
    Insertable<SyncEventRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('seq')) {
      context.handle(
        _seqMeta,
        seq.isAcceptableOrUnknown(data['seq']!, _seqMeta),
      );
    }
    if (data.containsKey('type')) {
      context.handle(
        _typeMeta,
        type.isAcceptableOrUnknown(data['type']!, _typeMeta),
      );
    } else if (isInserting) {
      context.missing(_typeMeta);
    }
    if (data.containsKey('payload')) {
      context.handle(
        _payloadMeta,
        payload.isAcceptableOrUnknown(data['payload']!, _payloadMeta),
      );
    } else if (isInserting) {
      context.missing(_payloadMeta);
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {seq};
  @override
  SyncEventRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SyncEventRow(
      seq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}seq'],
      )!,
      type: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}type'],
      )!,
      payload: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}payload'],
      )!,
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}created_at'],
      )!,
    );
  }

  @override
  $SyncEventsTable createAlias(String alias) {
    return $SyncEventsTable(attachedDatabase, alias);
  }
}

class SyncEventRow extends DataClass implements Insertable<SyncEventRow> {
  final int seq;
  final String type;
  final String payload;
  final int createdAt;
  const SyncEventRow({
    required this.seq,
    required this.type,
    required this.payload,
    required this.createdAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['seq'] = Variable<int>(seq);
    map['type'] = Variable<String>(type);
    map['payload'] = Variable<String>(payload);
    map['created_at'] = Variable<int>(createdAt);
    return map;
  }

  SyncEventsCompanion toCompanion(bool nullToAbsent) {
    return SyncEventsCompanion(
      seq: Value(seq),
      type: Value(type),
      payload: Value(payload),
      createdAt: Value(createdAt),
    );
  }

  factory SyncEventRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SyncEventRow(
      seq: serializer.fromJson<int>(json['seq']),
      type: serializer.fromJson<String>(json['type']),
      payload: serializer.fromJson<String>(json['payload']),
      createdAt: serializer.fromJson<int>(json['createdAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'seq': serializer.toJson<int>(seq),
      'type': serializer.toJson<String>(type),
      'payload': serializer.toJson<String>(payload),
      'createdAt': serializer.toJson<int>(createdAt),
    };
  }

  SyncEventRow copyWith({
    int? seq,
    String? type,
    String? payload,
    int? createdAt,
  }) => SyncEventRow(
    seq: seq ?? this.seq,
    type: type ?? this.type,
    payload: payload ?? this.payload,
    createdAt: createdAt ?? this.createdAt,
  );
  SyncEventRow copyWithCompanion(SyncEventsCompanion data) {
    return SyncEventRow(
      seq: data.seq.present ? data.seq.value : this.seq,
      type: data.type.present ? data.type.value : this.type,
      payload: data.payload.present ? data.payload.value : this.payload,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SyncEventRow(')
          ..write('seq: $seq, ')
          ..write('type: $type, ')
          ..write('payload: $payload, ')
          ..write('createdAt: $createdAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(seq, type, payload, createdAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SyncEventRow &&
          other.seq == this.seq &&
          other.type == this.type &&
          other.payload == this.payload &&
          other.createdAt == this.createdAt);
}

class SyncEventsCompanion extends UpdateCompanion<SyncEventRow> {
  final Value<int> seq;
  final Value<String> type;
  final Value<String> payload;
  final Value<int> createdAt;
  const SyncEventsCompanion({
    this.seq = const Value.absent(),
    this.type = const Value.absent(),
    this.payload = const Value.absent(),
    this.createdAt = const Value.absent(),
  });
  SyncEventsCompanion.insert({
    this.seq = const Value.absent(),
    required String type,
    required String payload,
    required int createdAt,
  }) : type = Value(type),
       payload = Value(payload),
       createdAt = Value(createdAt);
  static Insertable<SyncEventRow> custom({
    Expression<int>? seq,
    Expression<String>? type,
    Expression<String>? payload,
    Expression<int>? createdAt,
  }) {
    return RawValuesInsertable({
      if (seq != null) 'seq': seq,
      if (type != null) 'type': type,
      if (payload != null) 'payload': payload,
      if (createdAt != null) 'created_at': createdAt,
    });
  }

  SyncEventsCompanion copyWith({
    Value<int>? seq,
    Value<String>? type,
    Value<String>? payload,
    Value<int>? createdAt,
  }) {
    return SyncEventsCompanion(
      seq: seq ?? this.seq,
      type: type ?? this.type,
      payload: payload ?? this.payload,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (seq.present) {
      map['seq'] = Variable<int>(seq.value);
    }
    if (type.present) {
      map['type'] = Variable<String>(type.value);
    }
    if (payload.present) {
      map['payload'] = Variable<String>(payload.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<int>(createdAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SyncEventsCompanion(')
          ..write('seq: $seq, ')
          ..write('type: $type, ')
          ..write('payload: $payload, ')
          ..write('createdAt: $createdAt')
          ..write(')'))
        .toString();
  }
}

class $OutboundStatesTable extends OutboundStates
    with TableInfo<$OutboundStatesTable, OutboundStateRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $OutboundStatesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _clientUuidMeta = const VerificationMeta(
    'clientUuid',
  );
  @override
  late final GeneratedColumn<String> clientUuid = GeneratedColumn<String>(
    'client_uuid',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _stateMeta = const VerificationMeta('state');
  @override
  late final GeneratedColumn<String> state = GeneratedColumn<String>(
    'state',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _providerIdMeta = const VerificationMeta(
    'providerId',
  );
  @override
  late final GeneratedColumn<int> providerId = GeneratedColumn<int>(
    'provider_id',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _errorCodeMeta = const VerificationMeta(
    'errorCode',
  );
  @override
  late final GeneratedColumn<int> errorCode = GeneratedColumn<int>(
    'error_code',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _partsMeta = const VerificationMeta('parts');
  @override
  late final GeneratedColumn<int> parts = GeneratedColumn<int>(
    'parts',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<int> updatedAt = GeneratedColumn<int>(
    'updated_at',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _reportedStateMeta = const VerificationMeta(
    'reportedState',
  );
  @override
  late final GeneratedColumn<String> reportedState = GeneratedColumn<String>(
    'reported_state',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _sentByMeta = const VerificationMeta('sentBy');
  @override
  late final GeneratedColumn<String> sentBy = GeneratedColumn<String>(
    'sent_by',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    clientUuid,
    state,
    providerId,
    errorCode,
    parts,
    updatedAt,
    reportedState,
    sentBy,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'outbound_states';
  @override
  VerificationContext validateIntegrity(
    Insertable<OutboundStateRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('client_uuid')) {
      context.handle(
        _clientUuidMeta,
        clientUuid.isAcceptableOrUnknown(data['client_uuid']!, _clientUuidMeta),
      );
    } else if (isInserting) {
      context.missing(_clientUuidMeta);
    }
    if (data.containsKey('state')) {
      context.handle(
        _stateMeta,
        state.isAcceptableOrUnknown(data['state']!, _stateMeta),
      );
    } else if (isInserting) {
      context.missing(_stateMeta);
    }
    if (data.containsKey('provider_id')) {
      context.handle(
        _providerIdMeta,
        providerId.isAcceptableOrUnknown(data['provider_id']!, _providerIdMeta),
      );
    }
    if (data.containsKey('error_code')) {
      context.handle(
        _errorCodeMeta,
        errorCode.isAcceptableOrUnknown(data['error_code']!, _errorCodeMeta),
      );
    }
    if (data.containsKey('parts')) {
      context.handle(
        _partsMeta,
        parts.isAcceptableOrUnknown(data['parts']!, _partsMeta),
      );
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    if (data.containsKey('reported_state')) {
      context.handle(
        _reportedStateMeta,
        reportedState.isAcceptableOrUnknown(
          data['reported_state']!,
          _reportedStateMeta,
        ),
      );
    }
    if (data.containsKey('sent_by')) {
      context.handle(
        _sentByMeta,
        sentBy.isAcceptableOrUnknown(data['sent_by']!, _sentByMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {clientUuid};
  @override
  OutboundStateRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return OutboundStateRow(
      clientUuid: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}client_uuid'],
      )!,
      state: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}state'],
      )!,
      providerId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}provider_id'],
      ),
      errorCode: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}error_code'],
      ),
      parts: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}parts'],
      ),
      updatedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}updated_at'],
      )!,
      reportedState: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}reported_state'],
      ),
      sentBy: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}sent_by'],
      ),
    );
  }

  @override
  $OutboundStatesTable createAlias(String alias) {
    return $OutboundStatesTable(attachedDatabase, alias);
  }
}

class OutboundStateRow extends DataClass
    implements Insertable<OutboundStateRow> {
  final String clientUuid;
  final String state;
  final int? providerId;
  final int? errorCode;
  final int? parts;
  final int updatedAt;
  final String? reportedState;
  final String? sentBy;
  const OutboundStateRow({
    required this.clientUuid,
    required this.state,
    this.providerId,
    this.errorCode,
    this.parts,
    required this.updatedAt,
    this.reportedState,
    this.sentBy,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['client_uuid'] = Variable<String>(clientUuid);
    map['state'] = Variable<String>(state);
    if (!nullToAbsent || providerId != null) {
      map['provider_id'] = Variable<int>(providerId);
    }
    if (!nullToAbsent || errorCode != null) {
      map['error_code'] = Variable<int>(errorCode);
    }
    if (!nullToAbsent || parts != null) {
      map['parts'] = Variable<int>(parts);
    }
    map['updated_at'] = Variable<int>(updatedAt);
    if (!nullToAbsent || reportedState != null) {
      map['reported_state'] = Variable<String>(reportedState);
    }
    if (!nullToAbsent || sentBy != null) {
      map['sent_by'] = Variable<String>(sentBy);
    }
    return map;
  }

  OutboundStatesCompanion toCompanion(bool nullToAbsent) {
    return OutboundStatesCompanion(
      clientUuid: Value(clientUuid),
      state: Value(state),
      providerId: providerId == null && nullToAbsent
          ? const Value.absent()
          : Value(providerId),
      errorCode: errorCode == null && nullToAbsent
          ? const Value.absent()
          : Value(errorCode),
      parts: parts == null && nullToAbsent
          ? const Value.absent()
          : Value(parts),
      updatedAt: Value(updatedAt),
      reportedState: reportedState == null && nullToAbsent
          ? const Value.absent()
          : Value(reportedState),
      sentBy: sentBy == null && nullToAbsent
          ? const Value.absent()
          : Value(sentBy),
    );
  }

  factory OutboundStateRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return OutboundStateRow(
      clientUuid: serializer.fromJson<String>(json['clientUuid']),
      state: serializer.fromJson<String>(json['state']),
      providerId: serializer.fromJson<int?>(json['providerId']),
      errorCode: serializer.fromJson<int?>(json['errorCode']),
      parts: serializer.fromJson<int?>(json['parts']),
      updatedAt: serializer.fromJson<int>(json['updatedAt']),
      reportedState: serializer.fromJson<String?>(json['reportedState']),
      sentBy: serializer.fromJson<String?>(json['sentBy']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'clientUuid': serializer.toJson<String>(clientUuid),
      'state': serializer.toJson<String>(state),
      'providerId': serializer.toJson<int?>(providerId),
      'errorCode': serializer.toJson<int?>(errorCode),
      'parts': serializer.toJson<int?>(parts),
      'updatedAt': serializer.toJson<int>(updatedAt),
      'reportedState': serializer.toJson<String?>(reportedState),
      'sentBy': serializer.toJson<String?>(sentBy),
    };
  }

  OutboundStateRow copyWith({
    String? clientUuid,
    String? state,
    Value<int?> providerId = const Value.absent(),
    Value<int?> errorCode = const Value.absent(),
    Value<int?> parts = const Value.absent(),
    int? updatedAt,
    Value<String?> reportedState = const Value.absent(),
    Value<String?> sentBy = const Value.absent(),
  }) => OutboundStateRow(
    clientUuid: clientUuid ?? this.clientUuid,
    state: state ?? this.state,
    providerId: providerId.present ? providerId.value : this.providerId,
    errorCode: errorCode.present ? errorCode.value : this.errorCode,
    parts: parts.present ? parts.value : this.parts,
    updatedAt: updatedAt ?? this.updatedAt,
    reportedState: reportedState.present
        ? reportedState.value
        : this.reportedState,
    sentBy: sentBy.present ? sentBy.value : this.sentBy,
  );
  OutboundStateRow copyWithCompanion(OutboundStatesCompanion data) {
    return OutboundStateRow(
      clientUuid: data.clientUuid.present
          ? data.clientUuid.value
          : this.clientUuid,
      state: data.state.present ? data.state.value : this.state,
      providerId: data.providerId.present
          ? data.providerId.value
          : this.providerId,
      errorCode: data.errorCode.present ? data.errorCode.value : this.errorCode,
      parts: data.parts.present ? data.parts.value : this.parts,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
      reportedState: data.reportedState.present
          ? data.reportedState.value
          : this.reportedState,
      sentBy: data.sentBy.present ? data.sentBy.value : this.sentBy,
    );
  }

  @override
  String toString() {
    return (StringBuffer('OutboundStateRow(')
          ..write('clientUuid: $clientUuid, ')
          ..write('state: $state, ')
          ..write('providerId: $providerId, ')
          ..write('errorCode: $errorCode, ')
          ..write('parts: $parts, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('reportedState: $reportedState, ')
          ..write('sentBy: $sentBy')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    clientUuid,
    state,
    providerId,
    errorCode,
    parts,
    updatedAt,
    reportedState,
    sentBy,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is OutboundStateRow &&
          other.clientUuid == this.clientUuid &&
          other.state == this.state &&
          other.providerId == this.providerId &&
          other.errorCode == this.errorCode &&
          other.parts == this.parts &&
          other.updatedAt == this.updatedAt &&
          other.reportedState == this.reportedState &&
          other.sentBy == this.sentBy);
}

class OutboundStatesCompanion extends UpdateCompanion<OutboundStateRow> {
  final Value<String> clientUuid;
  final Value<String> state;
  final Value<int?> providerId;
  final Value<int?> errorCode;
  final Value<int?> parts;
  final Value<int> updatedAt;
  final Value<String?> reportedState;
  final Value<String?> sentBy;
  final Value<int> rowid;
  const OutboundStatesCompanion({
    this.clientUuid = const Value.absent(),
    this.state = const Value.absent(),
    this.providerId = const Value.absent(),
    this.errorCode = const Value.absent(),
    this.parts = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.reportedState = const Value.absent(),
    this.sentBy = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  OutboundStatesCompanion.insert({
    required String clientUuid,
    required String state,
    this.providerId = const Value.absent(),
    this.errorCode = const Value.absent(),
    this.parts = const Value.absent(),
    required int updatedAt,
    this.reportedState = const Value.absent(),
    this.sentBy = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : clientUuid = Value(clientUuid),
       state = Value(state),
       updatedAt = Value(updatedAt);
  static Insertable<OutboundStateRow> custom({
    Expression<String>? clientUuid,
    Expression<String>? state,
    Expression<int>? providerId,
    Expression<int>? errorCode,
    Expression<int>? parts,
    Expression<int>? updatedAt,
    Expression<String>? reportedState,
    Expression<String>? sentBy,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (clientUuid != null) 'client_uuid': clientUuid,
      if (state != null) 'state': state,
      if (providerId != null) 'provider_id': providerId,
      if (errorCode != null) 'error_code': errorCode,
      if (parts != null) 'parts': parts,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (reportedState != null) 'reported_state': reportedState,
      if (sentBy != null) 'sent_by': sentBy,
      if (rowid != null) 'rowid': rowid,
    });
  }

  OutboundStatesCompanion copyWith({
    Value<String>? clientUuid,
    Value<String>? state,
    Value<int?>? providerId,
    Value<int?>? errorCode,
    Value<int?>? parts,
    Value<int>? updatedAt,
    Value<String?>? reportedState,
    Value<String?>? sentBy,
    Value<int>? rowid,
  }) {
    return OutboundStatesCompanion(
      clientUuid: clientUuid ?? this.clientUuid,
      state: state ?? this.state,
      providerId: providerId ?? this.providerId,
      errorCode: errorCode ?? this.errorCode,
      parts: parts ?? this.parts,
      updatedAt: updatedAt ?? this.updatedAt,
      reportedState: reportedState ?? this.reportedState,
      sentBy: sentBy ?? this.sentBy,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (clientUuid.present) {
      map['client_uuid'] = Variable<String>(clientUuid.value);
    }
    if (state.present) {
      map['state'] = Variable<String>(state.value);
    }
    if (providerId.present) {
      map['provider_id'] = Variable<int>(providerId.value);
    }
    if (errorCode.present) {
      map['error_code'] = Variable<int>(errorCode.value);
    }
    if (parts.present) {
      map['parts'] = Variable<int>(parts.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<int>(updatedAt.value);
    }
    if (reportedState.present) {
      map['reported_state'] = Variable<String>(reportedState.value);
    }
    if (sentBy.present) {
      map['sent_by'] = Variable<String>(sentBy.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('OutboundStatesCompanion(')
          ..write('clientUuid: $clientUuid, ')
          ..write('state: $state, ')
          ..write('providerId: $providerId, ')
          ..write('errorCode: $errorCode, ')
          ..write('parts: $parts, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('reportedState: $reportedState, ')
          ..write('sentBy: $sentBy, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ConversationPrefsTable extends ConversationPrefs
    with TableInfo<$ConversationPrefsTable, ConversationPrefRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ConversationPrefsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _threadIdMeta = const VerificationMeta(
    'threadId',
  );
  @override
  late final GeneratedColumn<int> threadId = GeneratedColumn<int>(
    'thread_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _pinnedMeta = const VerificationMeta('pinned');
  @override
  late final GeneratedColumn<bool> pinned = GeneratedColumn<bool>(
    'pinned',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("pinned" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _archivedMeta = const VerificationMeta(
    'archived',
  );
  @override
  late final GeneratedColumn<bool> archived = GeneratedColumn<bool>(
    'archived',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("archived" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _mutedMeta = const VerificationMeta('muted');
  @override
  late final GeneratedColumn<bool> muted = GeneratedColumn<bool>(
    'muted',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("muted" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _spamMeta = const VerificationMeta('spam');
  @override
  late final GeneratedColumn<bool> spam = GeneratedColumn<bool>(
    'spam',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("spam" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  @override
  List<GeneratedColumn> get $columns => [
    threadId,
    pinned,
    archived,
    muted,
    spam,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'conversation_prefs';
  @override
  VerificationContext validateIntegrity(
    Insertable<ConversationPrefRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('thread_id')) {
      context.handle(
        _threadIdMeta,
        threadId.isAcceptableOrUnknown(data['thread_id']!, _threadIdMeta),
      );
    }
    if (data.containsKey('pinned')) {
      context.handle(
        _pinnedMeta,
        pinned.isAcceptableOrUnknown(data['pinned']!, _pinnedMeta),
      );
    }
    if (data.containsKey('archived')) {
      context.handle(
        _archivedMeta,
        archived.isAcceptableOrUnknown(data['archived']!, _archivedMeta),
      );
    }
    if (data.containsKey('muted')) {
      context.handle(
        _mutedMeta,
        muted.isAcceptableOrUnknown(data['muted']!, _mutedMeta),
      );
    }
    if (data.containsKey('spam')) {
      context.handle(
        _spamMeta,
        spam.isAcceptableOrUnknown(data['spam']!, _spamMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {threadId};
  @override
  ConversationPrefRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ConversationPrefRow(
      threadId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}thread_id'],
      )!,
      pinned: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}pinned'],
      )!,
      archived: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}archived'],
      )!,
      muted: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}muted'],
      )!,
      spam: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}spam'],
      )!,
    );
  }

  @override
  $ConversationPrefsTable createAlias(String alias) {
    return $ConversationPrefsTable(attachedDatabase, alias);
  }
}

class ConversationPrefRow extends DataClass
    implements Insertable<ConversationPrefRow> {
  final int threadId;
  final bool pinned;
  final bool archived;
  final bool muted;
  final bool spam;
  const ConversationPrefRow({
    required this.threadId,
    required this.pinned,
    required this.archived,
    required this.muted,
    required this.spam,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['thread_id'] = Variable<int>(threadId);
    map['pinned'] = Variable<bool>(pinned);
    map['archived'] = Variable<bool>(archived);
    map['muted'] = Variable<bool>(muted);
    map['spam'] = Variable<bool>(spam);
    return map;
  }

  ConversationPrefsCompanion toCompanion(bool nullToAbsent) {
    return ConversationPrefsCompanion(
      threadId: Value(threadId),
      pinned: Value(pinned),
      archived: Value(archived),
      muted: Value(muted),
      spam: Value(spam),
    );
  }

  factory ConversationPrefRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ConversationPrefRow(
      threadId: serializer.fromJson<int>(json['threadId']),
      pinned: serializer.fromJson<bool>(json['pinned']),
      archived: serializer.fromJson<bool>(json['archived']),
      muted: serializer.fromJson<bool>(json['muted']),
      spam: serializer.fromJson<bool>(json['spam']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'threadId': serializer.toJson<int>(threadId),
      'pinned': serializer.toJson<bool>(pinned),
      'archived': serializer.toJson<bool>(archived),
      'muted': serializer.toJson<bool>(muted),
      'spam': serializer.toJson<bool>(spam),
    };
  }

  ConversationPrefRow copyWith({
    int? threadId,
    bool? pinned,
    bool? archived,
    bool? muted,
    bool? spam,
  }) => ConversationPrefRow(
    threadId: threadId ?? this.threadId,
    pinned: pinned ?? this.pinned,
    archived: archived ?? this.archived,
    muted: muted ?? this.muted,
    spam: spam ?? this.spam,
  );
  ConversationPrefRow copyWithCompanion(ConversationPrefsCompanion data) {
    return ConversationPrefRow(
      threadId: data.threadId.present ? data.threadId.value : this.threadId,
      pinned: data.pinned.present ? data.pinned.value : this.pinned,
      archived: data.archived.present ? data.archived.value : this.archived,
      muted: data.muted.present ? data.muted.value : this.muted,
      spam: data.spam.present ? data.spam.value : this.spam,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ConversationPrefRow(')
          ..write('threadId: $threadId, ')
          ..write('pinned: $pinned, ')
          ..write('archived: $archived, ')
          ..write('muted: $muted, ')
          ..write('spam: $spam')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(threadId, pinned, archived, muted, spam);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ConversationPrefRow &&
          other.threadId == this.threadId &&
          other.pinned == this.pinned &&
          other.archived == this.archived &&
          other.muted == this.muted &&
          other.spam == this.spam);
}

class ConversationPrefsCompanion extends UpdateCompanion<ConversationPrefRow> {
  final Value<int> threadId;
  final Value<bool> pinned;
  final Value<bool> archived;
  final Value<bool> muted;
  final Value<bool> spam;
  const ConversationPrefsCompanion({
    this.threadId = const Value.absent(),
    this.pinned = const Value.absent(),
    this.archived = const Value.absent(),
    this.muted = const Value.absent(),
    this.spam = const Value.absent(),
  });
  ConversationPrefsCompanion.insert({
    this.threadId = const Value.absent(),
    this.pinned = const Value.absent(),
    this.archived = const Value.absent(),
    this.muted = const Value.absent(),
    this.spam = const Value.absent(),
  });
  static Insertable<ConversationPrefRow> custom({
    Expression<int>? threadId,
    Expression<bool>? pinned,
    Expression<bool>? archived,
    Expression<bool>? muted,
    Expression<bool>? spam,
  }) {
    return RawValuesInsertable({
      if (threadId != null) 'thread_id': threadId,
      if (pinned != null) 'pinned': pinned,
      if (archived != null) 'archived': archived,
      if (muted != null) 'muted': muted,
      if (spam != null) 'spam': spam,
    });
  }

  ConversationPrefsCompanion copyWith({
    Value<int>? threadId,
    Value<bool>? pinned,
    Value<bool>? archived,
    Value<bool>? muted,
    Value<bool>? spam,
  }) {
    return ConversationPrefsCompanion(
      threadId: threadId ?? this.threadId,
      pinned: pinned ?? this.pinned,
      archived: archived ?? this.archived,
      muted: muted ?? this.muted,
      spam: spam ?? this.spam,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (threadId.present) {
      map['thread_id'] = Variable<int>(threadId.value);
    }
    if (pinned.present) {
      map['pinned'] = Variable<bool>(pinned.value);
    }
    if (archived.present) {
      map['archived'] = Variable<bool>(archived.value);
    }
    if (muted.present) {
      map['muted'] = Variable<bool>(muted.value);
    }
    if (spam.present) {
      map['spam'] = Variable<bool>(spam.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ConversationPrefsCompanion(')
          ..write('threadId: $threadId, ')
          ..write('pinned: $pinned, ')
          ..write('archived: $archived, ')
          ..write('muted: $muted, ')
          ..write('spam: $spam')
          ..write(')'))
        .toString();
  }
}

class $StarredMessagesTable extends StarredMessages
    with TableInfo<$StarredMessagesTable, StarredRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $StarredMessagesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _kindMeta = const VerificationMeta('kind');
  @override
  late final GeneratedColumn<String> kind = GeneratedColumn<String>(
    'kind',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _providerIdMeta = const VerificationMeta(
    'providerId',
  );
  @override
  late final GeneratedColumn<int> providerId = GeneratedColumn<int>(
    'provider_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [kind, providerId];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'starred_messages';
  @override
  VerificationContext validateIntegrity(
    Insertable<StarredRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('kind')) {
      context.handle(
        _kindMeta,
        kind.isAcceptableOrUnknown(data['kind']!, _kindMeta),
      );
    } else if (isInserting) {
      context.missing(_kindMeta);
    }
    if (data.containsKey('provider_id')) {
      context.handle(
        _providerIdMeta,
        providerId.isAcceptableOrUnknown(data['provider_id']!, _providerIdMeta),
      );
    } else if (isInserting) {
      context.missing(_providerIdMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {kind, providerId};
  @override
  StarredRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return StarredRow(
      kind: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}kind'],
      )!,
      providerId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}provider_id'],
      )!,
    );
  }

  @override
  $StarredMessagesTable createAlias(String alias) {
    return $StarredMessagesTable(attachedDatabase, alias);
  }
}

class StarredRow extends DataClass implements Insertable<StarredRow> {
  final String kind;
  final int providerId;
  const StarredRow({required this.kind, required this.providerId});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['kind'] = Variable<String>(kind);
    map['provider_id'] = Variable<int>(providerId);
    return map;
  }

  StarredMessagesCompanion toCompanion(bool nullToAbsent) {
    return StarredMessagesCompanion(
      kind: Value(kind),
      providerId: Value(providerId),
    );
  }

  factory StarredRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return StarredRow(
      kind: serializer.fromJson<String>(json['kind']),
      providerId: serializer.fromJson<int>(json['providerId']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'kind': serializer.toJson<String>(kind),
      'providerId': serializer.toJson<int>(providerId),
    };
  }

  StarredRow copyWith({String? kind, int? providerId}) => StarredRow(
    kind: kind ?? this.kind,
    providerId: providerId ?? this.providerId,
  );
  StarredRow copyWithCompanion(StarredMessagesCompanion data) {
    return StarredRow(
      kind: data.kind.present ? data.kind.value : this.kind,
      providerId: data.providerId.present
          ? data.providerId.value
          : this.providerId,
    );
  }

  @override
  String toString() {
    return (StringBuffer('StarredRow(')
          ..write('kind: $kind, ')
          ..write('providerId: $providerId')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(kind, providerId);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is StarredRow &&
          other.kind == this.kind &&
          other.providerId == this.providerId);
}

class StarredMessagesCompanion extends UpdateCompanion<StarredRow> {
  final Value<String> kind;
  final Value<int> providerId;
  final Value<int> rowid;
  const StarredMessagesCompanion({
    this.kind = const Value.absent(),
    this.providerId = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  StarredMessagesCompanion.insert({
    required String kind,
    required int providerId,
    this.rowid = const Value.absent(),
  }) : kind = Value(kind),
       providerId = Value(providerId);
  static Insertable<StarredRow> custom({
    Expression<String>? kind,
    Expression<int>? providerId,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (kind != null) 'kind': kind,
      if (providerId != null) 'provider_id': providerId,
      if (rowid != null) 'rowid': rowid,
    });
  }

  StarredMessagesCompanion copyWith({
    Value<String>? kind,
    Value<int>? providerId,
    Value<int>? rowid,
  }) {
    return StarredMessagesCompanion(
      kind: kind ?? this.kind,
      providerId: providerId ?? this.providerId,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (kind.present) {
      map['kind'] = Variable<String>(kind.value);
    }
    if (providerId.present) {
      map['provider_id'] = Variable<int>(providerId.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('StarredMessagesCompanion(')
          ..write('kind: $kind, ')
          ..write('providerId: $providerId, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $DraftsTable extends Drafts with TableInfo<$DraftsTable, DraftRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $DraftsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _keyMeta = const VerificationMeta('key');
  @override
  late final GeneratedColumn<String> key = GeneratedColumn<String>(
    'key',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _bodyMeta = const VerificationMeta('body');
  @override
  late final GeneratedColumn<String> body = GeneratedColumn<String>(
    'body',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<int> updatedAt = GeneratedColumn<int>(
    'updated_at',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [key, body, updatedAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'drafts';
  @override
  VerificationContext validateIntegrity(
    Insertable<DraftRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('key')) {
      context.handle(
        _keyMeta,
        key.isAcceptableOrUnknown(data['key']!, _keyMeta),
      );
    } else if (isInserting) {
      context.missing(_keyMeta);
    }
    if (data.containsKey('body')) {
      context.handle(
        _bodyMeta,
        body.isAcceptableOrUnknown(data['body']!, _bodyMeta),
      );
    } else if (isInserting) {
      context.missing(_bodyMeta);
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {key};
  @override
  DraftRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return DraftRow(
      key: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}key'],
      )!,
      body: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}body'],
      )!,
      updatedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}updated_at'],
      )!,
    );
  }

  @override
  $DraftsTable createAlias(String alias) {
    return $DraftsTable(attachedDatabase, alias);
  }
}

class DraftRow extends DataClass implements Insertable<DraftRow> {
  final String key;
  final String body;
  final int updatedAt;
  const DraftRow({
    required this.key,
    required this.body,
    required this.updatedAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['key'] = Variable<String>(key);
    map['body'] = Variable<String>(body);
    map['updated_at'] = Variable<int>(updatedAt);
    return map;
  }

  DraftsCompanion toCompanion(bool nullToAbsent) {
    return DraftsCompanion(
      key: Value(key),
      body: Value(body),
      updatedAt: Value(updatedAt),
    );
  }

  factory DraftRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return DraftRow(
      key: serializer.fromJson<String>(json['key']),
      body: serializer.fromJson<String>(json['body']),
      updatedAt: serializer.fromJson<int>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'key': serializer.toJson<String>(key),
      'body': serializer.toJson<String>(body),
      'updatedAt': serializer.toJson<int>(updatedAt),
    };
  }

  DraftRow copyWith({String? key, String? body, int? updatedAt}) => DraftRow(
    key: key ?? this.key,
    body: body ?? this.body,
    updatedAt: updatedAt ?? this.updatedAt,
  );
  DraftRow copyWithCompanion(DraftsCompanion data) {
    return DraftRow(
      key: data.key.present ? data.key.value : this.key,
      body: data.body.present ? data.body.value : this.body,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('DraftRow(')
          ..write('key: $key, ')
          ..write('body: $body, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(key, body, updatedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is DraftRow &&
          other.key == this.key &&
          other.body == this.body &&
          other.updatedAt == this.updatedAt);
}

class DraftsCompanion extends UpdateCompanion<DraftRow> {
  final Value<String> key;
  final Value<String> body;
  final Value<int> updatedAt;
  final Value<int> rowid;
  const DraftsCompanion({
    this.key = const Value.absent(),
    this.body = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  DraftsCompanion.insert({
    required String key,
    required String body,
    required int updatedAt,
    this.rowid = const Value.absent(),
  }) : key = Value(key),
       body = Value(body),
       updatedAt = Value(updatedAt);
  static Insertable<DraftRow> custom({
    Expression<String>? key,
    Expression<String>? body,
    Expression<int>? updatedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (key != null) 'key': key,
      if (body != null) 'body': body,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  DraftsCompanion copyWith({
    Value<String>? key,
    Value<String>? body,
    Value<int>? updatedAt,
    Value<int>? rowid,
  }) {
    return DraftsCompanion(
      key: key ?? this.key,
      body: body ?? this.body,
      updatedAt: updatedAt ?? this.updatedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (key.present) {
      map['key'] = Variable<String>(key.value);
    }
    if (body.present) {
      map['body'] = Variable<String>(body.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<int>(updatedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('DraftsCompanion(')
          ..write('key: $key, ')
          ..write('body: $body, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ScheduledSendsTable extends ScheduledSends
    with TableInfo<$ScheduledSendsTable, ScheduledRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ScheduledSendsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _clientUuidMeta = const VerificationMeta(
    'clientUuid',
  );
  @override
  late final GeneratedColumn<String> clientUuid = GeneratedColumn<String>(
    'client_uuid',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _addressesMeta = const VerificationMeta(
    'addresses',
  );
  @override
  late final GeneratedColumn<String> addresses = GeneratedColumn<String>(
    'addresses',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _bodyMeta = const VerificationMeta('body');
  @override
  late final GeneratedColumn<String> body = GeneratedColumn<String>(
    'body',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _subscriptionIdMeta = const VerificationMeta(
    'subscriptionId',
  );
  @override
  late final GeneratedColumn<int> subscriptionId = GeneratedColumn<int>(
    'subscription_id',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _sendAtMeta = const VerificationMeta('sendAt');
  @override
  late final GeneratedColumn<int> sendAt = GeneratedColumn<int>(
    'send_at',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    clientUuid,
    addresses,
    body,
    subscriptionId,
    sendAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'scheduled_sends';
  @override
  VerificationContext validateIntegrity(
    Insertable<ScheduledRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('client_uuid')) {
      context.handle(
        _clientUuidMeta,
        clientUuid.isAcceptableOrUnknown(data['client_uuid']!, _clientUuidMeta),
      );
    } else if (isInserting) {
      context.missing(_clientUuidMeta);
    }
    if (data.containsKey('addresses')) {
      context.handle(
        _addressesMeta,
        addresses.isAcceptableOrUnknown(data['addresses']!, _addressesMeta),
      );
    } else if (isInserting) {
      context.missing(_addressesMeta);
    }
    if (data.containsKey('body')) {
      context.handle(
        _bodyMeta,
        body.isAcceptableOrUnknown(data['body']!, _bodyMeta),
      );
    } else if (isInserting) {
      context.missing(_bodyMeta);
    }
    if (data.containsKey('subscription_id')) {
      context.handle(
        _subscriptionIdMeta,
        subscriptionId.isAcceptableOrUnknown(
          data['subscription_id']!,
          _subscriptionIdMeta,
        ),
      );
    }
    if (data.containsKey('send_at')) {
      context.handle(
        _sendAtMeta,
        sendAt.isAcceptableOrUnknown(data['send_at']!, _sendAtMeta),
      );
    } else if (isInserting) {
      context.missing(_sendAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {clientUuid};
  @override
  ScheduledRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ScheduledRow(
      clientUuid: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}client_uuid'],
      )!,
      addresses: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}addresses'],
      )!,
      body: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}body'],
      )!,
      subscriptionId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}subscription_id'],
      ),
      sendAt: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}send_at'],
      )!,
    );
  }

  @override
  $ScheduledSendsTable createAlias(String alias) {
    return $ScheduledSendsTable(attachedDatabase, alias);
  }
}

class ScheduledRow extends DataClass implements Insertable<ScheduledRow> {
  final String clientUuid;
  final String addresses;
  final String body;
  final int? subscriptionId;
  final int sendAt;
  const ScheduledRow({
    required this.clientUuid,
    required this.addresses,
    required this.body,
    this.subscriptionId,
    required this.sendAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['client_uuid'] = Variable<String>(clientUuid);
    map['addresses'] = Variable<String>(addresses);
    map['body'] = Variable<String>(body);
    if (!nullToAbsent || subscriptionId != null) {
      map['subscription_id'] = Variable<int>(subscriptionId);
    }
    map['send_at'] = Variable<int>(sendAt);
    return map;
  }

  ScheduledSendsCompanion toCompanion(bool nullToAbsent) {
    return ScheduledSendsCompanion(
      clientUuid: Value(clientUuid),
      addresses: Value(addresses),
      body: Value(body),
      subscriptionId: subscriptionId == null && nullToAbsent
          ? const Value.absent()
          : Value(subscriptionId),
      sendAt: Value(sendAt),
    );
  }

  factory ScheduledRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ScheduledRow(
      clientUuid: serializer.fromJson<String>(json['clientUuid']),
      addresses: serializer.fromJson<String>(json['addresses']),
      body: serializer.fromJson<String>(json['body']),
      subscriptionId: serializer.fromJson<int?>(json['subscriptionId']),
      sendAt: serializer.fromJson<int>(json['sendAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'clientUuid': serializer.toJson<String>(clientUuid),
      'addresses': serializer.toJson<String>(addresses),
      'body': serializer.toJson<String>(body),
      'subscriptionId': serializer.toJson<int?>(subscriptionId),
      'sendAt': serializer.toJson<int>(sendAt),
    };
  }

  ScheduledRow copyWith({
    String? clientUuid,
    String? addresses,
    String? body,
    Value<int?> subscriptionId = const Value.absent(),
    int? sendAt,
  }) => ScheduledRow(
    clientUuid: clientUuid ?? this.clientUuid,
    addresses: addresses ?? this.addresses,
    body: body ?? this.body,
    subscriptionId: subscriptionId.present
        ? subscriptionId.value
        : this.subscriptionId,
    sendAt: sendAt ?? this.sendAt,
  );
  ScheduledRow copyWithCompanion(ScheduledSendsCompanion data) {
    return ScheduledRow(
      clientUuid: data.clientUuid.present
          ? data.clientUuid.value
          : this.clientUuid,
      addresses: data.addresses.present ? data.addresses.value : this.addresses,
      body: data.body.present ? data.body.value : this.body,
      subscriptionId: data.subscriptionId.present
          ? data.subscriptionId.value
          : this.subscriptionId,
      sendAt: data.sendAt.present ? data.sendAt.value : this.sendAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ScheduledRow(')
          ..write('clientUuid: $clientUuid, ')
          ..write('addresses: $addresses, ')
          ..write('body: $body, ')
          ..write('subscriptionId: $subscriptionId, ')
          ..write('sendAt: $sendAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(clientUuid, addresses, body, subscriptionId, sendAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ScheduledRow &&
          other.clientUuid == this.clientUuid &&
          other.addresses == this.addresses &&
          other.body == this.body &&
          other.subscriptionId == this.subscriptionId &&
          other.sendAt == this.sendAt);
}

class ScheduledSendsCompanion extends UpdateCompanion<ScheduledRow> {
  final Value<String> clientUuid;
  final Value<String> addresses;
  final Value<String> body;
  final Value<int?> subscriptionId;
  final Value<int> sendAt;
  final Value<int> rowid;
  const ScheduledSendsCompanion({
    this.clientUuid = const Value.absent(),
    this.addresses = const Value.absent(),
    this.body = const Value.absent(),
    this.subscriptionId = const Value.absent(),
    this.sendAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  ScheduledSendsCompanion.insert({
    required String clientUuid,
    required String addresses,
    required String body,
    this.subscriptionId = const Value.absent(),
    required int sendAt,
    this.rowid = const Value.absent(),
  }) : clientUuid = Value(clientUuid),
       addresses = Value(addresses),
       body = Value(body),
       sendAt = Value(sendAt);
  static Insertable<ScheduledRow> custom({
    Expression<String>? clientUuid,
    Expression<String>? addresses,
    Expression<String>? body,
    Expression<int>? subscriptionId,
    Expression<int>? sendAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (clientUuid != null) 'client_uuid': clientUuid,
      if (addresses != null) 'addresses': addresses,
      if (body != null) 'body': body,
      if (subscriptionId != null) 'subscription_id': subscriptionId,
      if (sendAt != null) 'send_at': sendAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  ScheduledSendsCompanion copyWith({
    Value<String>? clientUuid,
    Value<String>? addresses,
    Value<String>? body,
    Value<int?>? subscriptionId,
    Value<int>? sendAt,
    Value<int>? rowid,
  }) {
    return ScheduledSendsCompanion(
      clientUuid: clientUuid ?? this.clientUuid,
      addresses: addresses ?? this.addresses,
      body: body ?? this.body,
      subscriptionId: subscriptionId ?? this.subscriptionId,
      sendAt: sendAt ?? this.sendAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (clientUuid.present) {
      map['client_uuid'] = Variable<String>(clientUuid.value);
    }
    if (addresses.present) {
      map['addresses'] = Variable<String>(addresses.value);
    }
    if (body.present) {
      map['body'] = Variable<String>(body.value);
    }
    if (subscriptionId.present) {
      map['subscription_id'] = Variable<int>(subscriptionId.value);
    }
    if (sendAt.present) {
      map['send_at'] = Variable<int>(sendAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ScheduledSendsCompanion(')
          ..write('clientUuid: $clientUuid, ')
          ..write('addresses: $addresses, ')
          ..write('body: $body, ')
          ..write('subscriptionId: $subscriptionId, ')
          ..write('sendAt: $sendAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $PendingMediaTable extends PendingMedia
    with TableInfo<$PendingMediaTable, PendingMediaRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $PendingMediaTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _providerIdMeta = const VerificationMeta(
    'providerId',
  );
  @override
  late final GeneratedColumn<int> providerId = GeneratedColumn<int>(
    'provider_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _dateMeta = const VerificationMeta('date');
  @override
  late final GeneratedColumn<int> date = GeneratedColumn<int>(
    'date',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _seqMeta = const VerificationMeta('seq');
  @override
  late final GeneratedColumn<int> seq = GeneratedColumn<int>(
    'seq',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _uriMeta = const VerificationMeta('uri');
  @override
  late final GeneratedColumn<String> uri = GeneratedColumn<String>(
    'uri',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sizeMeta = const VerificationMeta('size');
  @override
  late final GeneratedColumn<int> size = GeneratedColumn<int>(
    'size',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _offsetMeta = const VerificationMeta('offset');
  @override
  late final GeneratedColumn<int> offset = GeneratedColumn<int>(
    'offset',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  @override
  List<GeneratedColumn> get $columns => [
    providerId,
    date,
    seq,
    uri,
    size,
    offset,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'pending_media';
  @override
  VerificationContext validateIntegrity(
    Insertable<PendingMediaRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('provider_id')) {
      context.handle(
        _providerIdMeta,
        providerId.isAcceptableOrUnknown(data['provider_id']!, _providerIdMeta),
      );
    } else if (isInserting) {
      context.missing(_providerIdMeta);
    }
    if (data.containsKey('date')) {
      context.handle(
        _dateMeta,
        date.isAcceptableOrUnknown(data['date']!, _dateMeta),
      );
    } else if (isInserting) {
      context.missing(_dateMeta);
    }
    if (data.containsKey('seq')) {
      context.handle(
        _seqMeta,
        seq.isAcceptableOrUnknown(data['seq']!, _seqMeta),
      );
    } else if (isInserting) {
      context.missing(_seqMeta);
    }
    if (data.containsKey('uri')) {
      context.handle(
        _uriMeta,
        uri.isAcceptableOrUnknown(data['uri']!, _uriMeta),
      );
    } else if (isInserting) {
      context.missing(_uriMeta);
    }
    if (data.containsKey('size')) {
      context.handle(
        _sizeMeta,
        size.isAcceptableOrUnknown(data['size']!, _sizeMeta),
      );
    } else if (isInserting) {
      context.missing(_sizeMeta);
    }
    if (data.containsKey('offset')) {
      context.handle(
        _offsetMeta,
        offset.isAcceptableOrUnknown(data['offset']!, _offsetMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {providerId, date, seq};
  @override
  PendingMediaRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return PendingMediaRow(
      providerId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}provider_id'],
      )!,
      date: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}date'],
      )!,
      seq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}seq'],
      )!,
      uri: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}uri'],
      )!,
      size: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}size'],
      )!,
      offset: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}offset'],
      )!,
    );
  }

  @override
  $PendingMediaTable createAlias(String alias) {
    return $PendingMediaTable(attachedDatabase, alias);
  }
}

class PendingMediaRow extends DataClass implements Insertable<PendingMediaRow> {
  final int providerId;
  final int date;
  final int seq;
  final String uri;
  final int size;
  final int offset;
  const PendingMediaRow({
    required this.providerId,
    required this.date,
    required this.seq,
    required this.uri,
    required this.size,
    required this.offset,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['provider_id'] = Variable<int>(providerId);
    map['date'] = Variable<int>(date);
    map['seq'] = Variable<int>(seq);
    map['uri'] = Variable<String>(uri);
    map['size'] = Variable<int>(size);
    map['offset'] = Variable<int>(offset);
    return map;
  }

  PendingMediaCompanion toCompanion(bool nullToAbsent) {
    return PendingMediaCompanion(
      providerId: Value(providerId),
      date: Value(date),
      seq: Value(seq),
      uri: Value(uri),
      size: Value(size),
      offset: Value(offset),
    );
  }

  factory PendingMediaRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return PendingMediaRow(
      providerId: serializer.fromJson<int>(json['providerId']),
      date: serializer.fromJson<int>(json['date']),
      seq: serializer.fromJson<int>(json['seq']),
      uri: serializer.fromJson<String>(json['uri']),
      size: serializer.fromJson<int>(json['size']),
      offset: serializer.fromJson<int>(json['offset']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'providerId': serializer.toJson<int>(providerId),
      'date': serializer.toJson<int>(date),
      'seq': serializer.toJson<int>(seq),
      'uri': serializer.toJson<String>(uri),
      'size': serializer.toJson<int>(size),
      'offset': serializer.toJson<int>(offset),
    };
  }

  PendingMediaRow copyWith({
    int? providerId,
    int? date,
    int? seq,
    String? uri,
    int? size,
    int? offset,
  }) => PendingMediaRow(
    providerId: providerId ?? this.providerId,
    date: date ?? this.date,
    seq: seq ?? this.seq,
    uri: uri ?? this.uri,
    size: size ?? this.size,
    offset: offset ?? this.offset,
  );
  PendingMediaRow copyWithCompanion(PendingMediaCompanion data) {
    return PendingMediaRow(
      providerId: data.providerId.present
          ? data.providerId.value
          : this.providerId,
      date: data.date.present ? data.date.value : this.date,
      seq: data.seq.present ? data.seq.value : this.seq,
      uri: data.uri.present ? data.uri.value : this.uri,
      size: data.size.present ? data.size.value : this.size,
      offset: data.offset.present ? data.offset.value : this.offset,
    );
  }

  @override
  String toString() {
    return (StringBuffer('PendingMediaRow(')
          ..write('providerId: $providerId, ')
          ..write('date: $date, ')
          ..write('seq: $seq, ')
          ..write('uri: $uri, ')
          ..write('size: $size, ')
          ..write('offset: $offset')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(providerId, date, seq, uri, size, offset);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is PendingMediaRow &&
          other.providerId == this.providerId &&
          other.date == this.date &&
          other.seq == this.seq &&
          other.uri == this.uri &&
          other.size == this.size &&
          other.offset == this.offset);
}

class PendingMediaCompanion extends UpdateCompanion<PendingMediaRow> {
  final Value<int> providerId;
  final Value<int> date;
  final Value<int> seq;
  final Value<String> uri;
  final Value<int> size;
  final Value<int> offset;
  final Value<int> rowid;
  const PendingMediaCompanion({
    this.providerId = const Value.absent(),
    this.date = const Value.absent(),
    this.seq = const Value.absent(),
    this.uri = const Value.absent(),
    this.size = const Value.absent(),
    this.offset = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  PendingMediaCompanion.insert({
    required int providerId,
    required int date,
    required int seq,
    required String uri,
    required int size,
    this.offset = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : providerId = Value(providerId),
       date = Value(date),
       seq = Value(seq),
       uri = Value(uri),
       size = Value(size);
  static Insertable<PendingMediaRow> custom({
    Expression<int>? providerId,
    Expression<int>? date,
    Expression<int>? seq,
    Expression<String>? uri,
    Expression<int>? size,
    Expression<int>? offset,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (providerId != null) 'provider_id': providerId,
      if (date != null) 'date': date,
      if (seq != null) 'seq': seq,
      if (uri != null) 'uri': uri,
      if (size != null) 'size': size,
      if (offset != null) 'offset': offset,
      if (rowid != null) 'rowid': rowid,
    });
  }

  PendingMediaCompanion copyWith({
    Value<int>? providerId,
    Value<int>? date,
    Value<int>? seq,
    Value<String>? uri,
    Value<int>? size,
    Value<int>? offset,
    Value<int>? rowid,
  }) {
    return PendingMediaCompanion(
      providerId: providerId ?? this.providerId,
      date: date ?? this.date,
      seq: seq ?? this.seq,
      uri: uri ?? this.uri,
      size: size ?? this.size,
      offset: offset ?? this.offset,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (providerId.present) {
      map['provider_id'] = Variable<int>(providerId.value);
    }
    if (date.present) {
      map['date'] = Variable<int>(date.value);
    }
    if (seq.present) {
      map['seq'] = Variable<int>(seq.value);
    }
    if (uri.present) {
      map['uri'] = Variable<String>(uri.value);
    }
    if (size.present) {
      map['size'] = Variable<int>(size.value);
    }
    if (offset.present) {
      map['offset'] = Variable<int>(offset.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('PendingMediaCompanion(')
          ..write('providerId: $providerId, ')
          ..write('date: $date, ')
          ..write('seq: $seq, ')
          ..write('uri: $uri, ')
          ..write('size: $size, ')
          ..write('offset: $offset, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $KeyValuesTable extends KeyValues with TableInfo<$KeyValuesTable, KvRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $KeyValuesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _keyMeta = const VerificationMeta('key');
  @override
  late final GeneratedColumn<String> key = GeneratedColumn<String>(
    'key',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _valueMeta = const VerificationMeta('value');
  @override
  late final GeneratedColumn<String> value = GeneratedColumn<String>(
    'value',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [key, value];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'kv';
  @override
  VerificationContext validateIntegrity(
    Insertable<KvRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('key')) {
      context.handle(
        _keyMeta,
        key.isAcceptableOrUnknown(data['key']!, _keyMeta),
      );
    } else if (isInserting) {
      context.missing(_keyMeta);
    }
    if (data.containsKey('value')) {
      context.handle(
        _valueMeta,
        value.isAcceptableOrUnknown(data['value']!, _valueMeta),
      );
    } else if (isInserting) {
      context.missing(_valueMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {key};
  @override
  KvRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return KvRow(
      key: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}key'],
      )!,
      value: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}value'],
      )!,
    );
  }

  @override
  $KeyValuesTable createAlias(String alias) {
    return $KeyValuesTable(attachedDatabase, alias);
  }
}

class KvRow extends DataClass implements Insertable<KvRow> {
  final String key;
  final String value;
  const KvRow({required this.key, required this.value});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['key'] = Variable<String>(key);
    map['value'] = Variable<String>(value);
    return map;
  }

  KeyValuesCompanion toCompanion(bool nullToAbsent) {
    return KeyValuesCompanion(key: Value(key), value: Value(value));
  }

  factory KvRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return KvRow(
      key: serializer.fromJson<String>(json['key']),
      value: serializer.fromJson<String>(json['value']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'key': serializer.toJson<String>(key),
      'value': serializer.toJson<String>(value),
    };
  }

  KvRow copyWith({String? key, String? value}) =>
      KvRow(key: key ?? this.key, value: value ?? this.value);
  KvRow copyWithCompanion(KeyValuesCompanion data) {
    return KvRow(
      key: data.key.present ? data.key.value : this.key,
      value: data.value.present ? data.value.value : this.value,
    );
  }

  @override
  String toString() {
    return (StringBuffer('KvRow(')
          ..write('key: $key, ')
          ..write('value: $value')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(key, value);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is KvRow && other.key == this.key && other.value == this.value);
}

class KeyValuesCompanion extends UpdateCompanion<KvRow> {
  final Value<String> key;
  final Value<String> value;
  final Value<int> rowid;
  const KeyValuesCompanion({
    this.key = const Value.absent(),
    this.value = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  KeyValuesCompanion.insert({
    required String key,
    required String value,
    this.rowid = const Value.absent(),
  }) : key = Value(key),
       value = Value(value);
  static Insertable<KvRow> custom({
    Expression<String>? key,
    Expression<String>? value,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (key != null) 'key': key,
      if (value != null) 'value': value,
      if (rowid != null) 'rowid': rowid,
    });
  }

  KeyValuesCompanion copyWith({
    Value<String>? key,
    Value<String>? value,
    Value<int>? rowid,
  }) {
    return KeyValuesCompanion(
      key: key ?? this.key,
      value: value ?? this.value,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (key.present) {
      map['key'] = Variable<String>(key.value);
    }
    if (value.present) {
      map['value'] = Variable<String>(value.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('KeyValuesCompanion(')
          ..write('key: $key, ')
          ..write('value: $value, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ThreadCacheTable extends ThreadCache
    with TableInfo<$ThreadCacheTable, ThreadCacheRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ThreadCacheTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _threadIdMeta = const VerificationMeta(
    'threadId',
  );
  @override
  late final GeneratedColumn<int> threadId = GeneratedColumn<int>(
    'thread_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _addressesMeta = const VerificationMeta(
    'addresses',
  );
  @override
  late final GeneratedColumn<String> addresses = GeneratedColumn<String>(
    'addresses',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _titleMeta = const VerificationMeta('title');
  @override
  late final GeneratedColumn<String> title = GeneratedColumn<String>(
    'title',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _savedMeta = const VerificationMeta('saved');
  @override
  late final GeneratedColumn<bool> saved = GeneratedColumn<bool>(
    'saved',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("saved" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _photoUriMeta = const VerificationMeta(
    'photoUri',
  );
  @override
  late final GeneratedColumn<String> photoUri = GeneratedColumn<String>(
    'photo_uri',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _snippetMeta = const VerificationMeta(
    'snippet',
  );
  @override
  late final GeneratedColumn<String> snippet = GeneratedColumn<String>(
    'snippet',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _dateMeta = const VerificationMeta('date');
  @override
  late final GeneratedColumn<int> date = GeneratedColumn<int>(
    'date',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unreadMeta = const VerificationMeta('unread');
  @override
  late final GeneratedColumn<int> unread = GeneratedColumn<int>(
    'unread',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _messageCountMeta = const VerificationMeta(
    'messageCount',
  );
  @override
  late final GeneratedColumn<int> messageCount = GeneratedColumn<int>(
    'message_count',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _hasMmsMeta = const VerificationMeta('hasMms');
  @override
  late final GeneratedColumn<bool> hasMms = GeneratedColumn<bool>(
    'has_mms',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("has_mms" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  @override
  List<GeneratedColumn> get $columns => [
    threadId,
    addresses,
    title,
    saved,
    photoUri,
    snippet,
    date,
    unread,
    messageCount,
    hasMms,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'thread_cache';
  @override
  VerificationContext validateIntegrity(
    Insertable<ThreadCacheRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('thread_id')) {
      context.handle(
        _threadIdMeta,
        threadId.isAcceptableOrUnknown(data['thread_id']!, _threadIdMeta),
      );
    }
    if (data.containsKey('addresses')) {
      context.handle(
        _addressesMeta,
        addresses.isAcceptableOrUnknown(data['addresses']!, _addressesMeta),
      );
    } else if (isInserting) {
      context.missing(_addressesMeta);
    }
    if (data.containsKey('title')) {
      context.handle(
        _titleMeta,
        title.isAcceptableOrUnknown(data['title']!, _titleMeta),
      );
    } else if (isInserting) {
      context.missing(_titleMeta);
    }
    if (data.containsKey('saved')) {
      context.handle(
        _savedMeta,
        saved.isAcceptableOrUnknown(data['saved']!, _savedMeta),
      );
    }
    if (data.containsKey('photo_uri')) {
      context.handle(
        _photoUriMeta,
        photoUri.isAcceptableOrUnknown(data['photo_uri']!, _photoUriMeta),
      );
    }
    if (data.containsKey('snippet')) {
      context.handle(
        _snippetMeta,
        snippet.isAcceptableOrUnknown(data['snippet']!, _snippetMeta),
      );
    } else if (isInserting) {
      context.missing(_snippetMeta);
    }
    if (data.containsKey('date')) {
      context.handle(
        _dateMeta,
        date.isAcceptableOrUnknown(data['date']!, _dateMeta),
      );
    } else if (isInserting) {
      context.missing(_dateMeta);
    }
    if (data.containsKey('unread')) {
      context.handle(
        _unreadMeta,
        unread.isAcceptableOrUnknown(data['unread']!, _unreadMeta),
      );
    }
    if (data.containsKey('message_count')) {
      context.handle(
        _messageCountMeta,
        messageCount.isAcceptableOrUnknown(
          data['message_count']!,
          _messageCountMeta,
        ),
      );
    }
    if (data.containsKey('has_mms')) {
      context.handle(
        _hasMmsMeta,
        hasMms.isAcceptableOrUnknown(data['has_mms']!, _hasMmsMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {threadId};
  @override
  ThreadCacheRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ThreadCacheRow(
      threadId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}thread_id'],
      )!,
      addresses: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}addresses'],
      )!,
      title: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}title'],
      )!,
      saved: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}saved'],
      )!,
      photoUri: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}photo_uri'],
      ),
      snippet: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}snippet'],
      )!,
      date: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}date'],
      )!,
      unread: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}unread'],
      )!,
      messageCount: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}message_count'],
      )!,
      hasMms: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}has_mms'],
      )!,
    );
  }

  @override
  $ThreadCacheTable createAlias(String alias) {
    return $ThreadCacheTable(attachedDatabase, alias);
  }
}

class ThreadCacheRow extends DataClass implements Insertable<ThreadCacheRow> {
  final int threadId;

  /// JSON list of addresses.
  final String addresses;
  final String title;
  final bool saved;
  final String? photoUri;
  final String snippet;
  final int date;
  final int unread;
  final int messageCount;
  final bool hasMms;
  const ThreadCacheRow({
    required this.threadId,
    required this.addresses,
    required this.title,
    required this.saved,
    this.photoUri,
    required this.snippet,
    required this.date,
    required this.unread,
    required this.messageCount,
    required this.hasMms,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['thread_id'] = Variable<int>(threadId);
    map['addresses'] = Variable<String>(addresses);
    map['title'] = Variable<String>(title);
    map['saved'] = Variable<bool>(saved);
    if (!nullToAbsent || photoUri != null) {
      map['photo_uri'] = Variable<String>(photoUri);
    }
    map['snippet'] = Variable<String>(snippet);
    map['date'] = Variable<int>(date);
    map['unread'] = Variable<int>(unread);
    map['message_count'] = Variable<int>(messageCount);
    map['has_mms'] = Variable<bool>(hasMms);
    return map;
  }

  ThreadCacheCompanion toCompanion(bool nullToAbsent) {
    return ThreadCacheCompanion(
      threadId: Value(threadId),
      addresses: Value(addresses),
      title: Value(title),
      saved: Value(saved),
      photoUri: photoUri == null && nullToAbsent
          ? const Value.absent()
          : Value(photoUri),
      snippet: Value(snippet),
      date: Value(date),
      unread: Value(unread),
      messageCount: Value(messageCount),
      hasMms: Value(hasMms),
    );
  }

  factory ThreadCacheRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ThreadCacheRow(
      threadId: serializer.fromJson<int>(json['threadId']),
      addresses: serializer.fromJson<String>(json['addresses']),
      title: serializer.fromJson<String>(json['title']),
      saved: serializer.fromJson<bool>(json['saved']),
      photoUri: serializer.fromJson<String?>(json['photoUri']),
      snippet: serializer.fromJson<String>(json['snippet']),
      date: serializer.fromJson<int>(json['date']),
      unread: serializer.fromJson<int>(json['unread']),
      messageCount: serializer.fromJson<int>(json['messageCount']),
      hasMms: serializer.fromJson<bool>(json['hasMms']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'threadId': serializer.toJson<int>(threadId),
      'addresses': serializer.toJson<String>(addresses),
      'title': serializer.toJson<String>(title),
      'saved': serializer.toJson<bool>(saved),
      'photoUri': serializer.toJson<String?>(photoUri),
      'snippet': serializer.toJson<String>(snippet),
      'date': serializer.toJson<int>(date),
      'unread': serializer.toJson<int>(unread),
      'messageCount': serializer.toJson<int>(messageCount),
      'hasMms': serializer.toJson<bool>(hasMms),
    };
  }

  ThreadCacheRow copyWith({
    int? threadId,
    String? addresses,
    String? title,
    bool? saved,
    Value<String?> photoUri = const Value.absent(),
    String? snippet,
    int? date,
    int? unread,
    int? messageCount,
    bool? hasMms,
  }) => ThreadCacheRow(
    threadId: threadId ?? this.threadId,
    addresses: addresses ?? this.addresses,
    title: title ?? this.title,
    saved: saved ?? this.saved,
    photoUri: photoUri.present ? photoUri.value : this.photoUri,
    snippet: snippet ?? this.snippet,
    date: date ?? this.date,
    unread: unread ?? this.unread,
    messageCount: messageCount ?? this.messageCount,
    hasMms: hasMms ?? this.hasMms,
  );
  ThreadCacheRow copyWithCompanion(ThreadCacheCompanion data) {
    return ThreadCacheRow(
      threadId: data.threadId.present ? data.threadId.value : this.threadId,
      addresses: data.addresses.present ? data.addresses.value : this.addresses,
      title: data.title.present ? data.title.value : this.title,
      saved: data.saved.present ? data.saved.value : this.saved,
      photoUri: data.photoUri.present ? data.photoUri.value : this.photoUri,
      snippet: data.snippet.present ? data.snippet.value : this.snippet,
      date: data.date.present ? data.date.value : this.date,
      unread: data.unread.present ? data.unread.value : this.unread,
      messageCount: data.messageCount.present
          ? data.messageCount.value
          : this.messageCount,
      hasMms: data.hasMms.present ? data.hasMms.value : this.hasMms,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ThreadCacheRow(')
          ..write('threadId: $threadId, ')
          ..write('addresses: $addresses, ')
          ..write('title: $title, ')
          ..write('saved: $saved, ')
          ..write('photoUri: $photoUri, ')
          ..write('snippet: $snippet, ')
          ..write('date: $date, ')
          ..write('unread: $unread, ')
          ..write('messageCount: $messageCount, ')
          ..write('hasMms: $hasMms')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    threadId,
    addresses,
    title,
    saved,
    photoUri,
    snippet,
    date,
    unread,
    messageCount,
    hasMms,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ThreadCacheRow &&
          other.threadId == this.threadId &&
          other.addresses == this.addresses &&
          other.title == this.title &&
          other.saved == this.saved &&
          other.photoUri == this.photoUri &&
          other.snippet == this.snippet &&
          other.date == this.date &&
          other.unread == this.unread &&
          other.messageCount == this.messageCount &&
          other.hasMms == this.hasMms);
}

class ThreadCacheCompanion extends UpdateCompanion<ThreadCacheRow> {
  final Value<int> threadId;
  final Value<String> addresses;
  final Value<String> title;
  final Value<bool> saved;
  final Value<String?> photoUri;
  final Value<String> snippet;
  final Value<int> date;
  final Value<int> unread;
  final Value<int> messageCount;
  final Value<bool> hasMms;
  const ThreadCacheCompanion({
    this.threadId = const Value.absent(),
    this.addresses = const Value.absent(),
    this.title = const Value.absent(),
    this.saved = const Value.absent(),
    this.photoUri = const Value.absent(),
    this.snippet = const Value.absent(),
    this.date = const Value.absent(),
    this.unread = const Value.absent(),
    this.messageCount = const Value.absent(),
    this.hasMms = const Value.absent(),
  });
  ThreadCacheCompanion.insert({
    this.threadId = const Value.absent(),
    required String addresses,
    required String title,
    this.saved = const Value.absent(),
    this.photoUri = const Value.absent(),
    required String snippet,
    required int date,
    this.unread = const Value.absent(),
    this.messageCount = const Value.absent(),
    this.hasMms = const Value.absent(),
  }) : addresses = Value(addresses),
       title = Value(title),
       snippet = Value(snippet),
       date = Value(date);
  static Insertable<ThreadCacheRow> custom({
    Expression<int>? threadId,
    Expression<String>? addresses,
    Expression<String>? title,
    Expression<bool>? saved,
    Expression<String>? photoUri,
    Expression<String>? snippet,
    Expression<int>? date,
    Expression<int>? unread,
    Expression<int>? messageCount,
    Expression<bool>? hasMms,
  }) {
    return RawValuesInsertable({
      if (threadId != null) 'thread_id': threadId,
      if (addresses != null) 'addresses': addresses,
      if (title != null) 'title': title,
      if (saved != null) 'saved': saved,
      if (photoUri != null) 'photo_uri': photoUri,
      if (snippet != null) 'snippet': snippet,
      if (date != null) 'date': date,
      if (unread != null) 'unread': unread,
      if (messageCount != null) 'message_count': messageCount,
      if (hasMms != null) 'has_mms': hasMms,
    });
  }

  ThreadCacheCompanion copyWith({
    Value<int>? threadId,
    Value<String>? addresses,
    Value<String>? title,
    Value<bool>? saved,
    Value<String?>? photoUri,
    Value<String>? snippet,
    Value<int>? date,
    Value<int>? unread,
    Value<int>? messageCount,
    Value<bool>? hasMms,
  }) {
    return ThreadCacheCompanion(
      threadId: threadId ?? this.threadId,
      addresses: addresses ?? this.addresses,
      title: title ?? this.title,
      saved: saved ?? this.saved,
      photoUri: photoUri ?? this.photoUri,
      snippet: snippet ?? this.snippet,
      date: date ?? this.date,
      unread: unread ?? this.unread,
      messageCount: messageCount ?? this.messageCount,
      hasMms: hasMms ?? this.hasMms,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (threadId.present) {
      map['thread_id'] = Variable<int>(threadId.value);
    }
    if (addresses.present) {
      map['addresses'] = Variable<String>(addresses.value);
    }
    if (title.present) {
      map['title'] = Variable<String>(title.value);
    }
    if (saved.present) {
      map['saved'] = Variable<bool>(saved.value);
    }
    if (photoUri.present) {
      map['photo_uri'] = Variable<String>(photoUri.value);
    }
    if (snippet.present) {
      map['snippet'] = Variable<String>(snippet.value);
    }
    if (date.present) {
      map['date'] = Variable<int>(date.value);
    }
    if (unread.present) {
      map['unread'] = Variable<int>(unread.value);
    }
    if (messageCount.present) {
      map['message_count'] = Variable<int>(messageCount.value);
    }
    if (hasMms.present) {
      map['has_mms'] = Variable<bool>(hasMms.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ThreadCacheCompanion(')
          ..write('threadId: $threadId, ')
          ..write('addresses: $addresses, ')
          ..write('title: $title, ')
          ..write('saved: $saved, ')
          ..write('photoUri: $photoUri, ')
          ..write('snippet: $snippet, ')
          ..write('date: $date, ')
          ..write('unread: $unread, ')
          ..write('messageCount: $messageCount, ')
          ..write('hasMms: $hasMms')
          ..write(')'))
        .toString();
  }
}

class $MessageCacheTable extends MessageCache
    with TableInfo<$MessageCacheTable, MessageCacheRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $MessageCacheTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _kindMeta = const VerificationMeta('kind');
  @override
  late final GeneratedColumn<String> kind = GeneratedColumn<String>(
    'kind',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _providerIdMeta = const VerificationMeta(
    'providerId',
  );
  @override
  late final GeneratedColumn<int> providerId = GeneratedColumn<int>(
    'provider_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _threadIdMeta = const VerificationMeta(
    'threadId',
  );
  @override
  late final GeneratedColumn<int> threadId = GeneratedColumn<int>(
    'thread_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _dateMeta = const VerificationMeta('date');
  @override
  late final GeneratedColumn<int> date = GeneratedColumn<int>(
    'date',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _dataMeta = const VerificationMeta('data');
  @override
  late final GeneratedColumn<String> data = GeneratedColumn<String>(
    'data',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    kind,
    providerId,
    threadId,
    date,
    data,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'message_cache';
  @override
  VerificationContext validateIntegrity(
    Insertable<MessageCacheRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('kind')) {
      context.handle(
        _kindMeta,
        kind.isAcceptableOrUnknown(data['kind']!, _kindMeta),
      );
    } else if (isInserting) {
      context.missing(_kindMeta);
    }
    if (data.containsKey('provider_id')) {
      context.handle(
        _providerIdMeta,
        providerId.isAcceptableOrUnknown(data['provider_id']!, _providerIdMeta),
      );
    } else if (isInserting) {
      context.missing(_providerIdMeta);
    }
    if (data.containsKey('thread_id')) {
      context.handle(
        _threadIdMeta,
        threadId.isAcceptableOrUnknown(data['thread_id']!, _threadIdMeta),
      );
    } else if (isInserting) {
      context.missing(_threadIdMeta);
    }
    if (data.containsKey('date')) {
      context.handle(
        _dateMeta,
        date.isAcceptableOrUnknown(data['date']!, _dateMeta),
      );
    } else if (isInserting) {
      context.missing(_dateMeta);
    }
    if (data.containsKey('data')) {
      context.handle(
        _dataMeta,
        this.data.isAcceptableOrUnknown(data['data']!, _dataMeta),
      );
    } else if (isInserting) {
      context.missing(_dataMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {kind, providerId};
  @override
  MessageCacheRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return MessageCacheRow(
      kind: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}kind'],
      )!,
      providerId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}provider_id'],
      )!,
      threadId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}thread_id'],
      )!,
      date: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}date'],
      )!,
      data: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}data'],
      )!,
    );
  }

  @override
  $MessageCacheTable createAlias(String alias) {
    return $MessageCacheTable(attachedDatabase, alias);
  }
}

class MessageCacheRow extends DataClass implements Insertable<MessageCacheRow> {
  final String kind;
  final int providerId;
  final int threadId;
  final int date;

  /// The ProviderMessage as JSON (addresses, body, status, parts…).
  final String data;
  const MessageCacheRow({
    required this.kind,
    required this.providerId,
    required this.threadId,
    required this.date,
    required this.data,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['kind'] = Variable<String>(kind);
    map['provider_id'] = Variable<int>(providerId);
    map['thread_id'] = Variable<int>(threadId);
    map['date'] = Variable<int>(date);
    map['data'] = Variable<String>(data);
    return map;
  }

  MessageCacheCompanion toCompanion(bool nullToAbsent) {
    return MessageCacheCompanion(
      kind: Value(kind),
      providerId: Value(providerId),
      threadId: Value(threadId),
      date: Value(date),
      data: Value(data),
    );
  }

  factory MessageCacheRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return MessageCacheRow(
      kind: serializer.fromJson<String>(json['kind']),
      providerId: serializer.fromJson<int>(json['providerId']),
      threadId: serializer.fromJson<int>(json['threadId']),
      date: serializer.fromJson<int>(json['date']),
      data: serializer.fromJson<String>(json['data']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'kind': serializer.toJson<String>(kind),
      'providerId': serializer.toJson<int>(providerId),
      'threadId': serializer.toJson<int>(threadId),
      'date': serializer.toJson<int>(date),
      'data': serializer.toJson<String>(data),
    };
  }

  MessageCacheRow copyWith({
    String? kind,
    int? providerId,
    int? threadId,
    int? date,
    String? data,
  }) => MessageCacheRow(
    kind: kind ?? this.kind,
    providerId: providerId ?? this.providerId,
    threadId: threadId ?? this.threadId,
    date: date ?? this.date,
    data: data ?? this.data,
  );
  MessageCacheRow copyWithCompanion(MessageCacheCompanion data) {
    return MessageCacheRow(
      kind: data.kind.present ? data.kind.value : this.kind,
      providerId: data.providerId.present
          ? data.providerId.value
          : this.providerId,
      threadId: data.threadId.present ? data.threadId.value : this.threadId,
      date: data.date.present ? data.date.value : this.date,
      data: data.data.present ? data.data.value : this.data,
    );
  }

  @override
  String toString() {
    return (StringBuffer('MessageCacheRow(')
          ..write('kind: $kind, ')
          ..write('providerId: $providerId, ')
          ..write('threadId: $threadId, ')
          ..write('date: $date, ')
          ..write('data: $data')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(kind, providerId, threadId, date, data);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is MessageCacheRow &&
          other.kind == this.kind &&
          other.providerId == this.providerId &&
          other.threadId == this.threadId &&
          other.date == this.date &&
          other.data == this.data);
}

class MessageCacheCompanion extends UpdateCompanion<MessageCacheRow> {
  final Value<String> kind;
  final Value<int> providerId;
  final Value<int> threadId;
  final Value<int> date;
  final Value<String> data;
  final Value<int> rowid;
  const MessageCacheCompanion({
    this.kind = const Value.absent(),
    this.providerId = const Value.absent(),
    this.threadId = const Value.absent(),
    this.date = const Value.absent(),
    this.data = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  MessageCacheCompanion.insert({
    required String kind,
    required int providerId,
    required int threadId,
    required int date,
    required String data,
    this.rowid = const Value.absent(),
  }) : kind = Value(kind),
       providerId = Value(providerId),
       threadId = Value(threadId),
       date = Value(date),
       data = Value(data);
  static Insertable<MessageCacheRow> custom({
    Expression<String>? kind,
    Expression<int>? providerId,
    Expression<int>? threadId,
    Expression<int>? date,
    Expression<String>? data,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (kind != null) 'kind': kind,
      if (providerId != null) 'provider_id': providerId,
      if (threadId != null) 'thread_id': threadId,
      if (date != null) 'date': date,
      if (data != null) 'data': data,
      if (rowid != null) 'rowid': rowid,
    });
  }

  MessageCacheCompanion copyWith({
    Value<String>? kind,
    Value<int>? providerId,
    Value<int>? threadId,
    Value<int>? date,
    Value<String>? data,
    Value<int>? rowid,
  }) {
    return MessageCacheCompanion(
      kind: kind ?? this.kind,
      providerId: providerId ?? this.providerId,
      threadId: threadId ?? this.threadId,
      date: date ?? this.date,
      data: data ?? this.data,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (kind.present) {
      map['kind'] = Variable<String>(kind.value);
    }
    if (providerId.present) {
      map['provider_id'] = Variable<int>(providerId.value);
    }
    if (threadId.present) {
      map['thread_id'] = Variable<int>(threadId.value);
    }
    if (date.present) {
      map['date'] = Variable<int>(date.value);
    }
    if (data.present) {
      map['data'] = Variable<String>(data.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('MessageCacheCompanion(')
          ..write('kind: $kind, ')
          ..write('providerId: $providerId, ')
          ..write('threadId: $threadId, ')
          ..write('date: $date, ')
          ..write('data: $data, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $SyncEventsTable syncEvents = $SyncEventsTable(this);
  late final $OutboundStatesTable outboundStates = $OutboundStatesTable(this);
  late final $ConversationPrefsTable conversationPrefs =
      $ConversationPrefsTable(this);
  late final $StarredMessagesTable starredMessages = $StarredMessagesTable(
    this,
  );
  late final $DraftsTable drafts = $DraftsTable(this);
  late final $ScheduledSendsTable scheduledSends = $ScheduledSendsTable(this);
  late final $PendingMediaTable pendingMedia = $PendingMediaTable(this);
  late final $KeyValuesTable keyValues = $KeyValuesTable(this);
  late final $ThreadCacheTable threadCache = $ThreadCacheTable(this);
  late final $MessageCacheTable messageCache = $MessageCacheTable(this);
  late final Index messageCacheThreadDate = Index(
    'message_cache_thread_date',
    'CREATE INDEX message_cache_thread_date ON message_cache (thread_id, date)',
  );
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    syncEvents,
    outboundStates,
    conversationPrefs,
    starredMessages,
    drafts,
    scheduledSends,
    pendingMedia,
    keyValues,
    threadCache,
    messageCache,
    messageCacheThreadDate,
  ];
}

typedef $$SyncEventsTableCreateCompanionBuilder = SyncEventsCompanion Function({
  Value<int> seq,
  required String type,
  required String payload,
  required int createdAt,
});
typedef $$SyncEventsTableUpdateCompanionBuilder = SyncEventsCompanion Function({
  Value<int> seq,
  Value<String> type,
  Value<String> payload,
  Value<int> createdAt,
});

class $$SyncEventsTableFilterComposer
    extends Composer<_$AppDatabase, $SyncEventsTable> {
  $$SyncEventsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get seq => $composableBuilder(
    column: $table.seq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get type => $composableBuilder(
    column: $table.type,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );
}

class $$SyncEventsTableOrderingComposer
    extends Composer<_$AppDatabase, $SyncEventsTable> {
  $$SyncEventsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get seq => $composableBuilder(
    column: $table.seq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get type => $composableBuilder(
    column: $table.type,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$SyncEventsTableAnnotationComposer
    extends Composer<_$AppDatabase, $SyncEventsTable> {
  $$SyncEventsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get seq =>
      $composableBuilder(column: $table.seq, builder: (column) => column);

  GeneratedColumn<String> get type =>
      $composableBuilder(column: $table.type, builder: (column) => column);

  GeneratedColumn<String> get payload =>
      $composableBuilder(column: $table.payload, builder: (column) => column);

  GeneratedColumn<int> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);
}

class $$SyncEventsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $SyncEventsTable,
          SyncEventRow,
          $$SyncEventsTableFilterComposer,
          $$SyncEventsTableOrderingComposer,
          $$SyncEventsTableAnnotationComposer,
          $$SyncEventsTableCreateCompanionBuilder,
          $$SyncEventsTableUpdateCompanionBuilder,
          (
            SyncEventRow,
            BaseReferences<_$AppDatabase, $SyncEventsTable, SyncEventRow>,
          ),
          SyncEventRow,
          PrefetchHooks Function()
        > {
  $$SyncEventsTableTableManager(_$AppDatabase db, $SyncEventsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SyncEventsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SyncEventsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SyncEventsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> seq = const Value.absent(),
                Value<String> type = const Value.absent(),
                Value<String> payload = const Value.absent(),
                Value<int> createdAt = const Value.absent(),
              }) => SyncEventsCompanion(
                seq: seq,
                type: type,
                payload: payload,
                createdAt: createdAt,
              ),
          createCompanionCallback:
              ({
                Value<int> seq = const Value.absent(),
                required String type,
                required String payload,
                required int createdAt,
              }) => SyncEventsCompanion.insert(
                seq: seq,
                type: type,
                payload: payload,
                createdAt: createdAt,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$SyncEventsTable, SyncEventRow>(table),
                  BaseReferences<_$AppDatabase, $SyncEventsTable, SyncEventRow>(
                    db,
                    table,
                    e,
                  ),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$SyncEventsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $SyncEventsTable,
      SyncEventRow,
      $$SyncEventsTableFilterComposer,
      $$SyncEventsTableOrderingComposer,
      $$SyncEventsTableAnnotationComposer,
      $$SyncEventsTableCreateCompanionBuilder,
      $$SyncEventsTableUpdateCompanionBuilder,
      (
        SyncEventRow,
        BaseReferences<_$AppDatabase, $SyncEventsTable, SyncEventRow>,
      ),
      SyncEventRow,
      PrefetchHooks Function()
    >;
typedef $$OutboundStatesTableCreateCompanionBuilder =
    OutboundStatesCompanion Function({
      required String clientUuid,
      required String state,
      Value<int?> providerId,
      Value<int?> errorCode,
      Value<int?> parts,
      required int updatedAt,
      Value<String?> reportedState,
      Value<String?> sentBy,
      Value<int> rowid,
    });
typedef $$OutboundStatesTableUpdateCompanionBuilder =
    OutboundStatesCompanion Function({
      Value<String> clientUuid,
      Value<String> state,
      Value<int?> providerId,
      Value<int?> errorCode,
      Value<int?> parts,
      Value<int> updatedAt,
      Value<String?> reportedState,
      Value<String?> sentBy,
      Value<int> rowid,
    });

class $$OutboundStatesTableFilterComposer
    extends Composer<_$AppDatabase, $OutboundStatesTable> {
  $$OutboundStatesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get errorCode => $composableBuilder(
    column: $table.errorCode,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get parts => $composableBuilder(
    column: $table.parts,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get reportedState => $composableBuilder(
    column: $table.reportedState,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get sentBy => $composableBuilder(
    column: $table.sentBy,
    builder: (column) => ColumnFilters(column),
  );
}

class $$OutboundStatesTableOrderingComposer
    extends Composer<_$AppDatabase, $OutboundStatesTable> {
  $$OutboundStatesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get errorCode => $composableBuilder(
    column: $table.errorCode,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get parts => $composableBuilder(
    column: $table.parts,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get reportedState => $composableBuilder(
    column: $table.reportedState,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get sentBy => $composableBuilder(
    column: $table.sentBy,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$OutboundStatesTableAnnotationComposer
    extends Composer<_$AppDatabase, $OutboundStatesTable> {
  $$OutboundStatesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => column,
  );

  GeneratedColumn<String> get state =>
      $composableBuilder(column: $table.state, builder: (column) => column);

  GeneratedColumn<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get errorCode =>
      $composableBuilder(column: $table.errorCode, builder: (column) => column);

  GeneratedColumn<int> get parts =>
      $composableBuilder(column: $table.parts, builder: (column) => column);

  GeneratedColumn<int> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);

  GeneratedColumn<String> get reportedState => $composableBuilder(
    column: $table.reportedState,
    builder: (column) => column,
  );

  GeneratedColumn<String> get sentBy =>
      $composableBuilder(column: $table.sentBy, builder: (column) => column);
}

class $$OutboundStatesTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $OutboundStatesTable,
          OutboundStateRow,
          $$OutboundStatesTableFilterComposer,
          $$OutboundStatesTableOrderingComposer,
          $$OutboundStatesTableAnnotationComposer,
          $$OutboundStatesTableCreateCompanionBuilder,
          $$OutboundStatesTableUpdateCompanionBuilder,
          (
            OutboundStateRow,
            BaseReferences<
              _$AppDatabase,
              $OutboundStatesTable,
              OutboundStateRow
            >,
          ),
          OutboundStateRow,
          PrefetchHooks Function()
        > {
  $$OutboundStatesTableTableManager(
    _$AppDatabase db,
    $OutboundStatesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$OutboundStatesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$OutboundStatesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$OutboundStatesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> clientUuid = const Value.absent(),
                Value<String> state = const Value.absent(),
                Value<int?> providerId = const Value.absent(),
                Value<int?> errorCode = const Value.absent(),
                Value<int?> parts = const Value.absent(),
                Value<int> updatedAt = const Value.absent(),
                Value<String?> reportedState = const Value.absent(),
                Value<String?> sentBy = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => OutboundStatesCompanion(
                clientUuid: clientUuid,
                state: state,
                providerId: providerId,
                errorCode: errorCode,
                parts: parts,
                updatedAt: updatedAt,
                reportedState: reportedState,
                sentBy: sentBy,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String clientUuid,
                required String state,
                Value<int?> providerId = const Value.absent(),
                Value<int?> errorCode = const Value.absent(),
                Value<int?> parts = const Value.absent(),
                required int updatedAt,
                Value<String?> reportedState = const Value.absent(),
                Value<String?> sentBy = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => OutboundStatesCompanion.insert(
                clientUuid: clientUuid,
                state: state,
                providerId: providerId,
                errorCode: errorCode,
                parts: parts,
                updatedAt: updatedAt,
                reportedState: reportedState,
                sentBy: sentBy,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$OutboundStatesTable, OutboundStateRow>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $OutboundStatesTable,
                    OutboundStateRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$OutboundStatesTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $OutboundStatesTable,
      OutboundStateRow,
      $$OutboundStatesTableFilterComposer,
      $$OutboundStatesTableOrderingComposer,
      $$OutboundStatesTableAnnotationComposer,
      $$OutboundStatesTableCreateCompanionBuilder,
      $$OutboundStatesTableUpdateCompanionBuilder,
      (
        OutboundStateRow,
        BaseReferences<_$AppDatabase, $OutboundStatesTable, OutboundStateRow>,
      ),
      OutboundStateRow,
      PrefetchHooks Function()
    >;
typedef $$ConversationPrefsTableCreateCompanionBuilder =
    ConversationPrefsCompanion Function({
      Value<int> threadId,
      Value<bool> pinned,
      Value<bool> archived,
      Value<bool> muted,
      Value<bool> spam,
    });
typedef $$ConversationPrefsTableUpdateCompanionBuilder =
    ConversationPrefsCompanion Function({
      Value<int> threadId,
      Value<bool> pinned,
      Value<bool> archived,
      Value<bool> muted,
      Value<bool> spam,
    });

class $$ConversationPrefsTableFilterComposer
    extends Composer<_$AppDatabase, $ConversationPrefsTable> {
  $$ConversationPrefsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get threadId => $composableBuilder(
    column: $table.threadId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get pinned => $composableBuilder(
    column: $table.pinned,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get archived => $composableBuilder(
    column: $table.archived,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get muted => $composableBuilder(
    column: $table.muted,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get spam => $composableBuilder(
    column: $table.spam,
    builder: (column) => ColumnFilters(column),
  );
}

class $$ConversationPrefsTableOrderingComposer
    extends Composer<_$AppDatabase, $ConversationPrefsTable> {
  $$ConversationPrefsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get threadId => $composableBuilder(
    column: $table.threadId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get pinned => $composableBuilder(
    column: $table.pinned,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get archived => $composableBuilder(
    column: $table.archived,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get muted => $composableBuilder(
    column: $table.muted,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get spam => $composableBuilder(
    column: $table.spam,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$ConversationPrefsTableAnnotationComposer
    extends Composer<_$AppDatabase, $ConversationPrefsTable> {
  $$ConversationPrefsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get threadId =>
      $composableBuilder(column: $table.threadId, builder: (column) => column);

  GeneratedColumn<bool> get pinned =>
      $composableBuilder(column: $table.pinned, builder: (column) => column);

  GeneratedColumn<bool> get archived =>
      $composableBuilder(column: $table.archived, builder: (column) => column);

  GeneratedColumn<bool> get muted =>
      $composableBuilder(column: $table.muted, builder: (column) => column);

  GeneratedColumn<bool> get spam =>
      $composableBuilder(column: $table.spam, builder: (column) => column);
}

class $$ConversationPrefsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $ConversationPrefsTable,
          ConversationPrefRow,
          $$ConversationPrefsTableFilterComposer,
          $$ConversationPrefsTableOrderingComposer,
          $$ConversationPrefsTableAnnotationComposer,
          $$ConversationPrefsTableCreateCompanionBuilder,
          $$ConversationPrefsTableUpdateCompanionBuilder,
          (
            ConversationPrefRow,
            BaseReferences<
              _$AppDatabase,
              $ConversationPrefsTable,
              ConversationPrefRow
            >,
          ),
          ConversationPrefRow,
          PrefetchHooks Function()
        > {
  $$ConversationPrefsTableTableManager(
    _$AppDatabase db,
    $ConversationPrefsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ConversationPrefsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ConversationPrefsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ConversationPrefsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> threadId = const Value.absent(),
                Value<bool> pinned = const Value.absent(),
                Value<bool> archived = const Value.absent(),
                Value<bool> muted = const Value.absent(),
                Value<bool> spam = const Value.absent(),
              }) => ConversationPrefsCompanion(
                threadId: threadId,
                pinned: pinned,
                archived: archived,
                muted: muted,
                spam: spam,
              ),
          createCompanionCallback:
              ({
                Value<int> threadId = const Value.absent(),
                Value<bool> pinned = const Value.absent(),
                Value<bool> archived = const Value.absent(),
                Value<bool> muted = const Value.absent(),
                Value<bool> spam = const Value.absent(),
              }) => ConversationPrefsCompanion.insert(
                threadId: threadId,
                pinned: pinned,
                archived: archived,
                muted: muted,
                spam: spam,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$ConversationPrefsTable, ConversationPrefRow>(
                    table,
                  ),
                  BaseReferences<
                    _$AppDatabase,
                    $ConversationPrefsTable,
                    ConversationPrefRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$ConversationPrefsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $ConversationPrefsTable,
      ConversationPrefRow,
      $$ConversationPrefsTableFilterComposer,
      $$ConversationPrefsTableOrderingComposer,
      $$ConversationPrefsTableAnnotationComposer,
      $$ConversationPrefsTableCreateCompanionBuilder,
      $$ConversationPrefsTableUpdateCompanionBuilder,
      (
        ConversationPrefRow,
        BaseReferences<
          _$AppDatabase,
          $ConversationPrefsTable,
          ConversationPrefRow
        >,
      ),
      ConversationPrefRow,
      PrefetchHooks Function()
    >;
typedef $$StarredMessagesTableCreateCompanionBuilder =
    StarredMessagesCompanion Function({
      required String kind,
      required int providerId,
      Value<int> rowid,
    });
typedef $$StarredMessagesTableUpdateCompanionBuilder =
    StarredMessagesCompanion Function({
      Value<String> kind,
      Value<int> providerId,
      Value<int> rowid,
    });

class $$StarredMessagesTableFilterComposer
    extends Composer<_$AppDatabase, $StarredMessagesTable> {
  $$StarredMessagesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnFilters(column),
  );
}

class $$StarredMessagesTableOrderingComposer
    extends Composer<_$AppDatabase, $StarredMessagesTable> {
  $$StarredMessagesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$StarredMessagesTableAnnotationComposer
    extends Composer<_$AppDatabase, $StarredMessagesTable> {
  $$StarredMessagesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get kind =>
      $composableBuilder(column: $table.kind, builder: (column) => column);

  GeneratedColumn<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => column,
  );
}

class $$StarredMessagesTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $StarredMessagesTable,
          StarredRow,
          $$StarredMessagesTableFilterComposer,
          $$StarredMessagesTableOrderingComposer,
          $$StarredMessagesTableAnnotationComposer,
          $$StarredMessagesTableCreateCompanionBuilder,
          $$StarredMessagesTableUpdateCompanionBuilder,
          (
            StarredRow,
            BaseReferences<_$AppDatabase, $StarredMessagesTable, StarredRow>,
          ),
          StarredRow,
          PrefetchHooks Function()
        > {
  $$StarredMessagesTableTableManager(
    _$AppDatabase db,
    $StarredMessagesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$StarredMessagesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$StarredMessagesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$StarredMessagesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> kind = const Value.absent(),
                Value<int> providerId = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => StarredMessagesCompanion(
                kind: kind,
                providerId: providerId,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String kind,
                required int providerId,
                Value<int> rowid = const Value.absent(),
              }) => StarredMessagesCompanion.insert(
                kind: kind,
                providerId: providerId,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$StarredMessagesTable, StarredRow>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $StarredMessagesTable,
                    StarredRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$StarredMessagesTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $StarredMessagesTable,
      StarredRow,
      $$StarredMessagesTableFilterComposer,
      $$StarredMessagesTableOrderingComposer,
      $$StarredMessagesTableAnnotationComposer,
      $$StarredMessagesTableCreateCompanionBuilder,
      $$StarredMessagesTableUpdateCompanionBuilder,
      (
        StarredRow,
        BaseReferences<_$AppDatabase, $StarredMessagesTable, StarredRow>,
      ),
      StarredRow,
      PrefetchHooks Function()
    >;
typedef $$DraftsTableCreateCompanionBuilder = DraftsCompanion Function({
  required String key,
  required String body,
  required int updatedAt,
  Value<int> rowid,
});
typedef $$DraftsTableUpdateCompanionBuilder = DraftsCompanion Function({
  Value<String> key,
  Value<String> body,
  Value<int> updatedAt,
  Value<int> rowid,
});

class $$DraftsTableFilterComposer
    extends Composer<_$AppDatabase, $DraftsTable> {
  $$DraftsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );
}

class $$DraftsTableOrderingComposer
    extends Composer<_$AppDatabase, $DraftsTable> {
  $$DraftsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$DraftsTableAnnotationComposer
    extends Composer<_$AppDatabase, $DraftsTable> {
  $$DraftsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get key =>
      $composableBuilder(column: $table.key, builder: (column) => column);

  GeneratedColumn<String> get body =>
      $composableBuilder(column: $table.body, builder: (column) => column);

  GeneratedColumn<int> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);
}

class $$DraftsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $DraftsTable,
          DraftRow,
          $$DraftsTableFilterComposer,
          $$DraftsTableOrderingComposer,
          $$DraftsTableAnnotationComposer,
          $$DraftsTableCreateCompanionBuilder,
          $$DraftsTableUpdateCompanionBuilder,
          (DraftRow, BaseReferences<_$AppDatabase, $DraftsTable, DraftRow>),
          DraftRow,
          PrefetchHooks Function()
        > {
  $$DraftsTableTableManager(_$AppDatabase db, $DraftsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$DraftsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$DraftsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$DraftsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> key = const Value.absent(),
                Value<String> body = const Value.absent(),
                Value<int> updatedAt = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => DraftsCompanion(
                key: key,
                body: body,
                updatedAt: updatedAt,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String key,
                required String body,
                required int updatedAt,
                Value<int> rowid = const Value.absent(),
              }) => DraftsCompanion.insert(
                key: key,
                body: body,
                updatedAt: updatedAt,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$DraftsTable, DraftRow>(table),
                  BaseReferences<_$AppDatabase, $DraftsTable, DraftRow>(
                    db,
                    table,
                    e,
                  ),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$DraftsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $DraftsTable,
      DraftRow,
      $$DraftsTableFilterComposer,
      $$DraftsTableOrderingComposer,
      $$DraftsTableAnnotationComposer,
      $$DraftsTableCreateCompanionBuilder,
      $$DraftsTableUpdateCompanionBuilder,
      (DraftRow, BaseReferences<_$AppDatabase, $DraftsTable, DraftRow>),
      DraftRow,
      PrefetchHooks Function()
    >;
typedef $$ScheduledSendsTableCreateCompanionBuilder =
    ScheduledSendsCompanion Function({
      required String clientUuid,
      required String addresses,
      required String body,
      Value<int?> subscriptionId,
      required int sendAt,
      Value<int> rowid,
    });
typedef $$ScheduledSendsTableUpdateCompanionBuilder =
    ScheduledSendsCompanion Function({
      Value<String> clientUuid,
      Value<String> addresses,
      Value<String> body,
      Value<int?> subscriptionId,
      Value<int> sendAt,
      Value<int> rowid,
    });

class $$ScheduledSendsTableFilterComposer
    extends Composer<_$AppDatabase, $ScheduledSendsTable> {
  $$ScheduledSendsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get addresses => $composableBuilder(
    column: $table.addresses,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get subscriptionId => $composableBuilder(
    column: $table.subscriptionId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get sendAt => $composableBuilder(
    column: $table.sendAt,
    builder: (column) => ColumnFilters(column),
  );
}

class $$ScheduledSendsTableOrderingComposer
    extends Composer<_$AppDatabase, $ScheduledSendsTable> {
  $$ScheduledSendsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get addresses => $composableBuilder(
    column: $table.addresses,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get subscriptionId => $composableBuilder(
    column: $table.subscriptionId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get sendAt => $composableBuilder(
    column: $table.sendAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$ScheduledSendsTableAnnotationComposer
    extends Composer<_$AppDatabase, $ScheduledSendsTable> {
  $$ScheduledSendsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => column,
  );

  GeneratedColumn<String> get addresses =>
      $composableBuilder(column: $table.addresses, builder: (column) => column);

  GeneratedColumn<String> get body =>
      $composableBuilder(column: $table.body, builder: (column) => column);

  GeneratedColumn<int> get subscriptionId => $composableBuilder(
    column: $table.subscriptionId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get sendAt =>
      $composableBuilder(column: $table.sendAt, builder: (column) => column);
}

class $$ScheduledSendsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $ScheduledSendsTable,
          ScheduledRow,
          $$ScheduledSendsTableFilterComposer,
          $$ScheduledSendsTableOrderingComposer,
          $$ScheduledSendsTableAnnotationComposer,
          $$ScheduledSendsTableCreateCompanionBuilder,
          $$ScheduledSendsTableUpdateCompanionBuilder,
          (
            ScheduledRow,
            BaseReferences<_$AppDatabase, $ScheduledSendsTable, ScheduledRow>,
          ),
          ScheduledRow,
          PrefetchHooks Function()
        > {
  $$ScheduledSendsTableTableManager(
    _$AppDatabase db,
    $ScheduledSendsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ScheduledSendsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ScheduledSendsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ScheduledSendsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> clientUuid = const Value.absent(),
                Value<String> addresses = const Value.absent(),
                Value<String> body = const Value.absent(),
                Value<int?> subscriptionId = const Value.absent(),
                Value<int> sendAt = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ScheduledSendsCompanion(
                clientUuid: clientUuid,
                addresses: addresses,
                body: body,
                subscriptionId: subscriptionId,
                sendAt: sendAt,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String clientUuid,
                required String addresses,
                required String body,
                Value<int?> subscriptionId = const Value.absent(),
                required int sendAt,
                Value<int> rowid = const Value.absent(),
              }) => ScheduledSendsCompanion.insert(
                clientUuid: clientUuid,
                addresses: addresses,
                body: body,
                subscriptionId: subscriptionId,
                sendAt: sendAt,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$ScheduledSendsTable, ScheduledRow>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $ScheduledSendsTable,
                    ScheduledRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$ScheduledSendsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $ScheduledSendsTable,
      ScheduledRow,
      $$ScheduledSendsTableFilterComposer,
      $$ScheduledSendsTableOrderingComposer,
      $$ScheduledSendsTableAnnotationComposer,
      $$ScheduledSendsTableCreateCompanionBuilder,
      $$ScheduledSendsTableUpdateCompanionBuilder,
      (
        ScheduledRow,
        BaseReferences<_$AppDatabase, $ScheduledSendsTable, ScheduledRow>,
      ),
      ScheduledRow,
      PrefetchHooks Function()
    >;
typedef $$PendingMediaTableCreateCompanionBuilder =
    PendingMediaCompanion Function({
      required int providerId,
      required int date,
      required int seq,
      required String uri,
      required int size,
      Value<int> offset,
      Value<int> rowid,
    });
typedef $$PendingMediaTableUpdateCompanionBuilder =
    PendingMediaCompanion Function({
      Value<int> providerId,
      Value<int> date,
      Value<int> seq,
      Value<String> uri,
      Value<int> size,
      Value<int> offset,
      Value<int> rowid,
    });

class $$PendingMediaTableFilterComposer
    extends Composer<_$AppDatabase, $PendingMediaTable> {
  $$PendingMediaTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get date => $composableBuilder(
    column: $table.date,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get seq => $composableBuilder(
    column: $table.seq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get uri => $composableBuilder(
    column: $table.uri,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get size => $composableBuilder(
    column: $table.size,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get offset => $composableBuilder(
    column: $table.offset,
    builder: (column) => ColumnFilters(column),
  );
}

class $$PendingMediaTableOrderingComposer
    extends Composer<_$AppDatabase, $PendingMediaTable> {
  $$PendingMediaTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get date => $composableBuilder(
    column: $table.date,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get seq => $composableBuilder(
    column: $table.seq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get uri => $composableBuilder(
    column: $table.uri,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get size => $composableBuilder(
    column: $table.size,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get offset => $composableBuilder(
    column: $table.offset,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$PendingMediaTableAnnotationComposer
    extends Composer<_$AppDatabase, $PendingMediaTable> {
  $$PendingMediaTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get date =>
      $composableBuilder(column: $table.date, builder: (column) => column);

  GeneratedColumn<int> get seq =>
      $composableBuilder(column: $table.seq, builder: (column) => column);

  GeneratedColumn<String> get uri =>
      $composableBuilder(column: $table.uri, builder: (column) => column);

  GeneratedColumn<int> get size =>
      $composableBuilder(column: $table.size, builder: (column) => column);

  GeneratedColumn<int> get offset =>
      $composableBuilder(column: $table.offset, builder: (column) => column);
}

class $$PendingMediaTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $PendingMediaTable,
          PendingMediaRow,
          $$PendingMediaTableFilterComposer,
          $$PendingMediaTableOrderingComposer,
          $$PendingMediaTableAnnotationComposer,
          $$PendingMediaTableCreateCompanionBuilder,
          $$PendingMediaTableUpdateCompanionBuilder,
          (
            PendingMediaRow,
            BaseReferences<_$AppDatabase, $PendingMediaTable, PendingMediaRow>,
          ),
          PendingMediaRow,
          PrefetchHooks Function()
        > {
  $$PendingMediaTableTableManager(_$AppDatabase db, $PendingMediaTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$PendingMediaTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$PendingMediaTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$PendingMediaTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> providerId = const Value.absent(),
                Value<int> date = const Value.absent(),
                Value<int> seq = const Value.absent(),
                Value<String> uri = const Value.absent(),
                Value<int> size = const Value.absent(),
                Value<int> offset = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => PendingMediaCompanion(
                providerId: providerId,
                date: date,
                seq: seq,
                uri: uri,
                size: size,
                offset: offset,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required int providerId,
                required int date,
                required int seq,
                required String uri,
                required int size,
                Value<int> offset = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => PendingMediaCompanion.insert(
                providerId: providerId,
                date: date,
                seq: seq,
                uri: uri,
                size: size,
                offset: offset,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$PendingMediaTable, PendingMediaRow>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $PendingMediaTable,
                    PendingMediaRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$PendingMediaTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $PendingMediaTable,
      PendingMediaRow,
      $$PendingMediaTableFilterComposer,
      $$PendingMediaTableOrderingComposer,
      $$PendingMediaTableAnnotationComposer,
      $$PendingMediaTableCreateCompanionBuilder,
      $$PendingMediaTableUpdateCompanionBuilder,
      (
        PendingMediaRow,
        BaseReferences<_$AppDatabase, $PendingMediaTable, PendingMediaRow>,
      ),
      PendingMediaRow,
      PrefetchHooks Function()
    >;
typedef $$KeyValuesTableCreateCompanionBuilder = KeyValuesCompanion Function({
  required String key,
  required String value,
  Value<int> rowid,
});
typedef $$KeyValuesTableUpdateCompanionBuilder = KeyValuesCompanion Function({
  Value<String> key,
  Value<String> value,
  Value<int> rowid,
});

class $$KeyValuesTableFilterComposer
    extends Composer<_$AppDatabase, $KeyValuesTable> {
  $$KeyValuesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get value => $composableBuilder(
    column: $table.value,
    builder: (column) => ColumnFilters(column),
  );
}

class $$KeyValuesTableOrderingComposer
    extends Composer<_$AppDatabase, $KeyValuesTable> {
  $$KeyValuesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get value => $composableBuilder(
    column: $table.value,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$KeyValuesTableAnnotationComposer
    extends Composer<_$AppDatabase, $KeyValuesTable> {
  $$KeyValuesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get key =>
      $composableBuilder(column: $table.key, builder: (column) => column);

  GeneratedColumn<String> get value =>
      $composableBuilder(column: $table.value, builder: (column) => column);
}

class $$KeyValuesTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $KeyValuesTable,
          KvRow,
          $$KeyValuesTableFilterComposer,
          $$KeyValuesTableOrderingComposer,
          $$KeyValuesTableAnnotationComposer,
          $$KeyValuesTableCreateCompanionBuilder,
          $$KeyValuesTableUpdateCompanionBuilder,
          (KvRow, BaseReferences<_$AppDatabase, $KeyValuesTable, KvRow>),
          KvRow,
          PrefetchHooks Function()
        > {
  $$KeyValuesTableTableManager(_$AppDatabase db, $KeyValuesTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$KeyValuesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$KeyValuesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$KeyValuesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> key = const Value.absent(),
            Value<String> value = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) => KeyValuesCompanion(key: key, value: value, rowid: rowid),
          createCompanionCallback: ({
            required String key,
            required String value,
            Value<int> rowid = const Value.absent(),
          }) => KeyValuesCompanion.insert(key: key, value: value, rowid: rowid),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$KeyValuesTable, KvRow>(table),
                  BaseReferences<_$AppDatabase, $KeyValuesTable, KvRow>(
                    db,
                    table,
                    e,
                  ),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$KeyValuesTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $KeyValuesTable,
      KvRow,
      $$KeyValuesTableFilterComposer,
      $$KeyValuesTableOrderingComposer,
      $$KeyValuesTableAnnotationComposer,
      $$KeyValuesTableCreateCompanionBuilder,
      $$KeyValuesTableUpdateCompanionBuilder,
      (KvRow, BaseReferences<_$AppDatabase, $KeyValuesTable, KvRow>),
      KvRow,
      PrefetchHooks Function()
    >;
typedef $$ThreadCacheTableCreateCompanionBuilder =
    ThreadCacheCompanion Function({
      Value<int> threadId,
      required String addresses,
      required String title,
      Value<bool> saved,
      Value<String?> photoUri,
      required String snippet,
      required int date,
      Value<int> unread,
      Value<int> messageCount,
      Value<bool> hasMms,
    });
typedef $$ThreadCacheTableUpdateCompanionBuilder =
    ThreadCacheCompanion Function({
      Value<int> threadId,
      Value<String> addresses,
      Value<String> title,
      Value<bool> saved,
      Value<String?> photoUri,
      Value<String> snippet,
      Value<int> date,
      Value<int> unread,
      Value<int> messageCount,
      Value<bool> hasMms,
    });

class $$ThreadCacheTableFilterComposer
    extends Composer<_$AppDatabase, $ThreadCacheTable> {
  $$ThreadCacheTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get threadId => $composableBuilder(
    column: $table.threadId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get addresses => $composableBuilder(
    column: $table.addresses,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get saved => $composableBuilder(
    column: $table.saved,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get photoUri => $composableBuilder(
    column: $table.photoUri,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get snippet => $composableBuilder(
    column: $table.snippet,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get date => $composableBuilder(
    column: $table.date,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get unread => $composableBuilder(
    column: $table.unread,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get messageCount => $composableBuilder(
    column: $table.messageCount,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get hasMms => $composableBuilder(
    column: $table.hasMms,
    builder: (column) => ColumnFilters(column),
  );
}

class $$ThreadCacheTableOrderingComposer
    extends Composer<_$AppDatabase, $ThreadCacheTable> {
  $$ThreadCacheTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get threadId => $composableBuilder(
    column: $table.threadId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get addresses => $composableBuilder(
    column: $table.addresses,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get saved => $composableBuilder(
    column: $table.saved,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get photoUri => $composableBuilder(
    column: $table.photoUri,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get snippet => $composableBuilder(
    column: $table.snippet,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get date => $composableBuilder(
    column: $table.date,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get unread => $composableBuilder(
    column: $table.unread,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get messageCount => $composableBuilder(
    column: $table.messageCount,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get hasMms => $composableBuilder(
    column: $table.hasMms,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$ThreadCacheTableAnnotationComposer
    extends Composer<_$AppDatabase, $ThreadCacheTable> {
  $$ThreadCacheTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get threadId =>
      $composableBuilder(column: $table.threadId, builder: (column) => column);

  GeneratedColumn<String> get addresses =>
      $composableBuilder(column: $table.addresses, builder: (column) => column);

  GeneratedColumn<String> get title =>
      $composableBuilder(column: $table.title, builder: (column) => column);

  GeneratedColumn<bool> get saved =>
      $composableBuilder(column: $table.saved, builder: (column) => column);

  GeneratedColumn<String> get photoUri =>
      $composableBuilder(column: $table.photoUri, builder: (column) => column);

  GeneratedColumn<String> get snippet =>
      $composableBuilder(column: $table.snippet, builder: (column) => column);

  GeneratedColumn<int> get date =>
      $composableBuilder(column: $table.date, builder: (column) => column);

  GeneratedColumn<int> get unread =>
      $composableBuilder(column: $table.unread, builder: (column) => column);

  GeneratedColumn<int> get messageCount => $composableBuilder(
    column: $table.messageCount,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get hasMms =>
      $composableBuilder(column: $table.hasMms, builder: (column) => column);
}

class $$ThreadCacheTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $ThreadCacheTable,
          ThreadCacheRow,
          $$ThreadCacheTableFilterComposer,
          $$ThreadCacheTableOrderingComposer,
          $$ThreadCacheTableAnnotationComposer,
          $$ThreadCacheTableCreateCompanionBuilder,
          $$ThreadCacheTableUpdateCompanionBuilder,
          (
            ThreadCacheRow,
            BaseReferences<_$AppDatabase, $ThreadCacheTable, ThreadCacheRow>,
          ),
          ThreadCacheRow,
          PrefetchHooks Function()
        > {
  $$ThreadCacheTableTableManager(_$AppDatabase db, $ThreadCacheTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ThreadCacheTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ThreadCacheTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ThreadCacheTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> threadId = const Value.absent(),
                Value<String> addresses = const Value.absent(),
                Value<String> title = const Value.absent(),
                Value<bool> saved = const Value.absent(),
                Value<String?> photoUri = const Value.absent(),
                Value<String> snippet = const Value.absent(),
                Value<int> date = const Value.absent(),
                Value<int> unread = const Value.absent(),
                Value<int> messageCount = const Value.absent(),
                Value<bool> hasMms = const Value.absent(),
              }) => ThreadCacheCompanion(
                threadId: threadId,
                addresses: addresses,
                title: title,
                saved: saved,
                photoUri: photoUri,
                snippet: snippet,
                date: date,
                unread: unread,
                messageCount: messageCount,
                hasMms: hasMms,
              ),
          createCompanionCallback:
              ({
                Value<int> threadId = const Value.absent(),
                required String addresses,
                required String title,
                Value<bool> saved = const Value.absent(),
                Value<String?> photoUri = const Value.absent(),
                required String snippet,
                required int date,
                Value<int> unread = const Value.absent(),
                Value<int> messageCount = const Value.absent(),
                Value<bool> hasMms = const Value.absent(),
              }) => ThreadCacheCompanion.insert(
                threadId: threadId,
                addresses: addresses,
                title: title,
                saved: saved,
                photoUri: photoUri,
                snippet: snippet,
                date: date,
                unread: unread,
                messageCount: messageCount,
                hasMms: hasMms,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$ThreadCacheTable, ThreadCacheRow>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $ThreadCacheTable,
                    ThreadCacheRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$ThreadCacheTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $ThreadCacheTable,
      ThreadCacheRow,
      $$ThreadCacheTableFilterComposer,
      $$ThreadCacheTableOrderingComposer,
      $$ThreadCacheTableAnnotationComposer,
      $$ThreadCacheTableCreateCompanionBuilder,
      $$ThreadCacheTableUpdateCompanionBuilder,
      (
        ThreadCacheRow,
        BaseReferences<_$AppDatabase, $ThreadCacheTable, ThreadCacheRow>,
      ),
      ThreadCacheRow,
      PrefetchHooks Function()
    >;
typedef $$MessageCacheTableCreateCompanionBuilder =
    MessageCacheCompanion Function({
      required String kind,
      required int providerId,
      required int threadId,
      required int date,
      required String data,
      Value<int> rowid,
    });
typedef $$MessageCacheTableUpdateCompanionBuilder =
    MessageCacheCompanion Function({
      Value<String> kind,
      Value<int> providerId,
      Value<int> threadId,
      Value<int> date,
      Value<String> data,
      Value<int> rowid,
    });

class $$MessageCacheTableFilterComposer
    extends Composer<_$AppDatabase, $MessageCacheTable> {
  $$MessageCacheTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get threadId => $composableBuilder(
    column: $table.threadId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get date => $composableBuilder(
    column: $table.date,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get data => $composableBuilder(
    column: $table.data,
    builder: (column) => ColumnFilters(column),
  );
}

class $$MessageCacheTableOrderingComposer
    extends Composer<_$AppDatabase, $MessageCacheTable> {
  $$MessageCacheTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get threadId => $composableBuilder(
    column: $table.threadId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get date => $composableBuilder(
    column: $table.date,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get data => $composableBuilder(
    column: $table.data,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$MessageCacheTableAnnotationComposer
    extends Composer<_$AppDatabase, $MessageCacheTable> {
  $$MessageCacheTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get kind =>
      $composableBuilder(column: $table.kind, builder: (column) => column);

  GeneratedColumn<int> get providerId => $composableBuilder(
    column: $table.providerId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get threadId =>
      $composableBuilder(column: $table.threadId, builder: (column) => column);

  GeneratedColumn<int> get date =>
      $composableBuilder(column: $table.date, builder: (column) => column);

  GeneratedColumn<String> get data =>
      $composableBuilder(column: $table.data, builder: (column) => column);
}

class $$MessageCacheTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $MessageCacheTable,
          MessageCacheRow,
          $$MessageCacheTableFilterComposer,
          $$MessageCacheTableOrderingComposer,
          $$MessageCacheTableAnnotationComposer,
          $$MessageCacheTableCreateCompanionBuilder,
          $$MessageCacheTableUpdateCompanionBuilder,
          (
            MessageCacheRow,
            BaseReferences<_$AppDatabase, $MessageCacheTable, MessageCacheRow>,
          ),
          MessageCacheRow,
          PrefetchHooks Function()
        > {
  $$MessageCacheTableTableManager(_$AppDatabase db, $MessageCacheTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$MessageCacheTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$MessageCacheTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$MessageCacheTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> kind = const Value.absent(),
                Value<int> providerId = const Value.absent(),
                Value<int> threadId = const Value.absent(),
                Value<int> date = const Value.absent(),
                Value<String> data = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => MessageCacheCompanion(
                kind: kind,
                providerId: providerId,
                threadId: threadId,
                date: date,
                data: data,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String kind,
                required int providerId,
                required int threadId,
                required int date,
                required String data,
                Value<int> rowid = const Value.absent(),
              }) => MessageCacheCompanion.insert(
                kind: kind,
                providerId: providerId,
                threadId: threadId,
                date: date,
                data: data,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$MessageCacheTable, MessageCacheRow>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $MessageCacheTable,
                    MessageCacheRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$MessageCacheTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $MessageCacheTable,
      MessageCacheRow,
      $$MessageCacheTableFilterComposer,
      $$MessageCacheTableOrderingComposer,
      $$MessageCacheTableAnnotationComposer,
      $$MessageCacheTableCreateCompanionBuilder,
      $$MessageCacheTableUpdateCompanionBuilder,
      (
        MessageCacheRow,
        BaseReferences<_$AppDatabase, $MessageCacheTable, MessageCacheRow>,
      ),
      MessageCacheRow,
      PrefetchHooks Function()
    >;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$SyncEventsTableTableManager get syncEvents =>
      $$SyncEventsTableTableManager(_db, _db.syncEvents);
  $$OutboundStatesTableTableManager get outboundStates =>
      $$OutboundStatesTableTableManager(_db, _db.outboundStates);
  $$ConversationPrefsTableTableManager get conversationPrefs =>
      $$ConversationPrefsTableTableManager(_db, _db.conversationPrefs);
  $$StarredMessagesTableTableManager get starredMessages =>
      $$StarredMessagesTableTableManager(_db, _db.starredMessages);
  $$DraftsTableTableManager get drafts =>
      $$DraftsTableTableManager(_db, _db.drafts);
  $$ScheduledSendsTableTableManager get scheduledSends =>
      $$ScheduledSendsTableTableManager(_db, _db.scheduledSends);
  $$PendingMediaTableTableManager get pendingMedia =>
      $$PendingMediaTableTableManager(_db, _db.pendingMedia);
  $$KeyValuesTableTableManager get keyValues =>
      $$KeyValuesTableTableManager(_db, _db.keyValues);
  $$ThreadCacheTableTableManager get threadCache =>
      $$ThreadCacheTableTableManager(_db, _db.threadCache);
  $$MessageCacheTableTableManager get messageCache =>
      $$MessageCacheTableTableManager(_db, _db.messageCache);
}
