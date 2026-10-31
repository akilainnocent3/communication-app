import 'dart:math' as math;
import 'dart:ui' show lerpDouble;

import 'package:flutter/material.dart';

import '../skin/tokens.dart';

/// Large headers: the big title (One UI, ColorOS, HyperOS). Everything else has a compact bar.
bool hasLargeHeader(SkinTokens tokens) => tokens.header == HeaderStyle.largeCollapsing || tokens.header == HeaderStyle.largeWithSearch;

/// Section labels, times and keypad letters.
Color secondaryTextOf(BuildContext context) => SkinTokens.of(context).secondaryText ?? Theme.of(context).colorScheme.onSurfaceVariant;

/// A tab's scrolling page under the skin's header: a large title that collapses into a 56 dp bar as the list scrolls
/// and expands again at the top (snapping to the nearer state when the finger lifts), or a pinned compact bar. The
/// header owns the status bar area, so the page has no AppBar of its own.
class SkinnedScrollView extends StatefulWidget {
  const SkinnedScrollView({super.key, required this.title, this.subtitle, this.actions = const [], required this.slivers, this.onRefresh, this.scrollKey});
  final String title;
  final String? subtitle;
  final List<Widget> actions;
  final List<Widget> slivers;
  final RefreshCallback? onRefresh;
  final Key? scrollKey;

  @override
  State<SkinnedScrollView> createState() => _SkinnedScrollViewState();
}

class _SkinnedScrollViewState extends State<SkinnedScrollView> {
  final _controller = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// Large title height above the 56 dp bar: a share of the screen on tall phones, none on short windows (landscape).
  double _expandedExtra(SkinTokens tokens, Size screen) {
    if (screen.height < 520) return 0;
    final share = screen.height * tokens.expandedHeaderFraction - kToolbarHeight;
    return math.max(share, tokens.centeredLargeTitle ? 160 : 72);
  }

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final top = MediaQuery.paddingOf(context).top;
    final large = hasLargeHeader(tokens);
    final extra = large ? _expandedExtra(tokens, MediaQuery.sizeOf(context)) : 0.0;
    final header = large
        ? SliverPersistentHeader(
            pinned: true,
            delegate: _LargeTitleHeader(
              title: widget.title, subtitle: widget.subtitle, actions: widget.actions, top: top, extra: extra, tokens: tokens,
              titleColor: Theme.of(context).colorScheme.onSurface, subtitleColor: secondaryTextOf(context),
            ),
          )
        : SliverAppBar(pinned: true, title: Text(widget.title), actions: widget.actions, backgroundColor: tokens.pageBackground);
    Widget view = CustomScrollView(
      key: widget.scrollKey,
      controller: _controller,
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      slivers: [header, ...widget.slivers, const SliverToBoxAdapter(child: SizedBox(height: 24))],
    );
    if (widget.onRefresh != null) view = RefreshIndicator(edgeOffset: top + kToolbarHeight + extra, onRefresh: widget.onRefresh!, child: view);
    if (extra == 0) return view;
    return NotificationListener<ScrollEndNotification>(
      onNotification: (n) {
        // Never left half collapsed: settle on the nearer state (and never aim past the end of a short list).
        final offset = n.metrics.pixels;
        if (n.depth != 0 || offset <= 0 || offset >= extra) return false;
        final target = math.min(offset < extra / 2 ? 0.0 : extra, n.metrics.maxScrollExtent);
        if ((target - offset).abs() > 1) {
          Future.microtask(() {
            if (_controller.hasClients) _controller.animateTo(target, duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
          });
        }
        return false;
      },
      child: view,
    );
  }
}

class _LargeTitleHeader extends SliverPersistentHeaderDelegate {
  _LargeTitleHeader({
    required this.title, required this.subtitle, required this.actions, required this.top, required this.extra, required this.tokens,
    required this.titleColor, required this.subtitleColor,
  });
  final String title;
  final String? subtitle;
  final List<Widget> actions;
  final double top, extra;
  final SkinTokens tokens;
  final Color titleColor, subtitleColor;

  @override
  double get minExtent => top + kToolbarHeight;
  @override
  double get maxExtent => top + kToolbarHeight + extra;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    final t = extra == 0 ? 1.0 : (shrinkOffset / extra).clamp(0.0, 1.0);
    final centred = tokens.centeredLargeTitle;
    final actionsWidth = actions.length * 48.0 + 12;
    return Material(
      color: tokens.pageBackground,
      child: Padding(
        padding: EdgeInsets.only(top: top),
        child: Stack(
          children: [
            // The title: centred (or bottom-left) above the action row when expanded, at the start of the bar collapsed.
            Positioned(
              left: 20,
              right: lerpDouble(20, actionsWidth, t),
              top: 0,
              bottom: lerpDouble(kToolbarHeight, 0, t),
              child: Align(
                alignment: Alignment.lerp(centred ? Alignment.center : Alignment.bottomLeft, Alignment.centerLeft, t)!,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: centred && t < 0.5 ? CrossAxisAlignment.center : CrossAxisAlignment.start,
                  children: [
                    Semantics(
                      header: true,
                      child: Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: lerpDouble(tokens.largeTitleSize, tokens.titleSize, t), fontWeight: FontWeight.w400, color: titleColor),
                      ),
                    ),
                    if (subtitle != null)
                      ClipRect(
                        child: Align(
                          heightFactor: 1 - t,
                          child: Opacity(
                            opacity: (1 - t * 2).clamp(0.0, 1.0),
                            child: Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(subtitle!, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 16, color: subtitleColor)),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            Positioned(right: 12, bottom: 0, height: kToolbarHeight, child: Row(children: actions)),
          ],
        ),
      ),
    );
  }

  @override
  bool shouldRebuild(_LargeTitleHeader old) =>
      old.title != title || old.subtitle != subtitle || old.actions != actions || old.top != top || old.extra != extra || old.tokens != tokens ||
      old.titleColor != titleColor || old.subtitleColor != subtitleColor;
}

/// The top of a page that does not scroll (the keypad): the action icons on the right for large-header skins, as the
/// phone's own keypad has no title; a compact bar with the title otherwise.
class SkinnedTopBar extends StatelessWidget {
  const SkinnedTopBar({super.key, required this.title, this.actions = const []});
  final String title;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    if (!hasLargeHeader(tokens)) return AppBar(title: Text(title), actions: actions, backgroundColor: tokens.pageBackground, primary: true);
    return SafeArea(
      bottom: false,
      child: SizedBox(
        height: kToolbarHeight,
        child: Padding(padding: const EdgeInsets.only(right: 12), child: Row(mainAxisAlignment: MainAxisAlignment.end, children: actions)),
      ),
    );
  }
}

/// A list section label ("Today", "Favourites", "A"), with an optional small icon before it.
class SectionLabel extends StatelessWidget {
  const SectionLabel(this.label, {super.key, this.icon});
  final String label;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final colour = secondaryTextOf(context);
    final grouped = tokens.groupedList;
    return Padding(
      padding: grouped ? const EdgeInsets.fromLTRB(26, 20, 26, 12) : const EdgeInsets.fromLTRB(16, 16, 16, 4),
      child: Semantics(
        header: true,
        child: Row(
          children: [
            if (icon != null) ...[Icon(icon, size: 16, color: colour), const SizedBox(width: 8)],
            Flexible(
              child: Text(
                label,
                style: grouped
                    ? TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: colour)
                    : Theme.of(context).textTheme.labelLarge?.copyWith(color: colour),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One row of a list section. Grouped skins (One UI) draw a section's rows as one very round card on the tinted page,
/// with dividers inset to the text and the pressed colour clipped to the card; other skins draw a plain row. Rows stay
/// separate widgets, so long lists still build lazily.
class GroupedRow extends StatelessWidget {
  const GroupedRow({super.key, required this.child, this.first = false, this.last = false, this.onTap, this.onLongPress, this.dividerIndent = 72, this.minHeight = 56});
  final Widget child;
  final bool first, last;
  final VoidCallback? onTap, onLongPress;
  final double dividerIndent;
  final double minHeight;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final grouped = tokens.groupedList;
    final r = Radius.circular(tokens.listRadius);
    final divider = !last && (grouped || tokens.dividers);
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: grouped ? tokens.listInset : 0),
      child: Material(
        color: grouped ? tokens.listSurface : Colors.transparent,
        borderRadius: grouped ? BorderRadius.vertical(top: first ? r : Radius.zero, bottom: last ? r : Radius.zero) : null,
        clipBehavior: grouped ? Clip.antiAlias : Clip.none,
        child: InkWell(
          onTap: onTap,
          onLongPress: onLongPress,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ConstrainedBox(constraints: BoxConstraints(minHeight: minHeight), child: child),
              if (divider)
                Padding(
                  padding: EdgeInsets.only(left: dividerIndent, right: grouped ? 26 : 0),
                  child: Container(height: 1, color: tokens.divider ?? Theme.of(context).colorScheme.outlineVariant),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Text-only bottom tabs (One UI): equal widths, the selected label darker and medium weight, with a rounded underline
/// as wide as its text that slides between tabs. [badges] puts a small count after a label.
class TextTabBar extends StatelessWidget {
  const TextTabBar({super.key, required this.labels, required this.selected, required this.onSelected, this.badges = const {}});
  final List<String> labels;
  final int selected;
  final ValueChanged<int> onSelected;
  final Map<int, int> badges;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final scheme = Theme.of(context).colorScheme;
    final active = scheme.onSurface;
    final inactive = secondaryTextOf(context);
    final scaler = MediaQuery.textScalerOf(context);
    TextStyle style(bool on) => TextStyle(fontSize: 15, fontWeight: on ? FontWeight.w500 : FontWeight.w400, color: on ? active : inactive);
    return Material(
      color: tokens.pageBackground,
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: LayoutBuilder(builder: (context, constraints) {
            final width = constraints.maxWidth / labels.length;
            final painter = TextPainter(text: TextSpan(text: labels[selected], style: style(true)), textDirection: Directionality.of(context), textScaler: scaler, maxLines: 1)
              ..layout(maxWidth: width - 16);
            final textWidth = painter.width;
            painter.dispose();
            return Stack(
              children: [
                Row(
                  children: [
                    for (var i = 0; i < labels.length; i++)
                      Expanded(
                        child: Semantics(
                          selected: i == selected,
                          button: true,
                          child: InkWell(
                            onTap: () => onSelected(i),
                            child: Center(
                              child: Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Flexible(child: Text(labels[i], maxLines: 1, overflow: TextOverflow.ellipsis, style: style(i == selected))),
                                    if ((badges[i] ?? 0) > 0) ...[
                                      const SizedBox(width: 4),
                                      Badge(label: Text('${badges[i]}'), backgroundColor: tokens.badge, textColor: tokens.onBadge),
                                    ],
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
                AnimatedPositioned(
                  duration: const Duration(milliseconds: 200),
                  curve: Curves.easeOut,
                  left: width * selected + (width - textWidth) / 2,
                  width: textWidth,
                  bottom: 19, // 6 dp under the label
                  height: 3,
                  child: IgnorePointer(child: DecoratedBox(decoration: BoxDecoration(color: active, borderRadius: BorderRadius.circular(2)))),
                ),
              ],
            );
          }),
        ),
      ),
    );
  }
}

/// A tab while its search is open: a back arrow and the search field in place of the header, results under it.
class SkinnedSearchView extends StatelessWidget {
  const SkinnedSearchView({super.key, required this.hint, required this.onChanged, required this.onClose, required this.slivers});
  final String hint;
  final ValueChanged<String> onChanged;
  final VoidCallback onClose;
  final List<Widget> slivers;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) onClose();
      },
      child: Column(
        children: [
          Material(
            color: tokens.pageBackground,
            child: SafeArea(
              bottom: false,
              child: SizedBox(
                height: kToolbarHeight,
                child: Row(
                  children: [
                    BackButton(onPressed: onClose),
                    Expanded(
                      child: TextField(
                        autofocus: true,
                        onChanged: onChanged,
                        textInputAction: TextInputAction.search,
                        decoration: InputDecoration(hintText: hint, border: InputBorder.none),
                      ),
                    ),
                    const SizedBox(width: 16),
                  ],
                ),
              ),
            ),
          ),
          Expanded(
            child: CustomScrollView(
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              slivers: [...slivers, const SliverToBoxAdapter(child: SizedBox(height: 24))],
            ),
          ),
        ],
      ),
    );
  }
}
