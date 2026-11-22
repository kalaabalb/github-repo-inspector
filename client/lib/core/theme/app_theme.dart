import 'package:flutter/material.dart';

/// Colour palette for the whole app.
class AppColors {
  AppColors._();

  static const background = Color(0xFF070B14);
  static const surface = Color(0xFF0F1626);
  static const surfaceHigh = Color(0xFF16203A);
  static const border = Color(0xFF243152);

  static const primary = Color(0xFF7C5CFF);
  static const secondary = Color(0xFF22D3EE);
  static const accent = Color(0xFFFFB454);

  static const success = Color(0xFF34D399);
  static const warning = Color(0xFFFBBF24);
  static const orange = Color(0xFFFB923C);
  static const danger = Color(0xFFFB7185);

  static const textPrimary = Color(0xFFF1F5FF);
  static const textSecondary = Color(0xFF9AA8C7);
  static const textMuted = Color(0xFF66738F);

  static const brandGradient = LinearGradient(
    colors: [primary, secondary],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

/// Text styles used across the app.
class AppText {
  AppText._();

  static const display = TextStyle(
    fontSize: 46,
    height: 1.08,
    fontWeight: FontWeight.w800,
    letterSpacing: -1.6,
    color: AppColors.textPrimary,
  );
  static const h2 = TextStyle(
    fontSize: 26,
    height: 1.2,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.6,
    color: AppColors.textPrimary,
  );
  static const h3 = TextStyle(
    fontSize: 18,
    height: 1.3,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );
  static const title = TextStyle(
    fontSize: 15.5,
    height: 1.35,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );
  static const lead = TextStyle(
    fontSize: 17,
    height: 1.55,
    color: AppColors.textSecondary,
  );
  static const body = TextStyle(
    fontSize: 14.5,
    height: 1.55,
    color: AppColors.textSecondary,
  );
  static const bodyStrong = TextStyle(
    fontSize: 14.5,
    height: 1.5,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );
  static const small = TextStyle(
    fontSize: 12.5,
    height: 1.45,
    color: AppColors.textMuted,
  );
  static const label = TextStyle(
    fontSize: 11.5,
    fontWeight: FontWeight.w700,
    letterSpacing: 1.4,
    color: AppColors.textMuted,
  );
}

/// Monospace style for paths and code-like values.
TextStyle monoStyle({Color color = AppColors.secondary, double size = 12.5}) {
  return TextStyle(
    fontFamily: 'monospace',
    fontFamilyFallback: const ['Menlo', 'Consolas', 'Courier New'],
    fontSize: size,
    height: 1.45,
    color: color,
  );
}

class AppTheme {
  static ThemeData dark() {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          brightness: Brightness.dark,
        ).copyWith(
          primary: AppColors.primary,
          secondary: AppColors.secondary,
          surface: AppColors.surface,
          onSurface: AppColors.textPrimary,
          error: AppColors.danger,
        );
    final inputBorder = OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: const BorderSide(color: AppColors.border),
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: 'Roboto',
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.background,
      canvasColor: AppColors.background,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        margin: EdgeInsets.zero,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.background.withValues(alpha: 0.65),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 18,
        ),
        hintStyle: const TextStyle(color: AppColors.textMuted),
        border: inputBorder,
        enabledBorder: inputBorder,
        disabledBorder: inputBorder,
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.secondary, width: 1.6),
        ),
      ),
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: AppColors.surfaceHigh,
        contentTextStyle: TextStyle(color: AppColors.textPrimary),
        behavior: SnackBarBehavior.floating,
      ),
      dividerColor: AppColors.border,
    );
  }
}
