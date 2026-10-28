import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../ui/skin/tokens.dart';

/// The conversation list's header in the skin's style (the one layout variant chosen by token besides the compose
/// button). Archived and Spam always use the compact bar with a back button.
class ListHeader {
  static List<Widget> slivers({
    required BuildContext context, required String title, String? subtitle, required bool inbox, required VoidCallback onSearch, required Widget menu,
  }) {
    final tokens = SkinTokens.of(context);
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final search = IconButton(tooltip: l10n.searchHint, icon: const Icon(Icons.search), onPressed: onSearch);
    if (!inbox) return [SliverAppBar(pinned: true, title: Text(title), actions: [search, menu])];
    switch (tokens.header) {
      case HeaderStyle.compact:
        return [SliverAppBar(floating: true, title: Text(title, style: TextStyle(fontSize: tokens.titleSize, fontWeight: FontWeight.w600)), actions: [search, menu])];
      case HeaderStyle.largeCollapsing:
        // The expanded title fills the top of the screen so the list starts in thumb reach on tall phones.
        final height = MediaQuery.sizeOf(context).height;
        final expanded = (height * tokens.expandedHeaderFraction).clamp(kToolbarHeight + 60, 320.0);
        return [
          SliverAppBar(
            pinned: true,
            expandedHeight: expanded,
            actions: [search, menu],
            flexibleSpace: LayoutBuilder(builder: (context, box) {
              final top = MediaQuery.paddingOf(context).top;
              final t = ((box.maxHeight - kToolbarHeight - top) / (expanded - kToolbarHeight)).clamp(0.0, 1.0);
              return Stack(children: [
                // Collapsed: a small title in the bar.
                Positioned(left: 16, top: top, height: kToolbarHeight, child: Opacity(
                  opacity: 1 - t,
                  child: Align(alignment: Alignment.centerLeft, child: Text(title, style: TextStyle(fontSize: tokens.titleSize, fontWeight: FontWeight.w600))),
                )),
                // Expanded: the big centred title and the unread count.
                Positioned.fill(top: top, bottom: 8, child: Opacity(
                  opacity: t,
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Text(title, style: TextStyle(fontSize: tokens.largeTitleSize, fontWeight: FontWeight.w400, color: scheme.onSurface)),
                    if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text(subtitle, style: TextStyle(color: scheme.onSurfaceVariant))),
                  ]),
                )),
              ]);
            }),
          ),
        ];
      case HeaderStyle.searchPill:
        return [
          SliverAppBar(
            floating: true,
            toolbarHeight: 72,
            titleSpacing: 12,
            title: Material(
              color: scheme.surfaceContainerHigh,
              borderRadius: BorderRadius.circular(28),
              child: InkWell(
                borderRadius: BorderRadius.circular(28),
                onTap: onSearch,
                child: SizedBox(
                  height: 52,
                  child: Row(children: [
                    const SizedBox(width: 16),
                    Icon(Icons.search, color: scheme.onSurfaceVariant),
                    const SizedBox(width: 12),
                    Expanded(child: Text(l10n.searchHint, style: TextStyle(fontSize: 16, color: scheme.onSurfaceVariant))),
                    menu,
                  ]),
                ),
              ),
            ),
          ),
        ];
      case HeaderStyle.largeWithSearch:
        return [
          SliverAppBar(pinned: true, title: const SizedBox.shrink(), actions: [menu]),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: TextStyle(fontSize: tokens.largeTitleSize, fontWeight: FontWeight.w600, color: scheme.onSurface)),
                const SizedBox(height: 14),
                Material(
                  color: tokens.composeField,
                  borderRadius: BorderRadius.circular(14),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(14),
                    onTap: onSearch,
                    child: SizedBox(height: 44, child: Row(children: [
                      const SizedBox(width: 12),
                      Icon(Icons.search, size: 20, color: scheme.onSurfaceVariant),
                      const SizedBox(width: 8),
                      Text(l10n.searchHint, style: TextStyle(color: scheme.onSurfaceVariant)),
                    ])),
                  ),
                ),
              ]),
            ),
          ),
        ];
    }
  }
}
