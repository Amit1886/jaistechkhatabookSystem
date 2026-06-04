import 'package:flutter/material.dart';

import '../../models/enterprise_app_config.dart';
import 'enterprise_glass.dart';
import 'enterprise_icons.dart';

class EnterpriseRuntimeButton extends StatelessWidget {
  const EnterpriseRuntimeButton({
    super.key,
    required this.button,
    required this.onPressed,
  });

  final EnterpriseActionButton button;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final radius = switch (button.shape) {
      'pill' => 999.0,
      'square' => 4.0,
      'circle' => 999.0,
      _ => 8.0,
    };
    return Tooltip(
      message: button.label,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(radius),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          constraints: const BoxConstraints(minHeight: 52),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: button.gradient),
            borderRadius: BorderRadius.circular(radius),
            border: Border.all(color: Colors.white.withValues(alpha: 0.16)),
            boxShadow: [
              BoxShadow(
                color: button.color.withValues(alpha: 0.22),
                blurRadius: button.primary ? 14 : 8,
                spreadRadius: button.primary ? 1 : 0,
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(EnterpriseIcons.fromName(button.icon), color: Colors.white, size: 20),
              if (button.shape != 'circle') ...[
                const SizedBox(width: 10),
                Flexible(
                  child: Text(
                    button.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class EnterpriseActionStrip extends StatelessWidget {
  const EnterpriseActionStrip({
    super.key,
    required this.buttons,
    required this.onPressed,
  });

  final List<EnterpriseActionButton> buttons;
  final ValueChanged<EnterpriseActionButton> onPressed;

  @override
  Widget build(BuildContext context) {
    final sorted = [...buttons]..sort((a, b) => a.order.compareTo(b.order));
    if (sorted.isEmpty) return const SizedBox.shrink();
    return SizedBox(
      height: 60,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: sorted.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final button = sorted[index];
          return EnterpriseRuntimeButton(
            button: button,
            onPressed: () => onPressed(button),
          );
        },
      ),
    );
  }
}

class EnterpriseLauncherGrid extends StatelessWidget {
  const EnterpriseLauncherGrid({
    super.key,
    required this.items,
    required this.onLaunch,
  });

  final List<EnterpriseLauncherItem> items;
  final ValueChanged<EnterpriseLauncherItem> onLaunch;

  @override
  Widget build(BuildContext context) {
    final sorted = [...items]..sort((a, b) => a.order.compareTo(b.order));
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth > 760 ? 5 : constraints.maxWidth > 460 ? 3 : 2;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: sorted.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            mainAxisExtent: 104,
          ),
          itemBuilder: (context, index) {
            final item = sorted[index];
            return InkWell(
              onTap: () => onLaunch(item),
              borderRadius: BorderRadius.circular(8),
              child: EnterpriseGlass(
                radius: 8,
                opacity: 0.72,
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(EnterpriseIcons.fromName(item.icon), color: item.color),
                    const Spacer(),
                    Text(
                      item.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class EnterpriseSkeleton extends StatefulWidget {
  const EnterpriseSkeleton({super.key, this.rows = 4});

  final int rows;

  @override
  State<EnterpriseSkeleton> createState() => _EnterpriseSkeletonState();
}

class _EnterpriseSkeletonState extends State<EnterpriseSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final opacity = 0.18 + (_controller.value * 0.16);
        return Column(
          children: [
            for (var i = 0; i < widget.rows; i++) ...[
              Container(
                height: i == 0 ? 92 : 54,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: opacity),
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              if (i != widget.rows - 1) const SizedBox(height: 10),
            ],
          ],
        );
      },
    );
  }
}
