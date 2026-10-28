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

class ConversationItem {
  const ConversationItem({required this.thread, required this.title, required this.subtitle, required this.saved, required this.pinned, required this.archived, required this.muted, required this.spam, required this.blocked});
  final ThreadSummary thread;
  final String title;
  final String subtitle;
  final bool saved;
  final bool pinned;
  final bool archived;
  final bool muted;
  final bool spam;
  final bool blocked;
}

/// The only code (with the sync engine) that touches the phone and the local database for conversations.
class ConversationsRepository {
  ConversationsRepository({required this.phone, required this.db});
  final PhoneGateway phone;
  final AppDatabase db;

  Future<List<ConversationItem>> list(Folder folder, {String query = '', int limit = 300}) async {
    final threads = await phone.threads(limit, 0);
    final prefs = await db.prefsFor(threads.map((t) => t.threadId));
    final contacts = {for (final c in await phone.lookupContacts(threads.expand((t) => t.addresses).toSet().toList())) c.address: c};
    final blocked = (await phone.blockedNumbers()).toSet();
    final needle = query.trim().toLowerCase();
    final items = <ConversationItem>[];
    for (final thread in threads) {
      final pref = prefs[thread.threadId];
      final names = thread.addresses.map((a) => contacts[a]?.displayName).toList();
      final saved = names.any((n) => (n ?? '').isNotEmpty);
      final title = [for (var i = 0; i < thread.addresses.length; i++) (names[i] ?? '').isNotEmpty ? names[i]! : formatNumber(thread.addresses[i])].join(', ');
      final isBlocked = thread.addresses.any(blocked.contains);
      final item = ConversationItem(
        thread: thread, title: title, subtitle: saved ? thread.addresses.map(formatNumber).join(', ') : '', saved: saved,
        pinned: pref?.pinned ?? false, archived: pref?.archived ?? false, muted: pref?.muted ?? false, spam: (pref?.spam ?? false) || isBlocked, blocked: isBlocked,
      );
      final inFolder = switch (folder) { Folder.inbox => !item.archived && !item.spam, Folder.archived => item.archived && !item.spam, Folder.spam => item.spam };
      if (!inFolder) continue;
      if (needle.isNotEmpty && !title.toLowerCase().contains(needle) && !thread.snippet.toLowerCase().contains(needle) && !thread.addresses.any((a) => a.contains(needle))) continue;
      items.add(item);
    }
    items.sort((a, b) => a.pinned != b.pinned ? (a.pinned ? -1 : 1) : b.thread.date.compareTo(a.thread.date));
    return items;
  }

  Future<void> setPinned(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(pinned: Value(value)));
  Future<void> setArchived(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(archived: Value(value)));
  Future<void> setMuted(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(muted: Value(value)));
  Future<void> setSpam(int threadId, bool value) => db.updatePref(threadId, ConversationPrefsCompanion(spam: Value(value)));
  Future<void> markRead(int threadId) => phone.markThreadRead(threadId);
  Future<void> delete(int threadId) => phone.deleteThread(threadId);

  Future<void> block(List<String> addresses, {required bool blocked}) async {
    for (final address in addresses) {
      blocked ? await phone.blockNumber(address) : await phone.unblockNumber(address);
    }
  }

  Future<List<ProviderMessage>> messages(int threadId, {int limit = 200, int? before}) => phone.messages(threadId, limit, before);

  Future<Set<int>> starred(String kind) async =>
      (await (db.select(db.starredMessages)..where((t) => t.kind.equals(kind))).get()).map((row) => row.providerId).toSet();

  Future<void> setStarred(ProviderMessage message, bool value) async {
    if (value) {
      await db.into(db.starredMessages).insertOnConflictUpdate(StarredMessagesCompanion.insert(kind: message.kind, providerId: message.providerId));
    } else {
      await (db.delete(db.starredMessages)..where((t) => t.kind.equals(message.kind) & t.providerId.equals(message.providerId))).go();
    }
  }

  /// Sends from the phone (origin "phone"). Scheduled sends wait in the local table for the sync loop.
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
}
