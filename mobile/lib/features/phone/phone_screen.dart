import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/text/phone_format.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../../ui/skin/tokens.dart';
import '../../ui/widgets/avatar.dart';
import 'dialer_gateway.dart';
import 't9.dart';

/// Overridden in tests; the app uses the native dialer through Pigeon.
final dialerProvider = Provider<DialerGateway>((ref) => PlatformDialerGateway(ref.watch(servicesProvider).host));

final recentsProvider = FutureProvider.autoDispose<List<RecentCall>>((ref) => ref.watch(dialerProvider).recent(300, 0));

/// The address book, kept for the session: the keypad searches it on every key press.
final phoneContactsProvider = FutureProvider<List<PhoneContact>>((ref) => ref.watch(dialerProvider).contacts(5000));

final callbackTasksProvider = FutureProvider.autoDispose<List<CallbackTaskData>>((ref) => ref.watch(dialerProvider).callbacks());

/// SIMs with the label and colour the admin gave them (calls config cached by the native engine), else the carrier.
final callSimsProvider = FutureProvider.autoDispose<List<CallSim>>((ref) async {
  final sims = await ref.watch(dialerProvider).sims();
  Map<int, Map<String, dynamic>> admin = {};
  try {
    final raw = (await ref.watch(servicesProvider).db.allValues())['cache.calls_config'];
    final list = raw == null ? const [] : (jsonDecode(raw)['sims'] as List? ?? const []);
    admin = {for (final s in list.cast<Map<String, dynamic>>()) (s['subscription_id'] as num).toInt(): s};
  } on Object {
    // widget tests without services
  }
  return [
    for (final sim in sims)
      CallSim(
        sim.subscriptionId,
        admin[sim.subscriptionId]?['label'] as String? ?? (sim.carrier.isEmpty ? 'SIM ${sim.slot + 1}' : sim.carrier),
        _colour(admin[sim.subscriptionId]?['colour'] as String?, sim.slot),
      ),
  ];
});

class CallSim {
  const CallSim(this.subscriptionId, this.label, this.colour);
  final int subscriptionId;
  final String label;
  final Color colour;
}

Color _colour(String? hex, int slot) {
  final value = int.tryParse((hex ?? '').replaceFirst('#', ''), radix: 16);
  if (value != null) return Color(0xFF000000 | value);
  return const [Color(0xFF10B981), Color(0xFF8B5CF6), Color(0xFFF59E0B), Color(0xFFEF4444)][slot % 4];
}

enum PhoneTab { keypad, recents, contacts, callbacks }

/// "OCM Phone": Keypad / Recents / Contacts / Call-backs. Skinned with the same tokens as Messages.
class PhoneScreen extends ConsumerStatefulWidget {
  const PhoneScreen({super.key, this.tab = PhoneTab.keypad, this.number});
  final PhoneTab tab;
  final String? number;
  @override
  ConsumerState<PhoneScreen> createState() => _PhoneScreenState();
}

class _PhoneScreenState extends ConsumerState<PhoneScreen> {
  late PhoneTab _tab = widget.tab;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final waiting = ref.watch(callbackTasksProvider).value?.length ?? 0;
    final body = switch (_tab) {
      PhoneTab.keypad => KeypadTab(initial: widget.number),
      PhoneTab.recents => const RecentsTab(),
      PhoneTab.contacts => const ContactsTab(),
      PhoneTab.callbacks => const CallbacksTab(),
    };
    return Scaffold(
      backgroundColor: tokens.pageBackground,
      appBar: AppBar(
        title: Text(l10n.phoneTitle),
        actions: [IconButton(tooltip: l10n.appTitle, icon: const Icon(Icons.chat_bubble_outline), onPressed: () => context.go('/conversations'))],
      ),
      body: SafeArea(top: false, child: body),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab.index,
        onDestinationSelected: (index) => setState(() => _tab = PhoneTab.values[index]),
        destinations: [
          NavigationDestination(icon: const Icon(Icons.dialpad), label: l10n.tabKeypad),
          NavigationDestination(icon: const Icon(Icons.history), label: l10n.tabRecents),
          NavigationDestination(icon: const Icon(Icons.person_outline), label: l10n.tabContacts),
          NavigationDestination(
            icon: Badge(isLabelVisible: waiting > 0, label: Text('$waiting'), child: const Icon(Icons.phone_callback_outlined)),
            label: l10n.tabCallbacks,
          ),
        ],
      ),
    );
  }
}

/// Places a call, asking which SIM on dual-SIM phones. Never dials without the person's tap (this runs from a tap).
Future<void> placeCall(BuildContext context, WidgetRef ref, String number, {String origin = 'manual', String? callbackTask}) async {
  if (number.trim().isEmpty) return;
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.of(context);
  final sims = await ref.read(callSimsProvider.future).catchError((Object _) => <CallSim>[]);
  // One SIM: name it, so the call record carries its line. Several: the person chooses.
  int? sub = sims.length == 1 ? sims.single.subscriptionId : null;
  if (sims.length > 1 && context.mounted) {
    final chosen = await showModalBottomSheet<CallSim>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(title: Text(l10n.callWith, style: Theme.of(context).textTheme.titleMedium)),
            for (final sim in sims)
              ListTile(
                leading: CircleAvatar(radius: 10, backgroundColor: sim.colour),
                title: Text(sim.label),
                onTap: () => Navigator.pop(context, sim),
              ),
          ],
        ),
      ),
    );
    if (chosen == null) return;
    sub = chosen.subscriptionId;
  }
  final result = await ref.read(dialerProvider).placeCall(number.trim(), subscriptionId: sub, origin: origin, callbackTask: callbackTask);
  if (result == 'permission') messenger.showSnackBar(SnackBar(content: Text(l10n.callFailedPermission)));
}

// --- Keypad ------------------------------------------------------------------------------------------------------

class KeypadTab extends ConsumerStatefulWidget {
  const KeypadTab({super.key, this.initial});
  final String? initial;
  @override
  ConsumerState<KeypadTab> createState() => _KeypadTabState();
}

class _KeypadTabState extends ConsumerState<KeypadTab> {
  late String _number = widget.initial ?? '';

  void _press(String key) {
    HapticFeedback.selectionClick();
    setState(() => _number += key);
  }

  void _longPress(String key) {
    HapticFeedback.heavyImpact();
    if (key == '0') return setState(() => _number += '+');
    if (key == '1' && _number.isEmpty) {
      placeCall(context, ref, 'voicemail');
      return;
    }
    _press(key);
  }

  Future<void> _paste() async {
    final text = (await Clipboard.getData(Clipboard.kTextPlain))?.text ?? '';
    final clean = text.replaceAll(RegExp(r'[^\d+*#,;]'), '');
    if (clean.isNotEmpty) setState(() => _number = clean);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final contacts = ref.watch(phoneContactsProvider).value ?? const <PhoneContact>[];
    final matches = t9Search(contacts, _number, name: (c) => c.name, number: (c) => c.number, limit: 4);
    return LayoutBuilder(
      builder: (context, constraints) {
        // Keys shrink to fit narrow windows (split screen, small phones); the skin's size is the maximum.
        final widthFactor = tokens.keypadKey == KeypadKeyStyle.flat ? 1.4 : 1.0;
        final keySize = ((constraints.maxWidth - 16) / (3 * widthFactor)).clamp(40.0, tokens.keypadKeySize);
        return Column(
          children: [
            Expanded(
              child: ListView(
                key: const Key('t9-results'),
                padding: const EdgeInsets.symmetric(horizontal: 8),
                reverse: true,
                children: [
                  for (final c in matches)
                    ListTile(
                      dense: true,
                      leading: ContactAvatar(title: c.name, address: c.number, saved: true, photoUri: c.photoUri, size: 36),
                      title: Text(c.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text(c.number),
                      onTap: () => setState(() => _number = c.number),
                    ),
                ],
              ),
            ),
            GestureDetector(
              onLongPress: _paste,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                child: Row(
                  children: [
                    const SizedBox(width: 48),
                    Expanded(
                      child: Text(
                        _number.isEmpty ? ' ' : formatNumber(_number),
                        key: const Key('keypad-number'),
                        textAlign: TextAlign.center,
                        maxLines: 1,
                        style: TextStyle(fontSize: _number.length > 14 ? 26 : 34, fontWeight: FontWeight.w400, letterSpacing: 1),
                      ),
                    ),
                    SizedBox(
                      width: 48,
                      child: _number.isEmpty
                          ? IconButton(tooltip: l10n.paste, icon: const Icon(Icons.content_paste), onPressed: _paste)
                          : GestureDetector(
                              onLongPress: () => setState(() => _number = ''),
                              child: IconButton(
                                tooltip: MaterialLocalizations.of(context).deleteButtonTooltip,
                                icon: const Icon(Icons.backspace_outlined),
                                onPressed: () => setState(() => _number = _number.substring(0, _number.length - 1)),
                              ),
                            ),
                    ),
                  ],
                ),
              ),
            ),
            for (final row in const [
              ['1', '2', '3'],
              ['4', '5', '6'],
              ['7', '8', '9'],
              ['*', '0', '#'],
            ])
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [for (final key in row) _Key(digit: key, size: keySize, onTap: () => _press(key), onLongPress: () => _longPress(key))],
              ),
            const SizedBox(height: 12),
            SizedBox(
              width: keySize,
              height: keySize,
              child: FloatingActionButton(
                key: const Key('call-button'),
                heroTag: 'call',
                elevation: 0,
                backgroundColor: tokens.callButton,
                foregroundColor: Colors.white,
                shape: const CircleBorder(),
                tooltip: l10n.callAction,
                onPressed: () => placeCall(context, ref, _number),
                child: const Icon(Icons.call, size: 30),
              ),
            ),
            const SizedBox(height: 16),
          ],
        );
      },
    );
  }
}

class _Key extends StatelessWidget {
  const _Key({required this.digit, required this.size, required this.onTap, required this.onLongPress});
  final String digit;
  final double size;
  final VoidCallback onTap;
  final VoidCallback onLongPress;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final scheme = Theme.of(context).colorScheme;
    final letters = digit == '1' ? 'voicemail' : keypadLetters[digit] ?? '';
    final shape = switch (tokens.keypadKey) {
      KeypadKeyStyle.circle => const CircleBorder(),
      KeypadKeyStyle.rounded => RoundedRectangleBorder(borderRadius: BorderRadius.circular(size * 0.28)),
      KeypadKeyStyle.flat => const StadiumBorder(),
    };
    final fill = tokens.keypadKey == KeypadKeyStyle.flat ? Colors.transparent : scheme.surfaceContainerHigh;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Material(
        color: fill,
        shape: shape,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          key: Key('key-$digit'),
          onTap: onTap,
          onLongPress: onLongPress,
          child: SizedBox(
            width: size * (tokens.keypadKey == KeypadKeyStyle.flat ? 1.4 : 1),
            height: size,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(digit, style: TextStyle(fontSize: size * 0.4, height: 1.1)),
                if (tokens.keypadLetters && letters.isNotEmpty)
                  digit == '1'
                      ? Icon(Icons.voicemail, size: size * 0.18, color: scheme.onSurfaceVariant)
                      : Text(
                          letters,
                          style: TextStyle(fontSize: size * 0.15, letterSpacing: 1.5, color: scheme.onSurfaceVariant),
                        ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// --- Recents -----------------------------------------------------------------------------------------------------

/// Consecutive calls with the same number and the same kind (missed / not missed) on the same day become one row.
List<List<RecentCall>> groupRecents(List<RecentCall> calls) {
  final groups = <List<RecentCall>>[];
  bool missed(RecentCall c) => c.direction == 'in' && const {'missed', 'rejected', 'voicemail'}.contains(c.result);
  DateTime day(RecentCall c) {
    final d = DateTime.fromMillisecondsSinceEpoch(c.date);
    return DateTime(d.year, d.month, d.day);
  }

  for (final call in calls) {
    final last = groups.isEmpty ? null : groups.last.first;
    if (last != null && last.number == call.number && missed(last) == missed(call) && day(last) == day(call)) {
      groups.last.add(call);
    } else {
      groups.add([call]);
    }
  }
  return groups;
}

class RecentsTab extends ConsumerWidget {
  const RecentsTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final recents = ref.watch(recentsProvider);
    return recents.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, _) => Center(child: Text(l10n.noRecents)),
      data: (calls) {
        if (calls.isEmpty) return Center(child: Text(l10n.noRecents));
        final groups = groupRecents(calls);
        return RefreshIndicator(
          onRefresh: () async => ref.invalidate(recentsProvider),
          child: ListView.builder(
            key: const Key('recents-list'),
            itemCount: groups.length,
            itemBuilder: (context, index) => RecentRow(group: groups[index]),
          ),
        );
      },
    );
  }
}

class RecentRow extends ConsumerWidget {
  const RecentRow({super.key, required this.group});
  final List<RecentCall> group;

  static IconData icon(RecentCall call) {
    if (call.direction == 'out') return Icons.call_made;
    return switch (call.result) {
      'missed' || 'voicemail' => Icons.call_missed,
      'rejected' || 'blocked' => Icons.call_end,
      _ => Icons.call_received,
    };
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final call = group.first;
    final missed = call.direction == 'in' && const {'missed', 'rejected', 'voicemail'}.contains(call.result);
    final title = call.name ?? (call.number.isEmpty ? l10n.privateNumber : formatNumber(call.number));
    final time = TimeOfDay.fromDateTime(DateTime.fromMillisecondsSinceEpoch(call.date)).format(context);
    return SizedBox(
      height: tokens.recentsRowHeight,
      child: ListTile(
        leading: ContactAvatar(title: title, address: call.number, saved: call.nameSource == 'contact', size: 42),
        title: Text(
          group.length > 1 ? '$title (${group.length})' : title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(color: missed ? tokens.missedCall : null, fontWeight: missed ? FontWeight.w600 : null),
        ),
        subtitle: Row(
          children: [
            Icon(icon(call), size: 15, color: missed ? tokens.missedCall : Theme.of(context).colorScheme.onSurfaceVariant),
            const SizedBox(width: 4),
            if (call.nameSource == 'directory') ...[
              Flexible(child: Text(l10n.companyDirectory, maxLines: 1, overflow: TextOverflow.ellipsis)),
              const Text(' · '),
            ],
            Text(time),
          ],
        ),
        trailing: IconButton(
          tooltip: l10n.callAction,
          icon: Icon(Icons.call_outlined, color: tokens.callButton),
          onPressed: call.number.isEmpty ? null : () => placeCall(context, ref, call.number, origin: 'redial'),
        ),
        onTap: () => _details(context, ref, call),
      ),
    );
  }

  void _details(BuildContext context, WidgetRef ref, RecentCall call) {
    final l10n = AppLocalizations.of(context);
    showModalBottomSheet<void>(
      context: context,
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: Text(call.name ?? formatNumber(call.number), style: Theme.of(context).textTheme.titleMedium),
              subtitle: Text(
                [
                  for (final c in group)
                    '${TimeOfDay.fromDateTime(DateTime.fromMillisecondsSinceEpoch(c.date)).format(context)} · ${_result(l10n, c)}'
                        '${c.durationSeconds > 0 ? ' · ${c.durationSeconds ~/ 60}:${(c.durationSeconds % 60).toString().padLeft(2, '0')}' : ''}',
                ].join('\n'),
              ),
            ),
            if (call.number.isNotEmpty) ...[
              ListTile(
                leading: const Icon(Icons.call),
                title: Text(l10n.callAction),
                onTap: () {
                  Navigator.pop(sheet);
                  placeCall(context, ref, call.number, origin: 'redial');
                },
              ),
              ListTile(
                leading: const Icon(Icons.message_outlined),
                title: Text(l10n.messageAction),
                onTap: () {
                  Navigator.pop(sheet);
                  context.push('/compose?to=${Uri.encodeComponent(call.number)}');
                },
              ),
              if (call.nameSource != 'contact')
                ListTile(
                  leading: const Icon(Icons.person_add_alt),
                  title: Text(l10n.addContact),
                  onTap: () {
                    Navigator.pop(sheet);
                    ref.read(dialerProvider).addContact(call.number);
                  },
                ),
              ListTile(
                leading: const Icon(Icons.block),
                title: Text(l10n.blockNumber),
                onTap: () async {
                  Navigator.pop(sheet);
                  await ref.read(repositoryProvider).phone.blockNumber(call.number);
                },
              ),
            ],
            ListTile(
              leading: const Icon(Icons.delete_outline),
              title: Text(l10n.deleteFromRecents),
              onTap: () async {
                Navigator.pop(sheet);
                for (final c in group) {
                  await ref.read(dialerProvider).deleteRecent(c.id);
                }
                ref.invalidate(recentsProvider);
              },
            ),
          ],
        ),
      ),
    );
  }

  static String _result(AppLocalizations l10n, RecentCall c) => switch (c.result) {
    'missed' => l10n.resultMissed,
    'rejected' => l10n.resultRejected,
    'blocked' => l10n.resultBlocked,
    'voicemail' => l10n.resultVoicemail,
    'no_answer' => l10n.resultNoAnswer,
    'answered_elsewhere' => l10n.resultElsewhere,
    _ => c.direction == 'in' ? l10n.incomingCall : l10n.outgoingCall,
  };
}

// --- Contacts ----------------------------------------------------------------------------------------------------

class ContactsTab extends ConsumerStatefulWidget {
  const ContactsTab({super.key});
  @override
  ConsumerState<ContactsTab> createState() => _ContactsTabState();
}

class _ContactsTabState extends ConsumerState<ContactsTab> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final contacts = ref.watch(phoneContactsProvider);
    return contacts.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, _) => Center(child: Text(l10n.noContacts)),
      data: (all) {
        final q = _query.trim().toLowerCase();
        final shown = q.isEmpty
            ? all
            : all.where((c) => c.name.toLowerCase().contains(q) || digitsOnly(c.number).contains(digitsOnly(q).isEmpty ? '\u0000' : digitsOnly(q))).toList();
        final favourites = q.isEmpty ? shown.where((c) => c.starred).toList() : const <PhoneContact>[];
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: SearchBar(
                hintText: l10n.searchContacts,
                leading: const Icon(Icons.search),
                elevation: const WidgetStatePropertyAll(0),
                onChanged: (v) => setState(() => _query = v),
              ),
            ),
            Expanded(
              child: shown.isEmpty
                  ? Center(child: Text(l10n.noContacts))
                  : ListView(
                      key: const Key('contacts-list'),
                      children: [
                        if (favourites.isNotEmpty) ...[
                          ListTile(dense: true, title: Text(l10n.favourites, style: Theme.of(context).textTheme.labelLarge)),
                          for (final c in favourites) _ContactTile(contact: c),
                          const Divider(),
                        ],
                        for (final c in shown) _ContactTile(contact: c),
                      ],
                    ),
            ),
          ],
        );
      },
    );
  }
}

class _ContactTile extends ConsumerWidget {
  const _ContactTile({required this.contact});
  final PhoneContact contact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    return ListTile(
      leading: ContactAvatar(title: contact.name, address: contact.number, saved: true, photoUri: contact.photoUri, size: 40),
      title: Text(contact.name, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(contact.directoryName != null ? '${formatNumber(contact.number)} · ${l10n.companyDirectory}' : formatNumber(contact.number)),
      trailing: IconButton(
        tooltip: l10n.callAction,
        icon: Icon(Icons.call_outlined, color: tokens.callButton),
        onPressed: () => placeCall(context, ref, contact.number),
      ),
      onTap: () => context.push('/compose?to=${Uri.encodeComponent(contact.number)}'),
    );
  }
}

// --- Call-backs --------------------------------------------------------------------------------------------------

class CallbacksTab extends ConsumerWidget {
  const CallbacksTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final tasks = ref.watch(callbackTasksProvider);
    return tasks.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, _) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(l10n.noCallbacks, textAlign: TextAlign.center),
        ),
      ),
      data: (list) {
        final open = list.where((t) => t.state != 'done').toList();
        if (open.isEmpty)
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(l10n.noCallbacks, textAlign: TextAlign.center),
            ),
          );
        return RefreshIndicator(
          onRefresh: () async {
            await ref.read(repositoryProvider).phone.syncNow();
            ref.invalidate(callbackTasksProvider);
          },
          child: ListView(
            key: const Key('callbacks-list'),
            children: [
              for (final task in open)
                Card(
                  margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(child: Text(task.name.isEmpty ? formatNumber(task.number) : task.name, style: Theme.of(context).textTheme.titleMedium)),
                            if (task.priority == 'high' || task.priority == 'urgent')
                              Chip(label: Text(task.priority == 'urgent' ? l10n.priorityUrgent : l10n.priorityHigh), visualDensity: VisualDensity.compact),
                          ],
                        ),
                        if (task.name.isNotEmpty) Text(formatNumber(task.number)),
                        if (task.reason.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text(task.reason)),
                        Text(l10n.requestedBy(task.requestedBy), style: Theme.of(context).textTheme.bodySmall),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton(
                              onPressed: () async {
                                await ref.read(dialerProvider).reportCallback(task.id, 'snoozed');
                                ref.invalidate(callbackTasksProvider);
                              },
                              child: Text(l10n.snoozeAction),
                            ),
                            TextButton(
                              onPressed: () async {
                                await ref.read(dialerProvider).reportCallback(task.id, 'done');
                                ref.invalidate(callbackTasksProvider);
                              },
                              child: Text(l10n.doneAction),
                            ),
                            FilledButton.icon(
                              style: FilledButton.styleFrom(backgroundColor: tokens.callButton),
                              onPressed: () => placeCall(context, ref, task.number, origin: 'callback_task', callbackTask: task.id),
                              icon: const Icon(Icons.call),
                              label: Text(l10n.callAction),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}
