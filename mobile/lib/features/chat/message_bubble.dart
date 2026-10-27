import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../../core/text/otp.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../theme.dart';

String statusText(AppLocalizations l10n, String status) => switch (status) {
      'sending' || 'queued' => l10n.statusSending,
      'sent' => l10n.statusSent,
      'delivered' => l10n.statusDelivered,
      'failed' => l10n.statusFailed,
      _ => '',
    };

/// One message. Admin-origin messages have their own colour and the label "Sent by admin · Name"; one-time codes get
/// a "Copy code" chip; links are shown as text (no automatic previews: they would leak the link to third parties).
class MessageBubble extends StatelessWidget {
  const MessageBubble({super.key, required this.message, this.adminName, this.isAdmin = false, this.starred = false, required this.onLongPress, this.onRetry});
  final ProviderMessage message;
  final bool isAdmin;
  final String? adminName;
  final bool starred;
  final VoidCallback onLongPress;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final out = message.outbound;
    final background = !out ? scheme.surfaceContainerHighest : isAdmin ? (dark ? adminBubbleDark : adminBubbleLight) : scheme.primary;
    final foreground = !out ? scheme.onSurface : isAdmin ? Colors.white : scheme.onPrimary;
    final otp = out ? null : extractOtp(message.body);
    final time = DateFormat.Hm(Localizations.localeOf(context).toString()).format(DateTime.fromMillisecondsSinceEpoch(message.date));
    return Column(
      crossAxisAlignment: out ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        if (isAdmin)
          Padding(
            padding: const EdgeInsets.only(right: 8, bottom: 2),
            child: Text(adminName == null || adminName!.isEmpty ? l10n.sentByAdmin : l10n.sentByAdminNamed(adminName!), style: TextStyle(fontSize: 11, color: dark ? const Color(0xFF5EEAD4) : adminBubbleLight)),
          ),
        GestureDetector(
          onLongPress: onLongPress,
          onTap: message.status == 'failed' ? onRetry : null,
          child: Semantics(
            label: '${out ? (isAdmin ? l10n.sentByAdmin : l10n.detailsSent) : l10n.detailsReceived}, $time',
            child: Container(
              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
              decoration: BoxDecoration(
                color: background,
                borderRadius: BorderRadius.only(topLeft: const Radius.circular(18), topRight: const Radius.circular(18), bottomLeft: Radius.circular(out ? 18 : 4), bottomRight: Radius.circular(out ? 4 : 18)),
                border: message.status == 'failed' ? Border.all(color: scheme.error, width: 1.5) : null,
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                if (message.parts.any((p) => p.contentType.startsWith('image/')))
                  Padding(padding: const EdgeInsets.only(bottom: 6), child: Icon(Icons.image_outlined, color: foreground)),
                if (message.body.isNotEmpty) SelectableText(message.body, style: TextStyle(color: foreground, fontSize: 15)),
              ]),
            ),
          ),
        ),
        if (otp != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: ActionChip(
              avatar: const Icon(Icons.copy, size: 16), label: Text('${l10n.copyCode} $otp'),
              onPressed: () {
                Clipboard.setData(ClipboardData(text: otp));
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l10n.codeCopied)));
              },
            ),
          ),
        Padding(
          padding: const EdgeInsets.only(top: 2, left: 4, right: 4),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (starred) const Icon(Icons.star, size: 12, color: Colors.amber),
            Text(time, style: Theme.of(context).textTheme.labelSmall),
            if (out) ...[const SizedBox(width: 4), Text(statusText(l10n, message.status), style: Theme.of(context).textTheme.labelSmall?.copyWith(color: message.status == 'failed' ? scheme.error : null))],
          ]),
        ),
      ],
    );
  }
}
