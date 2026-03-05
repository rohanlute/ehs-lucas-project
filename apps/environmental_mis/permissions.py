from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse


# =====================================================
# ENV MODULE ACCESS CHECK
# =====================================================

def env_module_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        user = request.user

        # Not logged in
        if not user.is_authenticated:
            return redirect("login")

        # Check module permission
        has_access = getattr(user, "can_access_env_data_module", False)

        if not has_access and not user.is_superuser:

            # AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "error": "You do not have access to Environmental MIS module."
                    },
                    status=403
                )

            # Normal request
            messages.error(
                request,
                "You do not have access to Environmental MIS module."
            )
            return redirect("environmental_mis:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


# =====================================================
# ADMIN ONLY CHECK
# =====================================================

def admin_env_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        user = request.user

        # Allow Django superuser
        if user.is_superuser:
            return view_func(request, *args, **kwargs)

        # Allow custom role-based admin
        if getattr(user, "is_admin_user", False):
            return view_func(request, *args, **kwargs)

        # AJAX request
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": False,
                    "error": "Only Admin can perform this action."
                },
                status=403
            )

        # Normal request
        messages.error(request, "Only Admin can perform this action.")
        return redirect("environmental_mis:dashboard")

    return wrapper