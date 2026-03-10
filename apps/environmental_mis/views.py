import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from apps.organizations.models import Plant
from .models import WasteReportData, WasteSummary
from .report_structure import MANUFACTURING_WASTE_STRUCTURE
from django.db.models import Sum
from .models import EnvironmentEntry


def manufacturing_waste_report(request):

    user_plants = Plant.objects.all()

    plant_id = request.GET.get("plant_id")
    waste_type = request.GET.get("waste_type", "MANUFACTURING")

    if plant_id:
        plant = Plant.objects.get(id=plant_id)
    else:
        plant = user_plants.first()

    year = timezone.now().year

    # ================= MAIN REPORT DATA =================

    report_data = WasteReportData.objects.filter(
        plant=plant,
        year=year,
        report_type=waste_type
    )

    data_map = {d.row_name: d for d in report_data}

    # ================= SUMMARY DATA =================

    summary_data = WasteSummary.objects.filter(
        plant=plant,
        year=year,
        report_type=waste_type
    )

    summary_map = {s.summary_type: s for s in summary_data}


    # ================= PRODUCTION FROM ENVIRONMENT REPORT =================
    # ================= SELECT ENVIRONMENT REPORT TYPE =================

    if waste_type == "MANUFACTURING":
        env_report_type = "MANUFACTURING_ENV"
    else:
        env_report_type = "NON_MANUFACTURING_ENV"


    # ================= PRODUCTION FROM ENVIRONMENT REPORT =================

    env_entries = EnvironmentEntry.objects.filter(
        plant=plant,
        year=year,
        report_type=env_report_type
    )

    prod = env_entries.aggregate(
        jan=Sum("jan_qty"),
        feb=Sum("feb_qty"),
        mar=Sum("mar_qty"),

        apr=Sum("apr_qty"),
        may=Sum("may_qty"),
        jun=Sum("jun_qty"),

        jul=Sum("jul_qty"),
        aug=Sum("aug_qty"),
        sep=Sum("sep_qty"),

        oct=Sum("oct_qty"),
        nov=Sum("nov_qty"),
        dec=Sum("dec_qty"),
    )

    # replace None with 0
    for k,v in prod.items():
        prod[k] = v or 0

    # quarters
    prod["q1"] = prod["jan"] + prod["feb"] + prod["mar"]
    prod["q2"] = prod["apr"] + prod["may"] + prod["jun"]
    prod["q3"] = prod["jul"] + prod["aug"] + prod["sep"]
    prod["q4"] = prod["oct"] + prod["nov"] + prod["dec"]

    # yearly total
    prod["total"] = sum([
        prod["jan"],prod["feb"],prod["mar"],
        prod["apr"],prod["may"],prod["jun"],
        prod["jul"],prod["aug"],prod["sep"],
        prod["oct"],prod["nov"],prod["dec"]
    ])

    # ================= CONTEXT =================

    context = {
        "report_rows": MANUFACTURING_WASTE_STRUCTURE,
        "data_map": data_map,
        "summary_map": summary_map,   
        "production_summary": prod,
        "selected_plant": plant,
        "user_plants": user_plants,
        "current_year": year,
        "selected_type": waste_type
    }

    return render(
        request,
        "environmental_mis/manufacturing_waste_report.html",
        context
    )


import json
from django.http import JsonResponse
from django.utils import timezone
from .models import WasteReportData, WasteSummary
from apps.organizations.models import Plant

from django.http import JsonResponse
from django.utils import timezone
import json

from .models import WasteReportData, WasteSummary
from apps.organizations.models import Plant


def save_waste_report(request):

    if request.method != "POST":
        return JsonResponse({"status":"error"},status=400)

    data=json.loads(request.body)

    rows=data.get("rows",[])
    summary=data.get("summary",[])

    plant_id=request.GET.get("plant_id")
    waste_type=request.GET.get("type","manufacturing")

    report_type="MANUFACTURING" if waste_type=="manufacturing" else "NON_MANUFACTURING"

    plant=Plant.objects.get(id=plant_id)

    year=timezone.now().year


    # ================= MAIN TABLE =================

    for row in rows:

        row_name=row.pop("row_name")

        WasteReportData.objects.update_or_create(

            plant=plant,
            year=year,
            report_type=report_type,
            row_name=row_name,

            defaults=row

        )


    # ================= SUMMARY TABLE =================

    for item in summary:

        summary_type=item.pop("summary_type")

        WasteSummary.objects.update_or_create(

            plant=plant,
            year=year,
            report_type=report_type,
            summary_type=summary_type,

            defaults=item

        )


    return JsonResponse({"status":"success"})










import json

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.organizations.models import Plant
from .models import EnvironmentEntry


# ===============================
# ENVIRONMENT REPORT PAGE
# ===============================
from django.shortcuts import render
from django.utils import timezone
from .report_structure import (
    MANUFACTURING_ENVIRONMENT_STRUCTURE,
    NON_MANUFACTURING_ENVIRONMENT_STRUCTURE
)

def prepare_rows(structure):

    rows = []
    current_section = ""

    for r in structure:

        row = r.copy()

        if row.get("section"):
            current_section = row["section"]

        row["category"] = current_section
        row["subcategory"] = row.get("sub_section", "")

        row["question"] = row.get("question", "")
        row["unit_category"] = row.get("unit_category", "")
        row["unit"] = row.get("unit", "")
        row["row_key"] = row.get("row_key", "")

        rows.append(row)

    # ================= CATEGORY ROWSPAN =================

    category_counts = {}

    for row in rows:
        cat = row["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    shown_category = set()

    for row in rows:

        cat = row["category"]

        if cat not in shown_category:
            row["category_rowspan"] = category_counts[cat]
            shown_category.add(cat)
        else:
            row["category_rowspan"] = None


    # ================= SUBCATEGORY ROWSPAN =================

    subcategory_counts = {}

    for row in rows:

        key = (row["category"], row["subcategory"])

        if row["subcategory"]:
            subcategory_counts[key] = subcategory_counts.get(key, 0) + 1


    shown_subcategory = set()

    for row in rows:

        key = (row["category"], row["subcategory"])

        if not row["subcategory"]:
            row["subcategory_rowspan"] = None
            continue

        if key not in shown_subcategory:
            row["subcategory_rowspan"] = subcategory_counts[key]
            shown_subcategory.add(key)
        else:
            row["subcategory_rowspan"] = None

    return rows












from .models import EnvironmentEntry

def environment_report(request):

    user_plants = Plant.objects.all()

    selected_type = request.GET.get("type", "MANUFACTURING")
    plant_id = request.GET.get("plant_id")

    if plant_id:
        plant = Plant.objects.get(id=plant_id)
    else:
        plant = user_plants.first()

    year = timezone.now().year

    manufacturing_rows = prepare_rows(MANUFACTURING_ENVIRONMENT_STRUCTURE)
    non_manufacturing_rows = prepare_rows(NON_MANUFACTURING_ENVIRONMENT_STRUCTURE)

    months = [
        "jan","feb","mar",
        "apr","may","jun",
        "jul","aug","sep",
        "oct","nov","dec"
    ]

    report_type = (
        "MANUFACTURING_ENV"
        if selected_type == "MANUFACTURING"
        else "NON_MANUFACTURING_ENV"
    )

    # ================= LOAD SAVED DATA =================

    saved_entries = EnvironmentEntry.objects.filter(
        plant=plant,
        year=year,
        report_type=report_type
    )

    data_map = {
        entry.row_name: entry
        for entry in saved_entries
    }

    context = {
        "manufacturing_rows": manufacturing_rows,
        "non_manufacturing_rows": non_manufacturing_rows,
        "months": months,
        "selected_type": selected_type,
        "selected_plant": plant,
        "user_plants": user_plants,
        "current_year": year,
        "data_map": data_map
    }

    return render(
        request,
        "environmental_mis/environment_report.html",
        context
    )

# ===============================
# SAVE DATA API
# ===============================
def save_environment_report(request):

    if request.method != "POST":
        return JsonResponse({"status": "error"})

    data = json.loads(request.body)

    plant_id = data.get("plant_id")
    report_type = data.get("report_type")
    year = data.get("year")

    rows = data.get("rows", [])

    plant = Plant.objects.get(id=plant_id)

    if report_type == "MANUFACTURING":
        report_type = "MANUFACTURING_ENV"
    else:
        report_type = "NON_MANUFACTURING_ENV"

    months = [
        "jan_qty","feb_qty","mar_qty","apr_qty","may_qty","jun_qty",
        "jul_qty","aug_qty","sep_qty","oct_qty","nov_qty","dec_qty"
    ]

    for row in rows:

        row_name = row.get("row_name")

        # Convert empty values to 0
        for m in months:
            val = row.get(m)
            row[m] = float(val) if val not in ["", None] else 0

        # Calculate totals
        row["total_quantity"] = sum(row[m] for m in months)

        row["q1_quantity"] = row["jan_qty"] + row["feb_qty"] + row["mar_qty"]
        row["q2_quantity"] = row["apr_qty"] + row["may_qty"] + row["jun_qty"]
        row["q3_quantity"] = row["jul_qty"] + row["aug_qty"] + row["sep_qty"]
        row["q4_quantity"] = row["oct_qty"] + row["nov_qty"] + row["dec_qty"]

        EnvironmentEntry.objects.update_or_create(
            plant=plant,
            year=year,
            report_type=report_type,
            row_name=row_name,
            defaults=row
        )

    return JsonResponse({"status": "success"})


# ===============================
# ANALYTICAL DASHBOARD
# ===============================

from django.shortcuts import render
from django.utils import timezone
from apps.organizations.models import Plant
from .models import EnvironmentEntry


def environment_dashboard(request):

    user_plants = Plant.objects.all()

    plant_id = request.GET.get("plant_id")
    selected_type = request.GET.get("type", "MANUFACTURING")

    year = timezone.now().year

    report_type = (
        "MANUFACTURING_ENV"
        if selected_type == "MANUFACTURING"
        else "NON_MANUFACTURING_ENV"
    )

    # ================= PLANT FILTER =================

    if plant_id and plant_id != "all":

        selected_plant = Plant.objects.filter(id=plant_id).first()

        entries = EnvironmentEntry.objects.filter(
            plant=selected_plant,
            year=year,
            report_type=report_type
        )

    else:

        selected_plant = None

        entries = EnvironmentEntry.objects.filter(
            year=year,
            report_type=report_type
        )

    # ================= DATA AGGREGATION =================

    data = {}

    for e in entries:

        if e.row_name not in data:

            data[e.row_name] = e

        else:

            existing = data[e.row_name]

            months = [
                "jan_qty","feb_qty","mar_qty",
                "apr_qty","may_qty","jun_qty",
                "jul_qty","aug_qty","sep_qty",
                "oct_qty","nov_qty","dec_qty"
            ]

            for m in months:
                setattr(existing, m, getattr(existing, m) + getattr(e, m))

            existing.total_quantity += e.total_quantity

    months = [
        "Jan","Feb","Mar","Apr","May","Jun",
        "Jul","Aug","Sep","Oct","Nov","Dec"
    ]

    def get_monthly(row_key):

        row = data.get(row_key)

        if not row:
            return [0]*12

        return [
            row.jan_qty,row.feb_qty,row.mar_qty,
            row.apr_qty,row.may_qty,row.jun_qty,
            row.jul_qty,row.aug_qty,row.sep_qty,
            row.oct_qty,row.nov_qty,row.dec_qty
        ]

    # ================= KPI =================

    if selected_type == "MANUFACTURING":

        water = data.get("total_water_intake")
        energy = data.get("electric_power_volume")
        cost = data.get("total_ERA_bill_cost")

    else:

        water = data.get("Non_total_kl")
        energy = data.get("Non_total_energy_power_volume")
        cost = data.get("Non_total_energy_power_cost")

    # ================= PLANT ENERGY COMPARISON =================

    plant_labels = []
    plant_energy = []
    plant_water = []

    for plant in user_plants:

        if selected_type == "MANUFACTURING":

            energy_row = "electric_power_volume"
            water_row = "total_water_intake"

        else:

            energy_row = "Non_total_energy_power_volume"
            water_row = "Non_total_kl"


        energy_entry = EnvironmentEntry.objects.filter(
            plant=plant,
            year=year,
            report_type=report_type,
            row_name=energy_row
        ).first()

        water_entry = EnvironmentEntry.objects.filter(
            plant=plant,
            year=year,
            report_type=report_type,
            row_name=water_row
        ).first()


        plant_labels.append(plant.name)

        plant_energy.append(
            energy_entry.total_quantity if energy_entry else 0
        )

        plant_water.append(
            water_entry.total_quantity if water_entry else 0
        )

    # ================= ENERGY SOURCE =================

    energy_sources = [

        data.get("disel_mobile_volume").total_quantity if data.get("disel_mobile_volume") else 0,

        data.get("disel_stationary_volume").total_quantity if data.get("disel_stationary_volume") else 0,

        data.get("electric_power_volume").total_quantity if data.get("electric_power_volume") else 0,

        data.get("natural_gas_volume").total_quantity if data.get("natural_gas_volume") else 0,

        data.get("renewable_energy_solar_used_volume").total_quantity if data.get("renewable_energy_solar_used_volume") else 0
    ]

    if selected_type == "MANUFACTURING":

        water_cost = data.get("total_mnm_water_cost")

        cost_data = [
            water_cost.total_quantity if water_cost else 0,
            cost.total_quantity if cost else 0
        ]

    else:

        water_cost = data.get("Non_water_cost_rs")

        cost_data = [
            water_cost.total_quantity if water_cost else 0,
            cost.total_quantity if cost else 0
        ]

    def r2(val):
        return round(val or 0, 2)

    context = {

        "user_plants": user_plants,
        "selected_plant": selected_plant,
        "selected_type": selected_type,

        "months": months,

        "kpi_water": r2(water.total_quantity if water else 0),
        "kpi_energy": r2(energy.total_quantity if energy else 0),
        "kpi_cost": r2(cost.total_quantity if cost else 0),

        "water_monthly": get_monthly(
            "total_water_intake"
            if selected_type=="MANUFACTURING"
            else "Non_total_kl"
        ),

        "energy_monthly": get_monthly(
            "electric_power_volume"
            if selected_type=="MANUFACTURING"
            else "Non_total_energy_power_volume"
        ),

        "energy_sources": energy_sources,
        "cost_data": cost_data,

        "plant_labels": plant_labels,
        "plant_energy": plant_energy,
        "plant_water": plant_water,

        "inlet_cod": get_monthly("inlet_effluent_cod"),
        "treated_cod": get_monthly("treated_effuent_tank_cod"),

        "inlet_bod": get_monthly("inlet_effluent_bod"),
        "treated_bod": get_monthly("treated_effuent_tank_bod"),
    }

    return render(
        request,
        "environmental_mis/environment_dashboard.html",
        context
    )
























from django.shortcuts import render
from django.utils import timezone
from apps.organizations.models import Plant
from .models import WasteSummary


def waste_dashboard(request):

    user_plants = Plant.objects.all()

    plant_id = request.GET.get("plant_id")
    waste_type = request.GET.get("waste_type", "MANUFACTURING")

    year = timezone.now().year


    # safer mapping
    report_map = {
        "MANUFACTURING": ["MANUFACTURING", "MANUFACTURING_WASTE"],
        "NON_MANUFACTURING": ["NON_MANUFACTURING", "NON_MANUFACTURING_WASTE"],
    }

    report_values = report_map.get(waste_type, ["MANUFACTURING"])


    if plant_id:
        selected_plant = Plant.objects.filter(id=plant_id).first()
    else:
        selected_plant = user_plants.first()


    summaries = WasteSummary.objects.filter(
        plant=selected_plant,
        report_type__in=report_values
    )


    summary_map = {s.summary_type: s for s in summaries}


    months = [
        "jan","feb","mar",
        "apr","may","jun",
        "jul","aug","sep",
        "oct","nov","dec"
    ]


    def monthly(summary_type):

        s = summary_map.get(summary_type)

        if not s:
            return [0]*12

        return [
            float(getattr(s, f"{m}_qty") or 0)
            for m in months
        ]


    def total(summary_type):

        s = summary_map.get(summary_type)

        if not s:
            return 0

        return float(s.total_quantity or 0)


    context = {

        "user_plants": user_plants,
        "selected_plant": selected_plant,
        "selected_type": waste_type,
        "year": year,

        "total_waste": total("GRAND_WASTE"),
        "nonhaz_total": total("NON_HAZ"),
        "haz_total": total("HAZ_PROCESS"),
        "ewaste_total": total("E_WASTE"),
        "diversion_total": total("DIVERSION_RATE"),

        "nonhaz_unit": total("NON_HAZ_UNIT"),
        "haz_unit": total("PROC_HAZ_UNIT"),

        "grand_data": monthly("GRAND_WASTE"),
        "nonhaz_data": monthly("NON_HAZ"),
        "haz_data": monthly("HAZ_PROCESS"),
        "ewaste_data": monthly("E_WASTE"),
        "diversion_data": monthly("DIVERSION_RATE"),
    }


    return render(
        request,
        "environmental_mis/waste_dashboard.html",
        context
    )