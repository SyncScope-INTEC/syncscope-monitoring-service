from django.contrib import admin

from .admin_auth import monitoring_admin_site
from .models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent


# Monkey patch LogEntry to avoid UUID/integer conflicts
def safe_log_action(self, user_id, content_type_id, object_id, object_repr, action_flag, change_message=""):
    """
    Safe logging that doesn't create entries to avoid UUID/integer type conflicts.
    This is a temporary fix until the database schema is properly synchronized.
    """
    # Skip logging to avoid UUID/integer type mismatch errors
    pass


# Monkey patch AdminSite index to avoid LogEntry queries
def safe_index(self, request, extra_context=None):
    """
    Safe admin index that doesn't query recent actions to avoid UUID/integer conflicts.
    """
    from django.contrib.admin.sites import AdminSite
    from django.shortcuts import render

    # Get the original index context without recent actions
    app_list = safe_get_app_list(self, request)
    context = {
        **self.each_context(request),
        "title": self.index_title,
        "subtitle": None,
        "app_list": app_list,
        "username": request.user.get_username() if hasattr(request, "user") else None,
        **(extra_context or {}),
    }

    return render(request, self.index_template or "admin/index.html", context)


def safe_get_app_list(self, request):
    """
    Safe get_app_list that doesn't include recent actions to avoid LogEntry queries.
    """
    app_dict = {}

    for model, model_admin in self._registry.items():
        app_label = model._meta.app_label

        has_module_perms = model_admin.has_module_permission(request)
        if not has_module_perms:
            continue

        perms = model_admin.get_model_perms(request)
        if True not in perms.values():
            continue

        info = (app_label, model._meta.model_name)
        model_dict = {
            "name": str(model._meta.verbose_name_plural),
            "object_name": model._meta.object_name,
            "perms": perms,
            "admin_url": None,
            "add_url": None,
        }
        if perms.get("change") or perms.get("view"):
            model_dict["view_only"] = not perms.get("change")
            try:
                from django.urls import reverse

                model_dict["admin_url"] = reverse("admin:%s_%s_changelist" % info)
            except:
                pass
        if perms.get("add"):
            try:
                from django.urls import reverse

                model_dict["add_url"] = reverse("admin:%s_%s_add" % info)
            except:
                pass

        if app_label in app_dict:
            app_dict[app_label]["models"].append(model_dict)
        else:
            from django.urls import reverse

            try:
                app_url = reverse("admin:app_list", kwargs={"app_label": app_label})
            except:
                app_url = "#"

            app_dict[app_label] = {
                "name": app_label.title(),
                "app_label": app_label,
                "app_url": app_url,
                "has_module_perms": has_module_perms,
                "models": [model_dict],
            }

    app_list = sorted(app_dict.values(), key=lambda x: x["name"].lower())
    return app_list


# Apply the monkey patches
admin.ModelAdmin.log_action = safe_log_action
admin.site.index = safe_index.__get__(admin.site, admin.AdminSite)
admin.site.get_app_list = safe_get_app_list.__get__(admin.site, admin.AdminSite)
monitoring_admin_site.index = safe_index.__get__(monitoring_admin_site, admin.AdminSite)
monitoring_admin_site.get_app_list = safe_get_app_list.__get__(monitoring_admin_site, admin.AdminSite)


class DeveloperSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "user_id", "ide_name", "session_start", "session_end", "is_active")
    list_filter = ("ide_name", "operating_system", "session_start")
    search_fields = ("user_id", "ide_name", "git_repository_url")
    readonly_fields = ("session_id", "created_at", "updated_at", "session_duration_minutes")
    ordering = ("-created_at",)


class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("log_id", "session", "activity_type", "timestamp", "file_path")
    list_filter = ("activity_type", "file_extension", "timestamp")
    search_fields = ("session__session_id", "file_path")
    readonly_fields = ("log_id", "created_at")
    ordering = ("-timestamp",)


class CodeMetricsAdmin(admin.ModelAdmin):
    list_display = ("metrics_id", "session", "file_path", "lines_of_code", "total_changes", "calculated_at")
    list_filter = ("file_extension", "calculated_at")
    search_fields = ("session__session_id", "file_path")
    readonly_fields = ("metrics_id", "created_at")
    ordering = ("-calculated_at",)


class GitEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "session", "event_type", "commit_hash", "branch_name", "timestamp")
    list_filter = ("event_type", "branch_name", "timestamp")
    search_fields = ("session__session_id", "commit_hash", "commit_message", "author_email")
    readonly_fields = ("event_id", "created_at")
    ordering = ("-timestamp",)


# Register models with both the default admin and custom admin
admin.site.register(DeveloperSession, DeveloperSessionAdmin)
admin.site.register(ActivityLog, ActivityLogAdmin)
admin.site.register(CodeMetrics, CodeMetricsAdmin)
admin.site.register(GitEvent, GitEventAdmin)

# Also register with custom admin site
monitoring_admin_site.register(DeveloperSession, DeveloperSessionAdmin)
monitoring_admin_site.register(ActivityLog, ActivityLogAdmin)
monitoring_admin_site.register(CodeMetrics, CodeMetricsAdmin)
monitoring_admin_site.register(GitEvent, GitEventAdmin)
