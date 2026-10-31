import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/text/phone_format.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../../ui/skin/tokens.dart';
import '../../ui/widgets/phone_chrome.dart';
import '../common/widgets.dart';
import 'dialer_gateway.dart';
import 't9.dart';

/// Overridden in tests; the app uses the native dialer through Pigeon.
final dialerProvider = Provider<DialerGateway>((ref) => PlatformDialerGateway(ref.watch(servicesProvider).host));

/// Kept for the session (calls_changed and resume refresh it in place), so Recents opens with its rows at once.
final recentsProvider = FutureProvider<List<RecentCall>>((ref) => ref.watch(dialerProvider).recent(300, 0));

/// The address book, kept for the session: the keypad searches it on every key press.
final phoneContactsProvider = FutureProvider<List<PhoneContact>>((ref) => ref.watch(dialerProvider).contacts(5000));

/// The owner's own card, for Contacts → My profile (One UI).
final myProfileProvider = FutureProvider<PhoneContact?>((ref) => ref.watch(dialerProvider).myProfile().catchError((Object _) => null));

/// The address book encoded for T9 once per load, not once per key press.
final t9IndexProvider = Provider<T9Index<PhoneContact>>(
  (ref) => T9Index(ref.watch(phoneContactsProvider).value ?? const [], name: (c) => c.name, number: (c) => c.number),
);

/// "Today" for the Recents day headers; fixed in tests.
final clockProvider = Provider<DateTime Function()>((ref) => DateTime.now);

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

/// "Phone": Keypad / Recents / Contacts / Call-backs, laid out like the Phone app this phone came with (the skin:
/// header, tabs, list cards and keypad all come from its tokens).
class PhoneScreen extends ConsumerStatefulWidget {
  const PhoneScreen({super.key, this.tab = PhoneTab.keypad, this.number});
  final PhoneTab tab;
  final String? number;
  @override
  ConsumerState<PhoneScreen> createState() => _PhoneScreenState();
}

class _PhoneScreenState extends ConsumerState<PhoneScreen> {
  late PhoneTab _tab = widget.number != null ? PhoneTab.keypad : widget.tab;
  /// Tabs stay alive once opened, as in the phone's own dialer: switching back keeps the typed number and the scroll
  /// position, and never shows a spinner again.
  late final Set<PhoneTab> _opened = {_tab};
  /// Bumped by the keypad's Search: Contacts opens its search field.
  int _contactsSearch = 0;

  @override
  void initState() {
    super.initState();
    // Load Recents and the address book with the first frame, so either tab opens with its rows.
    ref.read(recentsProvider);
    ref.read(phoneContactsProvider);
  }

  @override
  void didUpdateWidget(PhoneScreen old) {
    super.didUpdateWidget(old);
    // A tel: link or notification while the app is open.
    if (widget.number != old.number && widget.number != null) {
      _tab = PhoneTab.keypad;
    } else if (widget.tab != old.tab) {
      _tab = widget.tab;
    }
    _opened.add(_tab);
  }

  void _select(PhoneTab tab) => setState(() => _opened.add(_tab = tab));

  void _searchContacts() => setState(() {
    _opened.add(_tab = PhoneTab.contacts);
    _contactsSearch++;
  });

  Widget _tabBody(PhoneTab tab) => switch (tab) {
    PhoneTab.keypad => KeypadTab(initial: widget.number, onSearch: _searchContacts),
    PhoneTab.recents => const RecentsTab(),
    PhoneTab.contacts => ContactsTab(searchRequest: _contactsSearch),
    PhoneTab.callbacks => const CallbacksTab(),
  };

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final waiting = ref.watch(callbackTasksProvider).value?.length ?? 0;
    final banner = DialerBanner.shown(ref);
    final body = IndexedStack(
      index: _tab.index,
      children: [for (final tab in PhoneTab.values) _opened.contains(tab) ? _tabBody(tab) : const SizedBox.shrink()],
    );
    return Scaffold(
      backgroundColor: tokens.pageBackground,
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            const DialerBanner(),
            // Each tab draws its own header under the status bar; the banner takes that inset when it shows.
            Expanded(child: MediaQuery.removePadding(context: context, removeTop: banner, child: body)),
          ],
        ),
      ),
      bottomNavigationBar: switch (tokens.phoneTabs) {
        PhoneTabStyle.text => TextTabBar(
          labels: [l10n.tabKeypad, l10n.tabRecents, l10n.tabContacts, l10n.tabCallbacks],
          selected: _tab.index,
          badges: {PhoneTab.callbacks.index: waiting},
          onSelected: (index) => _select(PhoneTab.values[index]),
        ),
        PhoneTabStyle.navigationBar => NavigationBar(
          selectedIndex: _tab.index,
          onDestinationSelected: (index) => _select(PhoneTab.values[index]),
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
      },
    );
  }
}

/// The ⋮ menu in every tab's header.
class PhoneMenuButton extends StatelessWidget {
  const PhoneMenuButton({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return PopupMenuButton<String>(
      tooltip: MaterialLocalizations.of(context).moreButtonTooltip,
      icon: const Icon(Icons.more_vert),
      onSelected: (route) => context.push(route),
      itemBuilder: (context) => [PopupMenuItem(value: '/settings', child: Text(l10n.settings))],
    );
  }
}

/// Places a call, asking which SIM on dual-SIM phones unless [subscriptionId] already names one (the per-SIM call
/// buttons). Never dials without the person's tap (this runs from a tap).
Future<void> placeCall(BuildContext context, WidgetRef ref, String number, {String origin = 'manual', String? callbackTask, int? subscriptionId}) async {
  if (number.trim().isEmpty) return;
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.of(context);
  final sims = subscriptionId != null ? const <CallSim>[] : await ref.read(callSimsProvider.future).catchError((Object _) => <CallSim>[]);
  // One SIM: name it, so the call record carries its line. Several: the person chooses.
  int? sub = subscriptionId ?? (sims.length == 1 ? sims.single.subscriptionId : null);
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
  const KeypadTab({super.key, this.initial, this.onSearch});
  final String? initial;
  /// The header's Search (opens the contacts search); no Search icon without it.
  final VoidCallback? onSearch;
  @override
  ConsumerState<KeypadTab> createState() => _KeypadTabState();
}

class _KeypadTabState extends ConsumerState<KeypadTab> {
  late String _number = widget.initial ?? '';

  @override
  void didUpdateWidget(KeypadTab old) {
    super.didUpdateWidget(old);
    if (widget.initial != old.initial && widget.initial != null) _number = widget.initial!;
  }

  void _press(String key) {
    HapticFeedback.selectionClick();
    unawaited(ref.read(dialerProvider).dialTone(key).catchError((Object _) {}));
    setState(() => _number += key);
  }

  /// As the phone's own dialer: Call on an empty keypad brings back the last number dialled; the next tap calls it.
  Future<void> _call({int? subscriptionId}) async {
    if (_number.trim().isNotEmpty) return placeCall(context, ref, _number, subscriptionId: subscriptionId);
    final calls = await ref.read(recentsProvider.future).catchError((Object _) => <RecentCall>[]);
    final last = calls.where((c) => c.direction == 'out' && c.number.isNotEmpty).firstOrNull;
    if (last != null && mounted && _number.isEmpty) setState(() => _number = last.number);
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
    final secondary = secondaryTextOf(context);
    final flat = tokens.keypadKey == KeypadKeyStyle.flat;
    final matches = ref.watch(t9IndexProvider).search(_number, limit: 4);
    // One UI: one call button per SIM on dual-SIM phones, no question after the tap.
    final sims = tokens.dualSimCallButtons ? ref.watch(callSimsProvider).value ?? const <CallSim>[] : const <CallSim>[];
    return Column(
      children: [
        SkinnedTopBar(
          title: l10n.phoneTitle,
          actions: [
            if (widget.onSearch != null) IconButton(tooltip: MaterialLocalizations.of(context).searchFieldLabel, icon: const Icon(Icons.search), onPressed: widget.onSearch),
            const PhoneMenuButton(),
          ],
        ),
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              // Keys shrink to fit narrow or short windows (split screen, landscape, small phones); the skin's size is the
              // maximum. Height: the number line and spacing take about 120 dp (152 with the suggestion line), then four key
              // rows and the call button.
              final widthFactor = flat ? 1.4 : 1.0;
              final byWidth = (constraints.maxWidth - 16) / (3 * widthFactor);
              final byHeight = (constraints.maxHeight - (flat ? 152 : 120)) / 5 - 8;
              final keySize = math.min(byWidth, byHeight).clamp(32.0, tokens.keypadKeySize);
              final callSize = flat ? keySize * 0.95 : keySize;
              Widget callButton({CallSim? sim, int index = 0}) => SizedBox(
                width: callSize,
                height: callSize,
                child: FloatingActionButton(
                  key: Key(sim == null ? 'call-button' : 'call-button-${sim.subscriptionId}'),
                  heroTag: 'call-${sim?.subscriptionId}',
                  elevation: 0,
                  highlightElevation: 0,
                  backgroundColor: tokens.callButton,
                  foregroundColor: Colors.white,
                  shape: const CircleBorder(),
                  tooltip: sim == null ? l10n.callAction : '${l10n.callAction} · ${sim.label}',
                  onPressed: () => _call(subscriptionId: sim?.subscriptionId),
                  child: sim == null
                      ? Icon(Icons.call, size: callSize * 0.42)
                      : Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.call, size: callSize * 0.34),
                            Text('SIM ${index + 1}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500), textScaler: TextScaler.noScaling),
                          ],
                        ),
                ),
              );
              final suggestion = flat ? matches.firstOrNull : null;
              return Column(
                children: [
                  Expanded(
                    child: flat
                        ? const SizedBox.shrink()
                        : ListView(
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
                            // Long numbers shrink to stay on one line.
                            child: FittedBox(
                              fit: BoxFit.scaleDown,
                              child: Text(
                                _number.isEmpty ? ' ' : formatNumber(_number),
                                key: const Key('keypad-number'),
                                textAlign: TextAlign.center,
                                maxLines: 1,
                                style: TextStyle(fontSize: flat ? 36 : 34, fontWeight: FontWeight.w400, letterSpacing: 1),
                              ),
                            ),
                          ),
                          SizedBox(
                            width: 48,
                            child: _number.isEmpty
                                ? (flat ? null : IconButton(tooltip: l10n.paste, icon: const Icon(Icons.content_paste), onPressed: _paste))
                                : GestureDetector(
                                    onLongPress: () => setState(() => _number = ''),
                                    child: IconButton(
                                      tooltip: MaterialLocalizations.of(context).deleteButtonTooltip,
                                      icon: Icon(Icons.backspace_outlined, color: flat ? secondary : null),
                                      onPressed: () => setState(() => _number = _number.substring(0, _number.length - 1)),
                                    ),
                                  ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  // Flat keypads: the best contact match on one line under the number; tap to use its number.
                  if (flat)
                    SizedBox(
                      height: 32,
                      child: suggestion == null
                          ? null
                          : TextButton(
                              key: const Key('t9-suggestion'),
                              onPressed: () => setState(() => _number = suggestion.number),
                              child: Text(
                                '${suggestion.name}  ${formatNumber(suggestion.number)}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(fontSize: 15, color: secondary),
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
                  SizedBox(height: flat ? 16 : 12),
                  if (sims.length > 1)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        for (var i = 0; i < sims.length && i < 2; i++) ...[
                          if (i > 0) const SizedBox(width: 40),
                          callButton(sim: sims[i], index: i),
                        ],
                      ],
                    )
                  else
                    callButton(),
                  const SizedBox(height: 16),
                ],
              );
            },
          ),
        ),
      ],
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
    final secondary = secondaryTextOf(context);
    final flat = tokens.keypadKey == KeypadKeyStyle.flat;
    final letters = digit == '1' ? 'voicemail' : keypadLetters[digit] ?? '';
    final shape = switch (tokens.keypadKey) {
      KeypadKeyStyle.circle => const CircleBorder(),
      KeypadKeyStyle.rounded => RoundedRectangleBorder(borderRadius: BorderRadius.circular(size * 0.28)),
      KeypadKeyStyle.flat => const CircleBorder(),
    };
    final content = SizedBox(
      width: size * (flat ? 1.4 : 1),
      height: size,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(digit, style: TextStyle(fontSize: size * (flat ? 0.47 : 0.4), height: 1.1, fontWeight: tokens.keypadDigitWeight), textScaler: TextScaler.noScaling),
          if (tokens.keypadLetters && letters.isNotEmpty)
            digit == '1'
                ? Icon(Icons.voicemail, size: size * 0.18, color: secondary)
                : Text(letters, style: TextStyle(fontSize: size * (flat ? 0.16 : 0.15), letterSpacing: flat ? 1 : 1.5, color: secondary), textScaler: TextScaler.noScaling),
        ],
      ),
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      // Flat keys: digits on the page, a round grey press behind the key; the whole cell stays tappable.
      child: flat
          ? Material(
              type: MaterialType.transparency,
              child: InkWell(key: Key('key-$digit'), customBorder: shape, onTap: onTap, onLongPress: onLongPress, child: content),
            )
          : Material(
              color: scheme.surfaceContainerHigh,
              shape: shape,
              clipBehavior: Clip.antiAlias,
              child: InkWell(key: Key('key-$digit'), onTap: onTap, onLongPress: onLongPress, child: content),
            ),
    );
  }
}

// --- Recents -----------------------------------------------------------------------------------------------------

/// Consecutive calls with the same number and the same kind (missed / not missed) on the same day become one row.
List<List<RecentCall>> groupRecents(List<RecentCall> calls) {
  final groups = <List<RecentCall>>[];
  DateTime day(RecentCall c) {
    final d = DateTime.fromMillisecondsSinceEpoch(c.date);
    return DateTime(d.year, d.month, d.day);
  }

  for (final call in calls) {
    final last = groups.isEmpty ? null : groups.last.first;
    if (last != null && last.number == call.number && isMissed(last) == isMissed(call) && day(last) == day(call)) {
      groups.last.add(call);
    } else {
      groups.add([call]);
    }
  }
  return groups;
}

bool isMissed(RecentCall c) => c.direction == 'in' && const {'missed', 'rejected', 'voicemail'}.contains(c.result);

/// A row of a sectioned list, with its place in its section (grouped skins round the section's first and last rows).
class _Placed<T> {
  const _Placed(this.value, {required this.first, required this.last});
  final T value;
  final bool first, last;
}

/// Section labels and rows: a String is a label, the rows under it are one section.
List<Object> _sectioned<T>(Iterable<(String?, T)> rows) {
  final out = <Object>[];
  final section = <T>[];
  void flush() {
    for (var i = 0; i < section.length; i++) {
      out.add(_Placed<T>(section[i], first: i == 0, last: i == section.length - 1));
    }
    section.clear();
  }

  String? current;
  var started = false;
  for (final (label, row) in rows) {
    if (!started || label != current) {
      flush();
      if (label != null) out.add(label);
      current = label;
      started = true;
    }
    section.add(row);
  }
  flush();
  return out;
}

class RecentsTab extends ConsumerStatefulWidget {
  const RecentsTab({super.key});
  @override
  ConsumerState<RecentsTab> createState() => _RecentsTabState();
}

class _RecentsTabState extends ConsumerState<RecentsTab> {
  bool _missedOnly = false;
  /// Non-null while the search field is open.
  String? _query;
  /// The row showing its Call / Message / Details actions (grouped skins), by its newest call's id.
  int? _expanded;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final recents = ref.watch(recentsProvider);
    final slivers = recents.when<List<Widget>>(
      loading: () => [const SliverFillRemaining(hasScrollBody: false, child: Center(child: CircularProgressIndicator()))],
      error: (_, _) => [_EmptySliver(l10n.noRecents)],
      data: (calls) {
        final q = (_query ?? '').trim().toLowerCase();
        final qDigits = digitsOnly(q);
        final shown = calls.where((c) {
          if (_missedOnly && !isMissed(c)) return false;
          if (q.isEmpty) return true;
          return (c.name ?? '').toLowerCase().contains(q) || (qDigits.isNotEmpty && digitsOnly(c.number).contains(qDigits));
        }).toList();
        if (shown.isEmpty) return [_EmptySliver(l10n.noRecents)];
        final now = ref.watch(clockProvider)();
        final locale = Localizations.localeOf(context).toString();
        // Day sections (Today, Yesterday, then dates), as in the phone's own call log; groups never span two days.
        final items = _sectioned([for (final group in groupRecents(shown)) (dayLabel(l10n, locale, group.first.date, now), group)]);
        return [
          SliverList.builder(
            itemCount: items.length,
            itemBuilder: (context, index) => switch (items[index]) {
              final String day => SectionLabel(day),
              final row => () {
                final placed = row as _Placed<List<RecentCall>>;
                final id = placed.value.first.id;
                return RecentRow(
                  group: placed.value,
                  first: placed.first,
                  last: placed.last,
                  expanded: _expanded == id,
                  onToggle: () => setState(() => _expanded = _expanded == id ? null : id),
                );
              }(),
            },
          ),
        ];
      },
    );
    if (_query != null) {
      return SkinnedSearchView(
        hint: MaterialLocalizations.of(context).searchFieldLabel,
        onChanged: (v) => setState(() => _query = v),
        onClose: () => setState(() => _query = null),
        slivers: slivers,
      );
    }
    return SkinnedScrollView(
      scrollKey: const Key('recents-list'),
      title: l10n.phoneTitle,
      onRefresh: () async => ref.refresh(recentsProvider.future),
      actions: [
        PopupMenuButton<bool>(
          tooltip: l10n.missedCalls,
          icon: Icon(_missedOnly ? Icons.filter_alt : Icons.filter_list),
          initialValue: _missedOnly,
          onSelected: (v) => setState(() => _missedOnly = v),
          itemBuilder: (context) => [
            CheckedPopupMenuItem(value: false, checked: !_missedOnly, child: Text(l10n.allCalls)),
            CheckedPopupMenuItem(value: true, checked: _missedOnly, child: Text(l10n.missedCalls)),
          ],
        ),
        IconButton(tooltip: MaterialLocalizations.of(context).searchFieldLabel, icon: const Icon(Icons.search), onPressed: () => setState(() => _query = '')),
        const PhoneMenuButton(),
      ],
      slivers: slivers,
    );
  }
}

class _EmptySliver extends StatelessWidget {
  const _EmptySliver(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => SliverFillRemaining(
    hasScrollBody: false,
    child: Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(text, textAlign: TextAlign.center, style: TextStyle(color: secondaryTextOf(context))))),
  );
}

/// Today / Yesterday / "Mon, 26 Oct" (this year) / "26 Oct 2025".
String dayLabel(AppLocalizations l10n, String locale, int millis, DateTime now) {
  final date = DateTime.fromMillisecondsSinceEpoch(millis);
  final days = (DateTime(now.year, now.month, now.day).difference(DateTime(date.year, date.month, date.day)).inHours / 24).round();
  if (days == 0) return l10n.today;
  if (days == 1) return l10n.yesterday;
  return (date.year == now.year ? DateFormat.MMMEd(locale) : DateFormat.yMMMd(locale)).format(date);
}

class RecentRow extends ConsumerWidget {
  const RecentRow({super.key, required this.group, this.first = false, this.last = false, this.expanded = false, this.onToggle});
  final List<RecentCall> group;
  final bool first, last;
  /// Grouped skins: the row shows Call / Message / Details under it.
  final bool expanded;
  final VoidCallback? onToggle;

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
    final missed = isMissed(call);
    final title = call.name ?? (call.number.isEmpty ? l10n.privateNumber : formatNumber(call.number));
    final time = TimeOfDay.fromDateTime(DateTime.fromMillisecondsSinceEpoch(call.date)).format(context);
    final label = group.length > 1 ? '$title (${group.length})' : title;
    if (!tokens.recentsAvatar) return _iconLed(context, ref, l10n, tokens, call, missed, title, label, time);
    return GroupedRow(
      first: first,
      last: last,
      minHeight: tokens.recentsRowHeight,
      child: ListTile(
        leading: ContactAvatar(title: title, address: call.number, saved: call.nameSource == 'contact', size: 42),
        title: Text(
          label,
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

  /// One UI: the call-type icon leads, the name in the middle, the SIM and time stacked on the right; a tap opens
  /// the row's actions in place, a long press the details.
  Widget _iconLed(BuildContext context, WidgetRef ref, AppLocalizations l10n, SkinTokens tokens, RecentCall call, bool missed, String title, String label, String time) {
    final secondary = secondaryTextOf(context);
    final sims = ref.watch(callSimsProvider).value ?? const <CallSim>[];
    final simIndex = sims.length > 1 ? sims.indexWhere((s) => s.subscriptionId == call.subscriptionId) : -1;
    final semantics = [
      title,
      _result(l10n, call),
      if (group.length > 1) l10n.callsCount(group.length),
      if (simIndex >= 0) 'SIM ${simIndex + 1}',
      time,
    ].join(', ');
    return GroupedRow(
      first: first,
      last: last,
      minHeight: tokens.recentsRowHeight,
      dividerIndent: 66,
      onTap: onToggle,
      onLongPress: () => _details(context, ref, call),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Semantics(
            label: semantics,
            excludeSemantics: true,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(22, 10, 22, 10),
              child: Row(
                children: [
                  _CallTypeIcon(call: call),
                  const SizedBox(width: 20),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: tokens.rowTitleSize, color: missed ? tokens.missedCall : null)),
                        if (call.nameSource == 'directory')
                          Text(l10n.companyDirectory, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 13, color: secondary)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (simIndex >= 0) _SimBadge(number: simIndex + 1, colour: sims[simIndex].colour),
                      Text(time.toLowerCase(), style: TextStyle(fontSize: 13, color: secondary)),
                    ],
                  ),
                ],
              ),
            ),
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 150),
            alignment: Alignment.topCenter,
            child: !expanded
                ? const SizedBox(width: double.infinity)
                : Padding(
                    padding: const EdgeInsets.fromLTRB(54, 0, 14, 8),
                    child: Row(
                      children: [
                        if (call.number.isNotEmpty) ...[
                          IconButton(
                            tooltip: l10n.callAction,
                            icon: Icon(Icons.call, color: tokens.callButton),
                            onPressed: () => placeCall(context, ref, call.number, origin: 'redial'),
                          ),
                          IconButton(tooltip: l10n.messageAction, icon: const Icon(Icons.chat_bubble_outline), onPressed: () => ref.read(dialerProvider).message(call.number)),
                        ],
                        IconButton(tooltip: l10n.details, icon: const Icon(Icons.info_outline), onPressed: () => _details(context, ref, call)),
                      ],
                    ),
                  ),
          ),
        ],
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
                  ref.read(dialerProvider).message(call.number);
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
                  await ref.read(phoneProvider).blockNumber(call.number);
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

/// A grey handset with a small direction arrow: green ↗ outgoing, blue ↙ incoming, red for missed or declined.
class _CallTypeIcon extends StatelessWidget {
  const _CallTypeIcon({required this.call});
  final RecentCall call;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final missed = isMissed(call) || call.result == 'blocked';
    final (arrow, colour) = switch (call.direction) {
      'out' => (Icons.north_east, tokens.callButton),
      _ when missed => (Icons.south_west, tokens.missedCall),
      _ => (Icons.south_west, const Color(0xFF3E7BFA)),
    };
    return SizedBox.square(
      dimension: 24,
      child: Stack(
        children: [
          Positioned(left: 0, bottom: 0, child: Icon(Icons.call, size: 18, color: missed ? tokens.missedCall : secondaryTextOf(context))),
          Positioned(right: 0, top: 0, child: Icon(arrow, size: 12, color: colour)),
        ],
      ),
    );
  }
}

/// Which SIM a call used, on dual-SIM phones: its number on the SIM's colour.
class _SimBadge extends StatelessWidget {
  const _SimBadge({required this.number, required this.colour});
  final int number;
  final Color colour;

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 2),
    padding: const EdgeInsets.symmetric(horizontal: 4),
    decoration: BoxDecoration(color: colour, borderRadius: const BorderRadius.only(topLeft: Radius.circular(2), topRight: Radius.circular(5), bottomLeft: Radius.circular(2), bottomRight: Radius.circular(2))),
    child: Text('$number', style: const TextStyle(fontSize: 10, height: 1.4, fontWeight: FontWeight.w700, color: Colors.white), textScaler: TextScaler.noScaling),
  );
}

// --- Contacts ----------------------------------------------------------------------------------------------------

class ContactsTab extends ConsumerStatefulWidget {
  const ContactsTab({super.key, this.searchRequest = 0});
  /// Changes when the keypad's Search asks for the search field.
  final int searchRequest;
  @override
  ConsumerState<ContactsTab> createState() => _ContactsTabState();
}

/// Lower-case names and number digits, worked out once per address book load for the search box.
final _contactSearchProvider = Provider<List<({PhoneContact contact, String name, String digits})>>((ref) => [
  for (final c in ref.watch(phoneContactsProvider).value ?? const <PhoneContact>[]) (contact: c, name: c.name.toLowerCase(), digits: digitsOnly(c.number)),
]);

/// The Favourites section's label (a star before it).
class _FavouritesLabel {
  const _FavouritesLabel();
}

/// The My profile row (the owner's card), on top of the list on One UI.
class _ProfileRow {
  const _ProfileRow(this.contact);
  final PhoneContact contact;
}

class _ContactsTabState extends ConsumerState<ContactsTab> {
  /// Non-null while the search field is open.
  late String? _query = widget.searchRequest > 0 ? '' : null;

  @override
  void didUpdateWidget(ContactsTab old) {
    super.didUpdateWidget(old);
    if (widget.searchRequest != old.searchRequest) _query = '';
  }

  /// The letter a contact is filed under (A–Z, else #), as in the phone's own Contacts list.
  static String _letter(String name) {
    final first = name.trim().isEmpty ? '#' : name.trim()[0].toUpperCase();
    return RegExp(r'[A-Z]').hasMatch(first) ? first : '#';
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final contacts = ref.watch(phoneContactsProvider);
    final profile = SkinTokens.of(context).groupedList ? ref.watch(myProfileProvider).value : null;
    final loaded = contacts.value ?? const <PhoneContact>[];
    final slivers = contacts.when<List<Widget>>(
      loading: () => [const SliverFillRemaining(hasScrollBody: false, child: Center(child: CircularProgressIndicator()))],
      error: (_, _) => [_EmptySliver(l10n.noContacts)],
      data: (all) {
        final q = (_query ?? '').trim().toLowerCase();
        final qDigits = digitsOnly(q);
        final shown = q.isEmpty
            ? all
            : [
                for (final e in ref.watch(_contactSearchProvider))
                  if (e.name.contains(q) || (qDigits.isNotEmpty && e.digits.contains(qDigits))) e.contact,
              ];
        if (shown.isEmpty) return [_EmptySliver(l10n.noContacts)];
        // Sections: Favourites, then A–Z (search results: one section). Rows are built lazily.
        final List<Object> items;
        if (q.isEmpty) {
          final favourites = _sectioned([for (final c in shown.where((c) => c.starred)) (l10n.favourites, c)]);
          if (favourites.isNotEmpty) favourites[0] = const _FavouritesLabel();
          items = [
            if (profile != null) ...[l10n.myProfile, _ProfileRow(profile)],
            ...favourites,
            ..._sectioned([for (final c in shown) (_letter(c.name), c)]),
          ];
        } else {
          items = _sectioned([for (final c in shown) (null, c)]);
        }
        return [
          SliverList.builder(
            itemCount: items.length,
            itemBuilder: (context, index) => switch (items[index]) {
              _FavouritesLabel() => SectionLabel(l10n.favourites, icon: Icons.star_rounded),
              _ProfileRow(:final contact) => _ContactTile(
                key: const Key('my-profile'),
                contact: contact,
                first: true,
                last: true,
                onTap: () => ref.read(dialerProvider).openProfile(),
              ),
              final String header => SectionLabel(header),
              final row => () {
                final placed = row as _Placed<PhoneContact>;
                return _ContactTile(contact: placed.value, first: placed.first, last: placed.last);
              }(),
            },
          ),
        ];
      },
    );
    if (_query != null) {
      return SkinnedSearchView(
        hint: l10n.searchContacts,
        onChanged: (v) => setState(() => _query = v),
        onClose: () => setState(() => _query = null),
        slivers: slivers,
      );
    }
    return SkinnedScrollView(
      scrollKey: const Key('contacts-list'),
      title: l10n.phoneTitle,
      subtitle: loaded.isEmpty ? null : l10n.contactsWithNumbers(loaded.length),
      actions: [
        IconButton(tooltip: l10n.addContact, icon: const Icon(Icons.add), onPressed: () => ref.read(dialerProvider).addContact('')),
        IconButton(tooltip: l10n.searchContacts, icon: const Icon(Icons.search), onPressed: () => setState(() => _query = '')),
        const PhoneMenuButton(),
      ],
      slivers: slivers,
    );
  }
}

class _ContactTile extends ConsumerWidget {
  const _ContactTile({super.key, required this.contact, this.first = false, this.last = false, this.onTap});
  final PhoneContact contact;
  final bool first, last;
  /// In place of the contact's actions (My profile opens the owner's card).
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    // A tap on the row opens the contact's actions (no call from a stray tap while scrolling).
    if (tokens.groupedList) {
      // One UI: avatar and name only, the name lined up with the dividers.
      return GroupedRow(
        first: first,
        last: last,
        minHeight: 58,
        dividerIndent: 86,
        onTap: onTap ?? () => _actions(context, ref),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 9, 22, 9),
          child: Row(
            children: [
              ContactAvatar(title: contact.name, address: contact.number, saved: true, photoUri: contact.photoUri, size: 40),
              const SizedBox(width: 24),
              Expanded(child: Text(contact.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: tokens.rowTitleSize))),
            ],
          ),
        ),
      );
    }
    return GroupedRow(
      first: first,
      last: last,
      child: ListTile(
        leading: ContactAvatar(title: contact.name, address: contact.number, saved: true, photoUri: contact.photoUri, size: 40),
        title: Text(contact.name, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(contact.directoryName != null ? '${formatNumber(contact.number)} · ${l10n.companyDirectory}' : formatNumber(contact.number)),
        trailing: IconButton(
          tooltip: l10n.callAction,
          icon: Icon(Icons.call_outlined, color: tokens.callButton),
          onPressed: () => placeCall(context, ref, contact.number),
        ),
        onTap: () => _actions(context, ref),
      ),
    );
  }

  void _actions(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    showModalBottomSheet<void>(
      context: context,
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: ContactAvatar(title: contact.name, address: contact.number, saved: true, photoUri: contact.photoUri, size: 40),
              title: Text(contact.name, style: Theme.of(context).textTheme.titleMedium),
              subtitle: Text(contact.directoryName != null ? '${formatNumber(contact.number)} · ${l10n.companyDirectory}' : formatNumber(contact.number)),
            ),
            ListTile(
              leading: const Icon(Icons.call),
              title: Text(l10n.callAction),
              onTap: () {
                Navigator.pop(sheet);
                placeCall(context, ref, contact.number);
              },
            ),
            ListTile(
              leading: const Icon(Icons.message_outlined),
              title: Text(l10n.messageAction),
              onTap: () {
                Navigator.pop(sheet);
                ref.read(dialerProvider).message(contact.number);
              },
            ),
          ],
        ),
      ),
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
    final slivers = tasks.when<List<Widget>>(
      loading: () => [const SliverFillRemaining(hasScrollBody: false, child: Center(child: CircularProgressIndicator()))],
      error: (_, _) => [_EmptySliver(l10n.noCallbacks)],
      data: (list) {
        final open = list.where((t) => t.state != 'done').toList();
        if (open.isEmpty) return [_EmptySliver(l10n.noCallbacks)];
        return [
          SliverList.list(
            children: [
              for (final task in open)
                Card(
                  elevation: 0,
                  color: tokens.groupedList ? tokens.listSurface : null,
                  margin: EdgeInsets.fromLTRB(tokens.groupedList ? tokens.listInset : 12, 8, tokens.groupedList ? tokens.listInset : 12, 0),
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(tokens.groupedList ? 22 : 16, 12, 8, 8),
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
        ];
      },
    );
    return SkinnedScrollView(
      scrollKey: const Key('callbacks-list'),
      title: l10n.tabCallbacks,
      onRefresh: () async {
        await ref.read(phoneProvider).syncNow();
        ref.invalidate(callbackTasksProvider);
      },
      actions: const [PhoneMenuButton()],
      slivers: slivers,
    );
  }
}
