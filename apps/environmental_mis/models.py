from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.ENVdata.models import Unit

User = get_user_model()


# =====================================================
# 1️⃣ BUSINESS TYPE
# =====================================================

class BusinessType(models.Model):

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="env_business_types_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# =====================================================
# 2️⃣ DOMAIN
# =====================================================

class Domain(models.Model):

    business_type = models.ForeignKey(
        BusinessType,
        on_delete=models.CASCADE,
        related_name="domains"
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("business_type", "name")
        ordering = ["business_type", "name"]

    def __str__(self):
        return f"{self.business_type.name} - {self.name}"


# =====================================================
# 3️⃣ CATEGORY
# =====================================================

class Category(models.Model):

    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        related_name="categories"
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("domain", "name")
        ordering = ["domain", "name"]

    def __str__(self):
        return f"{self.domain.name} - {self.name}"


# =====================================================
# 4️⃣ SUB CATEGORY (CONFIG LEVEL)
# =====================================================

class SubCategory(models.Model):

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories"
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("category", "name")
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.category.name} - {self.name}"


# =====================================================
# 5️⃣ ENVIRONMENTAL MIS – MONTHLY DATA
# =====================================================

class EnvironmentalMISMonthlyData(models.Model):

    TREATMENT_CHOICES = (
        ("R", "Recycled"),
        ("Inci", "Incinerated"),
        ("LF", "Landfill"),
        ("NA", "Not Applicable"),
    )

    plant = models.ForeignKey(
        "organizations.Plant",
        on_delete=models.CASCADE
    )

    business_type = models.ForeignKey(
        "environmental_mis.BusinessType",
        on_delete=models.CASCADE
    )

    domain = models.ForeignKey(
        "environmental_mis.Domain",
        on_delete=models.CASCADE
    )

    category = models.ForeignKey(
        "environmental_mis.Category",
        on_delete=models.CASCADE
    )

    subcategory = models.ForeignKey(
        "environmental_mis.SubCategory",
        on_delete=models.CASCADE
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT
    )

    year = models.IntegerField()

    # ================= MONTH =================
    MONTH_CHOICES = [
        ("JAN", "January"),
        ("FEB", "February"),
        ("MAR", "March"),
        ("APR", "April"),
        ("MAY", "May"),
        ("JUN", "June"),
        ("JUL", "July"),
        ("AUG", "August"),
        ("SEP", "September"),
        ("OCT", "October"),
        ("NOV", "November"),
        ("DEC", "December"),
    ]

    month = models.CharField(max_length=3, choices=MONTH_CHOICES)

    # ================= VALUES =================
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=0
    )

    cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    treatment_type = models.CharField(
        max_length=10,
        choices=TREATMENT_CHOICES,
        blank=True,
        null=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "plant",
            "subcategory",
            "year",
            "month",
        )
        ordering = ["-year", "month"]

    def __str__(self):
        return f"{self.plant.name} - {self.subcategory.name} - {self.month} {self.year}"
    




# =====================================================
# 6️⃣ ENVIRONMENTAL MIS – QUARTERLY DATA
# =====================================================

class EnvironmentalMISQuarterlyData(models.Model):

    plant = models.ForeignKey(
        "organizations.Plant",
        on_delete=models.CASCADE
    )

    report_config = models.ForeignKey(
        "environmental_mis.EnvironmentalMISReportConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    business_type = models.ForeignKey(
        "environmental_mis.BusinessType",
        on_delete=models.CASCADE
    )

    domain = models.ForeignKey(
        "environmental_mis.Domain",
        on_delete=models.CASCADE
    )

    category = models.ForeignKey(
        "environmental_mis.Category",
        on_delete=models.CASCADE
    )

    subcategory = models.ForeignKey(
        "environmental_mis.SubCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )

    year = models.IntegerField()

    question_text = models.CharField(max_length=500,blank=True,null=True)
    # ================= PART CODE / TREATMENT =================

    part_code = models.CharField(max_length=100, blank=True, null=True)

    TREATMENT_CHOICES = (
        ("R", "Recycling"),
        ("D", "Disposal"),
        ("S", "Storage"),
    )

    treatment = models.CharField(
        max_length=2,
        choices=TREATMENT_CHOICES,
        blank=True,
        null=True
    )

    # ================= MONTHLY DATA =================

    jan_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    jan_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    feb_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    feb_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    mar_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    mar_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    apr_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    apr_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    may_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    may_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    jun_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    jun_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    jul_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    jul_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    aug_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    aug_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    sep_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    sep_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    oct_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    oct_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    nov_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    nov_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    dec_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    dec_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # ================= QUARTERS =================

    q1_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    q1_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    q2_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    q2_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    q3_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    q3_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    q4_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    q4_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # ================= TOTAL =================

    total_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "plant",
            "report_config",
            "year",
        )

    def __str__(self):
        return f"{self.plant.name} - {self.report_config.question_text} - {self.year}"
    
# =====================================================
# 7️⃣ ENVIRONMENTAL MIS – REPORT CONFIGURATION
# =====================================================

class EnvironmentalMISReportConfig(models.Model):

    business_type = models.ForeignKey(
        BusinessType,
        on_delete=models.CASCADE,
        related_name="report_configs"
    )

    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        related_name="report_configs"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="report_configs"
    )

    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="report_configs"
    )

    question_text = models.CharField(max_length=500)

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="mis_report_units"
    )

    order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["business_type", "domain", "category", "order"]
        unique_together = (
            "business_type",
            "domain",
            "category",
            "question_text",
        )

    def clean(self):
        if self.domain.business_type != self.business_type:
            raise ValidationError(
                "Domain does not belong to selected Business Type."
            )

        if self.category.domain != self.domain:
            raise ValidationError(
                "Category does not belong to selected Domain."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.business_type.name} | "
            f"{self.domain.name} | "
            f"{self.category.name} | "
            f"{self.question_text}"
        )