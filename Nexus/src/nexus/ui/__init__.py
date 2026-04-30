"""Nexus UI — design tokens, theme system, model routing, and hardware detection."""
from nexus.ui.tokens import (
    DARK_THEME,
    LIGHT_THEME,
    ALL_THEMES,
    ANSI_MAP,
    get_ansi_style,
    get_theme,
    get_css_variables,
    get_token,
    print_theme_sample,
    SPACING,
    ANIMATION,
    RADIUS,
    FONTS,
    EASING,
)
from nexus.ui.model_routing import (
    MODEL_REGISTRY,
    TASK_ROUTES,
    get_model_for_task,
    get_fallback_model,
    get_timeout_for_model,
    list_available_models,
    print_model_summary,
    ModelProfile,
)
from nexus.ui.hardware import (
    HardwareProfile,
    detect_hardware,
    get_recommendations,
    generate_routing_config,
    print_hardware_report,
    print_recommendation_report,
    MODEL_SIZES_GB,
)
