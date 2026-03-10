from django.db import models
from apps.organizations.models import Plant


class WasteReportData(models.Model):

    REPORT_TYPE_CHOICES = (
        ("MANUFACTURING", "Manufacturing Waste"),
        ("NON_MANUFACTURING", "Non Manufacturing Waste"),
    )

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE
    )

    year = models.IntegerField()

    report_type = models.CharField(
        max_length=30,
        choices=REPORT_TYPE_CHOICES
    )

    row_name = models.CharField(max_length=255)

    part_code = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    treatment = models.CharField(
        max_length=10,
        choices=[
            ("R", "Recycling"),
            ("D", "Disposal"),
            ("S", "Storage"),
        ],
        blank=True,
        null=True
    )

    # ================= MONTHLY QTY =================

    jan_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    feb_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mar_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    apr_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    may_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    jun_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    jul_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    aug_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sep_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    oct_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nov_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dec_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ================= MONTHLY COST =================

    jan_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    feb_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mar_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    apr_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    may_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    jun_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    jul_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    aug_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sep_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    oct_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nov_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dec_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ================= QUARTERS =================

    q1_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    q2_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    q3_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    q4_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    q1_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    q2_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    q3_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    q4_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ================= YEAR TOTAL =================

    total_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    total_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    # ================= AUDIT FIELDS =================

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "plant",
            "year",
            "report_type",
            "row_name",
        )

    def __str__(self):
        return f"{self.plant.name} - {self.row_name} - {self.year}"
    


class WasteSummary(models.Model):

    SUMMARY_TYPE_CHOICES = (
        ("NON_HAZ", "Total Non Hazardous Waste"),
        ("HAZ_PROCESS", "Total Hazardous Waste (Process)"),
        ("E_WASTE", "Total E Waste"),
        ("GRAND_WASTE", "Grand Total Waste"),
        ("PRODUCTION", "Production in Month"),
        ("NON_HAZ_UNIT", "Non Hazardous Waste per Unit"),
        ("PROC_HAZ_UNIT", "Process Hazardous Waste per Unit"),
        ("NON_PROC_HAZ", "Non Process Hazardous Waste"),
        ("DIVERSION_RATE", "Diversion Rate"),
    )

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE)

    year = models.IntegerField()

    report_type = models.CharField(max_length=30)

    summary_type = models.CharField(max_length=50, choices=SUMMARY_TYPE_CHOICES)

    # MONTHLY QTY

    jan_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    feb_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    mar_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    apr_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    may_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    jun_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    jul_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    aug_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sep_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    oct_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nov_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    dec_qty = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # MONTHLY COST

    jan_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    feb_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    mar_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    apr_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    may_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    jun_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    jul_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    aug_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sep_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    oct_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nov_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    dec_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # QUARTERS

    q1_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    q2_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    q3_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    q4_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    q1_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    q2_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    q3_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    q4_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    total_quantity = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        unique_together = ("plant","year","report_type","summary_type")





# 
class EnvironmentEntry(models.Model):

    REPORT_TYPE_CHOICES = (
        ("MANUFACTURING_ENV", "Manufacturing Environment"),
        ("NON_MANUFACTURING_ENV", "Non Manufacturing Environment"),
    )

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE)

    year = models.IntegerField()

    report_type = models.CharField(
        max_length=50,
        choices=REPORT_TYPE_CHOICES
    )

    row_name = models.CharField(max_length=200)

    # Manufacturing Year Data
    year_2024 = models.FloatField(default=0)
    year_2025 = models.FloatField(default=0)

    # MONTHLY
    jan_qty = models.FloatField(default=0)
    feb_qty = models.FloatField(default=0)
    mar_qty = models.FloatField(default=0)

    apr_qty = models.FloatField(default=0)
    may_qty = models.FloatField(default=0)
    jun_qty = models.FloatField(default=0)

    jul_qty = models.FloatField(default=0)
    aug_qty = models.FloatField(default=0)
    sep_qty = models.FloatField(default=0)

    oct_qty = models.FloatField(default=0)
    nov_qty = models.FloatField(default=0)
    dec_qty = models.FloatField(default=0)

    # QUARTERS
    q1_quantity = models.FloatField(default=0)
    q2_quantity = models.FloatField(default=0)
    q3_quantity = models.FloatField(default=0)
    q4_quantity = models.FloatField(default=0)

    total_quantity = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "plant",
            "year",
            "report_type",
            "row_name"
        )
    def __str__(self):
        return f"{self.row_name} - {self.plant.name} - {self.year}"