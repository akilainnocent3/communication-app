import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:uuid/uuid.dart';

import '../core/db/database.dart';
import '../core/text/phone_format.dart';
import '../platform/telephony_api.g.dart';
import 'phone_gateway.dart';

enum Folder { inbox, archived, spam }

/// The phone refused a message before writing it anywhere (not the default SMS app, no SIM), so there is no failed
/// bubble to retry from; the composer keeps the text and says why.
class SendRefused implements Exception {
  const SendRefused(this.errorCode);
  final int? errorCode;
  @override
  String toString() => 'SendRefused($errorCode)';
}

/// One conversation row. Immutable; the list replaces rows one at a time when an event names their thread.
class ConversationItem {
  const ConversationItem({
    required this.thread, required this.title, required this.subtitle, required this.saved, this.photoUri, this.pinned = false, this.archived = false,
    this.muted = false, this.spam = false, this.blocked = false,
  });
  final ThreadSummary thread;
  final String title;
  final String subtitle;
  final bool saved;
  final String? photoUri;
  final bool pinned;
  final bool archived;
  final bool muted;
  final bool spam;
  final bool blocked;

  int get id => thread.threadId;
  bool inFolder(Folder folder) => switch (folder) { Folder.inbox => !archived && !spam, Folder.archived => archived && !spam, Folder.spam => spam };

  ConversationItem copyWith({ThreadSummary? thread, String? title, String? subtitle, bool? saved, String? photoUri, bool? pinned, bool? archived, bool? muted, bool? spam, bool? blocked}) =>
      ConversationItem(
        thread: thread ?? this.thread, title: title ?? this.title, subtitle: subtitle ?? this.subtitle, saved: saved ?? this.saved, photoUri: photoUri ?? this.photoUri,
        pinned: pinned ?? this.pinned, archived: archived ?? this.archived, muted: muted ?? this.muted, spam: spam ?? this.spam, blocked: blocked ?? this.blocked,
      );

  /// Case-insensitive match on the title, the numbers and the snippet (the local half of search).
  bool matches(String needle) {
    final digits = needle.replaceAll(RegExp(r'[^0-9+]'), '');
    return title.toLowerCase().contains(needle) || thread.snippet.toLowerCase().contains(needle) ||
        (digits.length >= 3 && thread.addresses.any((a) => a.replaceAll(RegExp(r'[^0-9+]'), '').contains(digits)));
  }
}

/// Pinned first, then newest.
int compareItems(ConversationItem a, ConversationItem b) => a.pinned != b.pinned ? (a.pinned ? -1 : 1) : b.thread.date.compareTo(a.thread.date);

/// The only code that touches the phone and the local database for conversations. Reads are cache-first: the encrypted
/// cache answers at once, the Telephony provider (through native code, off the main thread) reconciles after.
class ConversationsRepository {
  ConversationsRepository({required this.phone, required this.db});
  final PhoneGateway phone;
  final AppDatabase db;

  static const pageSize = 50;
  static const messagePage = 50;

  // --- Conversation list -------------------------------------------------------------------------------------

  Future<Map<int, ConversationPrefRow>> prefs() async => {for (final row in await db.allPrefs()) row.threadId: row};

  ConversationItem _item(ThreadSummary thread, Map<String, ContactInfo> contacts, ConversationPrefRow? pref, Set<String> blocked) {
    final names = [for (final a in thread.addresses) contacts[a]?.displayName];
    final saved = names.any((n) => (n ?? '').isNotEmpty);
    final title = [for (var i = 0; i < thread.addresses.length; i++) (names[i] ?? '').isNotEmpty ? names[i]! : formatNumber(thread.addresses[i])].join(', ');
    final isBlocked = thread.addresses.any(blocked.contains);
    return ConversationItem(
      thread: thread, title: title, subtitle: saved ? thread.addresses.map(formatNumber).join(', ') : '', saved: saved,
      photoUri: thread.addresses.length == 1 ? contacts[thread.addresses.first]?.photoUri : null,
      pinned: pref?.pinned ?? false, archived: pref?.archived ?? false, muted: pref?.muted ?? false, spam: (pref?.spam ?? false) || isBlocked, blocked: isBlocked,
    );
  }

  /// What the list draws on its first frame: the cache, no platform call.
  Future<List<ConversationItem>> cached() async {
    final rows = await db.cachedThreads();
    final prefs = await this.prefs();
    return [
      for (final r in rows)
        ConversationItem(
          thread: ThreadSummary(threadId: r.threadId, addresses: (jsonDecode(r.addresses) as List).cast<String>(), snippet: r.snippet, date: r.date,
              unreadCount: r.unread, messageCount: r.messageCount, hasMms: r.hasMms),
          title: r.title, subtitle: r.saved ? (jsonDecode(r.addresses) as List).cast<String>().map(formatNumber).join(', ') : '', saved: r.saved, photoUri: r.photoUri,
          pinned: prefs[r.threadId]?.pinned ?? false, archived: prefs[r.threadId]?.archived ?? false, muted: prefs[r.threadId]?.muted ?? false,
          spam: prefs[r.threadId]?.spam ?? false,
        ),
    ]..sort(compareItems);
  }

  /// One page from the provider. Names come from [known] first (render the number, fill the name when ready); call
  /// [withNames] for the address-book pass.
  Future<List<ConversationItem>> page(int offset, {Map<String, ContactInfo> known = const {}}) async {
    final threads = await phone.threads(pageSize, offset);
    final prefs = await this.prefs();
    final blocked = (await phone.blockedNumbers()).toSet();
    return [for (final t in threads) _item(t, known, prefs[t.threadId], blocked)];
  }

  /// The address-book pass for rows whose names are not known yet (one native call, cached natively).
  Future<List<ConversationItem>> withNames(List<ConversationItem> items) async {
    final addresses = {for (final i in items) ...i.thread.addresses}.toList();
    if (addresses.isEmpty) return items;
    final contacts = {for (final c in await phone.lookupContacts(addresses)) c.address: c};
    final prefs = await this.prefs();
    final blocked = (await phone.blockedNumbers()).toSet();
    return [for (final i in items) _item(i.thread, contacts, prefs[i.id], blocked)];
  }

  /// One conversation after an event about it; null when the thread is gone.
  Future<ConversationItem?> refreshThread(int threadId) async {
    final thread = await phone.thread(threadId);
    if (thread == null) {
      await db.forgetThread(threadId);
      return null;
    }
    final contacts = {for (final c in await phone.lookupContacts(thread.addresses)) c.address: c};
    final pref = (await db.prefsFor([threadId]))[threadId];
    final item = _item(thread, contacts, pref, (await phone.blockedNumbers()).toSet());
    await saveToCache([item]);
    return item;
  }

  Future<void> saveToCache(List<ConversationItem> items) => db.cacheThreads([
        for (final i in items)
          ThreadCacheCompanion.insert(
            threadId: Value(i.id), addresses: jsonEncode(i.thread.addresses), title: i.title, saved: Value(i.saved), photoUri: Value(i.photoUri),
            snippet: i.thread.snippet, date: i.thread.date, unread: Value(i.thread.unreadCount), messageCount: Value(i.thread.messageCount), hasMms: Value(i.thread.hasMms),
          ),
      ]);

  /// After a full first page: threads newer than the page's oldest that the provider no longer has were deleted.
  Future<void> pruneCache(List<ConversationItem> firstPage) async {
    if (firstPage.isEmpty) return;
    final oldest = firstPage.map((i) => i.thread.date).reduce((a, b) => a < b ? a : b);
    await db.pruneThreads({for (final i in firstPage) i.id}, olderThan: oldest);
  }

  Future<void> setPinned(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(pinned: Value(value)));
  Future<void> setArchived(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(archived: Value(value)));
  Future<void> setMuted(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(muted: Value(value)));
  Future<void> setSpam(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(spam: Value(value)));
  Future<void> markRead(int threadId) => phone.markThreadRead(threadId);

  Future<void> delete(int threadId) async {
    await phone.deleteThread(threadId);
    await db.forgetThread(threadId);
  }

  Future<void> block(List<String> addresses, {required bool blocked}) async {
    for (final address in addresses) {
      blocked ? await phone.blockNumber(address) : await phone.unblockNumber(address);
    }
  }

  // --- Messages ----------------------------------------------------------------------------------------------

  /// The chat's first frame: the cached newest messages (newest first), no platform call.
  Future<List<ProviderMessage>> cachedMessages(int threadId) async =>
      [for (final row in await db.cachedMessages(threadId)) messageFromJson(jsonDecode(row.data) as Map<String, dynamic>)];

  /// Newest first, a page of 50 before [before] (null = the newest page, which also refreshes the cache).
  Future<List<ProviderMessage>> messages(int threadId, {int? before}) async {
    final page = await phone.messages(threadId, messagePage, before);
    if (before == null) {
      await db.cacheMessages(threadId, [
        for (final m in page) MessageCacheCompanion.insert(kind: m.kind, providerId: m.providerId, threadId: threadId, date: m.date, data: jsonEncode(messageToJson(m))),
      ]);
    }
    return page;
  }

  Future<List<ProviderMessage>> searchMessages(String query, {int offset = 0, int limit = 30}) => phone.searchMessages(query, limit, offset);

  Future<Set<int>> starred(String kind) async =>
      (await (db.select(db.starredMessages)..where((t) => t.kind.equals(kind))).get()).map((row) => row.providerId).toSet();

  Future<void> setStarred(ProviderMessage message, bool value) async {
    if (value) {
      await db.into(db.starredMessages).insertOnConflictUpdate(StarredMessagesCompanion.insert(kind: message.kind, providerId: message.providerId));
    } else {
      await (db.delete(db.starredMessages)..where((t) => t.kind.equals(message.kind) & t.providerId.equals(message.providerId))).go();
    }
  }

  /// Sends from the phone (origin "phone"). Scheduled sends wait in the local table for the native sync engine.
  Future<SendResult?> send({required List<String> addresses, required String body, int? subscriptionId, List<String> attachments = const [], DateTime? at}) async {
    final clientUuid = const Uuid().v4();
    if (at != null) {
      await db.into(db.scheduledSends).insert(ScheduledSendsCompanion.insert(
        clientUuid: clientUuid, addresses: jsonEncode(addresses), body: body, subscriptionId: Value(subscriptionId), sendAt: at.millisecondsSinceEpoch,
      ));
      return null;
    }
    final result = await phone.sendMessage(SendRequest(clientUuid: clientUuid, addresses: addresses, body: body, subscriptionId: subscriptionId, deliveryReport: true, attachmentUris: attachments, origin: 'phone'));
    if (result.state == 'failed' && result.providerId == null) throw SendRefused(result.errorCode);
    return result;
  }

  Future<String?> draft(String key) async => (await (db.select(db.drafts)..where((t) => t.key.equals(key))).getSingleOrNull())?.body;

  Future<void> saveDraft(String key, String body) async {
    if (body.trim().isEmpty) {
      await (db.delete(db.drafts)..where((t) => t.key.equals(key))).go();
    } else {
      await db.into(db.drafts).insertOnConflictUpdate(DraftsCompanion.insert(key: key, body: body, updatedAt: DateTime.now().millisecondsSinceEpoch));
    }
  }

  /// Admin-origin messages, so the chat can label them "Sent by admin".
  Future<Map<int, String?>> adminSent(List<ProviderMessage> messages) async {
    final ids = messages.where((m) => m.outbound).map((m) => m.providerId).toList();
    if (ids.isEmpty) return const {};
    final rows = await (db.select(db.outboundStates)..where((t) => t.providerId.isIn(ids))).get();
    return {for (final row in rows) row.providerId!: row.sentBy};
  }

  /// Quick replies from the admin, cached by the native sync engine (never a server call from the UI).
  Future<List<Map<String, dynamic>>> quickReplies() async {
    final raw = await db.getValue('cache.quick_replies');
    if (raw == null || raw.isEmpty) return const [];
    try {
      return (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
    } on FormatException {
      return const [];
    }
  }
}
