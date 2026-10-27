import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../l10n/app_localizations.dart';
import '../../providers.dart';

final _syncStatusProvider = FutureProvider<Map<String, Object?>>((ref) async {
  ref.watch(refreshTickProvider);
  final services = ref.watch(servicesProvider);
  final status = await services.phone.serviceStatus();
  return {
    'server': services.session?.server.host ?? '-',
    'code': services.session?.deviceCode ?? '-',
    'last': int.tryParse(await services.db.getValue('last_sync_at') ?? ''),
    'pending': await services.db.pendingCount(),
    'queue': (await services.db.unreportedOutbound()).length,
    'online': status.networkAvailable,
    'network': status.networkType,
  };
});

class SyncStatusScreen extends ConsumerWidget {
  const SyncStatusScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final data = ref.watch(_syncStatusProvider).value;
    final last = data?['last'] as int?;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.syncStatus)),
      body: data == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(children: [
              ListTile(title: Text(l10n.server), subtitle: Text('${data['server']}')),
              ListTile(title: Text(l10n.deviceCode), subtitle: SelectableText('${data['code']}')),
              ListTile(title: Text(l10n.lastSync), subtitle: Text(last == null ? l10n.never : DateFormat.yMMMd().add_Hms().format(DateTime.fromMillisecondsSinceEpoch(last)))),
              ListTile(title: Text(l10n.pendingUploads), trailing: Text('${data['pending']}')),
              ListTile(title: Text(l10n.queueWaiting), trailing: Text('${data['queue']}')),
              ListTile(title: Text(l10n.connectivity), trailing: Text(data['online'] == true ? '${l10n.online} · ${data['network']}' : l10n.offline)),
              Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton.icon(
                  icon: const Icon(Icons.sync),
                  label: Text(l10n.syncNow),
                  onPressed: () async {
                    await ref.read(servicesProvider).host.startSyncService(); // the service runs a cycle on start
                    ref.read(refreshTickProvider.notifier).bump();
                  },
                ),
              ),
            ]),
    );
  }
}
