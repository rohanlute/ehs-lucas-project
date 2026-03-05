from django.contrib import admin
from .models import (
    BusinessType,
    Domain,
    Category,
    SubCategory,
)


# ===============================
# Business Type
# ===============================
@admin.register(BusinessType)
class BusinessTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


# ===============================
# Domain
# ===============================
@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("name", "business_type", "is_active")
    list_filter = ("business_type", "is_active")
    search_fields = ("name",)


# ===============================
# Category
# ===============================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "is_active")
    list_filter = ("domain", "is_active")
    search_fields = ("name",)


# ===============================
# SubCategory
# ===============================
@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "is_active",
        "created_at",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name",)

