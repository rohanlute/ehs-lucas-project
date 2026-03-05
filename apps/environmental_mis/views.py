from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction

from apps.organizations.models import Plant
from apps.ENVdata.models import Unit

from .models import (
    BusinessType,
    Domain,
    Category,
    EnvironmentalMISQuarterlyData,
    SubCategory,
)

from .permissions import env_module_required, admin_env_required


# =========================================================
# BUSINESS TYPE
# =========================================================

@env_module_required
def business_type_list(request):
    # if not (request.user.is_superuser or request.user.is_staff or getattr(request.user, 'is_admin_user', False)):
    #     messages.error(request, "You don't have permission to access this page")
    #     return redirect("environmental_mis:business-types")
    
    search = request.GET.get("search", "")

    queryset = BusinessType.objects.all().order_by("name")

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "environmental_mis/business_type_list.html",
        {
            "page_obj": page_obj,
            "search": search,
        }
    )


@env_module_required
@admin_env_required
def business_type_create(request):

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not name:
            messages.error(request, "Name is required.")
            return redirect("environmental_mis:business_type_create")

        if BusinessType.objects.filter(name__iexact=name).exists():
            messages.error(request, "Business Type already exists.")
            return redirect("environmental_mis:business_type_create")

        BusinessType.objects.create(
            name=name,
            description=description,
            is_active=is_active,
            created_by=request.user
        )

        messages.success(request, "Business Type created successfully.")
        return redirect("environmental_mis:business_type_list")

    return render(request, "environmental_mis/business_type_form.html")


@env_module_required
@admin_env_required
def business_type_edit(request, pk):

    obj = get_object_or_404(BusinessType, pk=pk)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not name:
            messages.error(request, "Name is required.")
            return redirect("environmental_mis:business_type_edit", pk=pk)

        if BusinessType.objects.exclude(pk=pk).filter(name__iexact=name).exists():
            messages.error(request, "Business Type already exists.")
            return redirect("environmental_mis:business_type_edit", pk=pk)

        obj.name = name
        obj.description = description
        obj.is_active = is_active
        obj.save()

        messages.success(request, "Business Type updated successfully.")
        return redirect("environmental_mis:business_type_list")

    return render(
        request,
        "environmental_mis/business_type_form.html",
        {"obj": obj}
    )


@env_module_required
@admin_env_required
def business_type_delete(request, pk):
    obj = get_object_or_404(BusinessType, pk=pk)
    obj.delete()
    messages.success(request, "Business Type deleted successfully.")
    return redirect("environmental_mis:business_type_list")


# =========================================================
# CONFIGURATION
# =========================================================

@env_module_required
@admin_env_required
def configuration_list(request):

    categories = Category.objects.select_related(
        "domain",
        "domain__business_type",
    ).prefetch_related(
        "subcategories"
    ).order_by(
        "domain__business_type__name",
        "domain__name",
        "name"
    )

    return render(
        request,
        "environmental_mis/configuration_list.html",
        {"categories": categories}
    )

@env_module_required
@admin_env_required
def configuration_flow(request):

    business_types = BusinessType.objects.filter(is_active=True)
    print("business_types",business_types)

    if request.method == "POST":

        business_type_id = request.POST.get("business_type")
        domain_name = request.POST.get("domain_name", "").strip()

        if not business_type_id or not domain_name:
            messages.error(request, "Business Type and Domain are required.")
            return redirect("environmental_mis:configuration_flow")

        business_type = get_object_or_404(
            BusinessType,
            id=business_type_id,
            is_active=True
        )

        try:
            with transaction.atomic():

                # ===============================
                # CREATE / GET DOMAIN
                # ===============================
                domain, _ = Domain.objects.get_or_create(
                    business_type=business_type,
                    name=domain_name
                )

                category_count = int(request.POST.get("category_count", 0))

                if category_count == 0:
                    raise Exception("At least one Category is required.")

                # ===============================
                # LOOP CATEGORIES
                # ===============================
                for i in range(category_count):

                    category_name = request.POST.get(
                        f"category_name_{i}", ""
                    ).strip()

                    if not category_name:
                        raise Exception("Category name cannot be empty.")

                    category, _ = Category.objects.get_or_create(
                        domain=domain,
                        name=category_name
                    )

                    # ===============================
                    # SUBCATEGORY (OPTIONAL)
                    # ===============================
                    sub_count = int(
                        request.POST.get(f"subcategory_count_{i}", 0)
                    )

                    for j in range(sub_count):

                        sub_name = request.POST.get(
                            f"category_{i}_subcategory_{j}", ""
                        ).strip()

                        if not sub_name:
                            continue  # skip empty subcategory

                        if SubCategory.objects.filter(
                            category=category,
                            name=sub_name
                        ).exists():
                            raise Exception(
                                f"Already exists: "
                                f"{domain.name} → {category.name} → {sub_name}"
                            )

                        SubCategory.objects.create(
                            category=category,
                            name=sub_name
                        )

            messages.success(request, "Configuration saved successfully.")
            return redirect("environmental_mis:configuration_flow")

        except Exception as e:
            messages.error(request, str(e))
            return redirect("environmental_mis:configuration_flow")

    return render(
        request,
        "environmental_mis/configuration_flow.html",
        {"business_types": business_types}
    )


# =========================================================
# DASHBOARD
# =========================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import JsonResponse

from .models import (
    EnvironmentalMISReportConfig,
    Domain,
    Category,
    SubCategory
)
from apps.ENVdata.models import Unit
from .permissions import env_module_required, admin_env_required


# =====================================================
# LIST
# =====================================================

from collections import OrderedDict

@env_module_required
@admin_env_required
def report_config_list(request):

    configs = EnvironmentalMISReportConfig.objects.select_related(
        "business_type",
        "domain",
        "category",
        "subcategory",
        "unit"
    ).order_by(
        "business_type__name",
        "domain__name",
        "category__name",
        "subcategory__name",
        "order"
    )

    grouped_data = OrderedDict()

    for obj in configs:

        group_key = (
            obj.business_type.name,
            obj.domain.name,
            obj.category.name,
            obj.subcategory.name if obj.subcategory else None
        )
        print(group_key)


        if group_key not in grouped_data:
            grouped_data[group_key] = []

        grouped_data[group_key].append(obj)

    return render(
        request,
        "environmental_mis/report_config_list.html",
        {"grouped_data": grouped_data}
    )

# =====================================================
# CREATE
# =====================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Max
from django.http import JsonResponse
from .models import (
    EnvironmentalMISReportConfig,
    Domain,
    Category,
    SubCategory
)
from apps.ENVdata.models import Unit
from .permissions import env_module_required, admin_env_required


@env_module_required
@admin_env_required
def report_config_create(request):

    domains = Domain.objects.select_related(
        "business_type"
    ).filter(
        is_active=True,
        business_type__is_active=True
    ).order_by(
        "business_type__name",
        "name"
    )

    if request.method == "POST":

        domain_id = request.POST.get("domain")
        category_id = request.POST.get("category")
        subcategory_id = request.POST.get("subcategory")

        questions = request.POST.getlist("question_text[]")
        units = request.POST.getlist("unit_id[]")

        if not domain_id or not category_id:
            messages.error(request, "Domain and Category are required.")
            return redirect("environmental_mis:report_config_create")

        if not questions:
            messages.error(request, "At least one question is required.")
            return redirect("environmental_mis:report_config_create")

        domain = get_object_or_404(Domain, id=domain_id)
        business_type = domain.business_type

        max_order = EnvironmentalMISReportConfig.objects.filter(
            domain=domain,
            category_id=category_id
        ).aggregate(Max("order"))["order__max"] or 0

        order_counter = max_order + 1

        for q_text, unit_id in zip(questions, units):

            if q_text.strip() and unit_id:

                EnvironmentalMISReportConfig.objects.create(
                    business_type=business_type,
                    domain=domain,
                    category_id=category_id,
                    subcategory_id=subcategory_id if subcategory_id else None,
                    question_text=q_text.strip(),
                    unit_id=unit_id,
                    order=order_counter,
                    created_by=request.user
                )

                order_counter += 1

        messages.success(request, "Report configuration created successfully.")
        return redirect("environmental_mis:report_config_list")

    return render(
        request,
        "environmental_mis/report_config_form.html",
        {"domains": domains}
    )


# =====================================================
# EDIT
# =====================================================
@env_module_required
@admin_env_required
def report_config_edit(request, pk):

    config = get_object_or_404(EnvironmentalMISReportConfig, pk=pk)

    configs = EnvironmentalMISReportConfig.objects.filter(
        business_type=config.business_type,
        domain=config.domain,
        category=config.category,
        subcategory=config.subcategory
    ).order_by("order")

    domains = Domain.objects.select_related(
        "business_type"
    ).filter(
        is_active=True,
        business_type__is_active=True
    ).order_by(
        "business_type__name",
        "name"
    )

    if request.method == "POST":

        domain_id = request.POST.get("domain")
        category_id = request.POST.get("category")
        subcategory_id = request.POST.get("subcategory")

        questions = request.POST.getlist("question_text[]")
        units = request.POST.getlist("unit_id[]")

        domain = get_object_or_404(Domain, id=domain_id)
        business_type = domain.business_type

        # Existing configs
        existing_configs = list(configs)

        order_counter = 1

        for i, (q_text, unit_id) in enumerate(zip(questions, units)):

            if not q_text.strip() or not unit_id:
                continue

            if i < len(existing_configs):

                # UPDATE existing
                obj = existing_configs[i]
                obj.question_text = q_text.strip()
                obj.unit_id = unit_id
                obj.order = order_counter
                obj.save()

            else:

                # CREATE new
                EnvironmentalMISReportConfig.objects.create(
                    business_type=business_type,
                    domain=domain,
                    category_id=category_id,
                    subcategory_id=subcategory_id if subcategory_id else None,
                    question_text=q_text.strip(),
                    unit_id=unit_id,
                    order=order_counter,
                    created_by=request.user
                )

            order_counter += 1

        # DELETE removed configs
        if len(existing_configs) > len(questions):

            for obj in existing_configs[len(questions):]:
                obj.delete()

        messages.success(request, "Report configuration updated.")
        return redirect("environmental_mis:report_config_list")

    return render(
        request,
        "environmental_mis/report_config_form.html",
        {
            "domains": domains,
            "configs": configs,
            "edit_mode": True
        }
    )


# =====================================================
# DELETE
# =====================================================

@env_module_required
@admin_env_required
def report_config_delete(request, pk):

    config = get_object_or_404(EnvironmentalMISReportConfig, pk=pk)
    config.delete()

    messages.success(request, "Report configuration deleted.")
    return redirect("environmental_mis:report_config_list")


# =====================================================
# AJAX
# =====================================================

def load_report_domains(request):

    business_type_id = request.GET.get("business_type")

    domains = Domain.objects.filter(
        business_type_id=business_type_id,
        is_active=True
    ).values("id", "name")

    return JsonResponse(list(domains), safe=False)


def load_report_categories(request):

    domain_id = request.GET.get("domain")

    categories = Category.objects.filter(
        domain_id=domain_id,
        is_active=True
    ).values("id", "name")

    return JsonResponse(list(categories), safe=False)



def load_report_subcategories(request):

    category_id = request.GET.get("category")

    subcategories = SubCategory.objects.filter(
        category_id=category_id,
        is_active=True
    ).values("id", "name")

    return JsonResponse(list(subcategories), safe=False)


def load_report_units(request):

    units = Unit.objects.filter(is_active=True).values("id", "name")
    return JsonResponse(list(units), safe=False)

















from collections import defaultdict
from django.shortcuts import render
from .models import BusinessType, Domain, EnvironmentalMISReportConfig
from .permissions import env_module_required


@env_module_required
def manufacturing_environment_report(request):

    business_type = BusinessType.objects.filter(
        name__iexact="Manufacturing",
        is_active=True
    ).first()

    domain = Domain.objects.filter(
        business_type=business_type,
        name__iexact="Environment",
        is_active=True
    ).first()

    configs = EnvironmentalMISReportConfig.objects.select_related(
        "category",
        "subcategory",
        "unit",
        "unit__category"
    ).filter(
        business_type=business_type,
        domain=domain,
        is_active=True
    ).order_by(
        "category__name",
        "subcategory__name",
        "order"
    )

    grouped = defaultdict(lambda: defaultdict(list))

    for obj in configs:
        grouped[obj.category.name][
            obj.subcategory.name if obj.subcategory else ""
        ].append(obj)

    report_rows = []

    for category, subcats in grouped.items():

        category_total_rows = sum(len(qs) + 2 for qs in subcats.values())
        category_first = True

        for subcat, questions in subcats.items():

            subcat_total_rows = len(questions) + 2
            subcat_first = True

            # Normal question rows
            for q in questions:

                report_rows.append({
                    "id": q.id,
                    "category": category,
                    "category_rowspan": category_total_rows if category_first else 0,
                    "subcategory": subcat,
                    "subcategory_rowspan": subcat_total_rows if subcat_first else 0,
                    "question": q.question_text,
                    "unit_category": q.unit.category.name if q.unit.category else "",
                    "unit": q.unit.name,
                    "is_total": False,
                    "group_key": f"{category}_{subcat}"
                })

                category_first = False
                subcat_first = False

            # TOTAL ROW (Volume)
            report_rows.append({
                "id": f"total_{category}_{subcat}",
                "category": "",
                "category_rowspan": 0,
                "subcategory": "",
                "subcategory_rowspan": 0,
                "question": f"TOTAL ( KL ) - {category}",
                "unit_category": "Volume",
                "unit": "kiloliters",
                "is_total": True,
                "group_key": f"{category}_{subcat}"
            })

            # COST ROW
            report_rows.append({
                "id": f"cost_{category}_{subcat}",
                "category": "",
                "category_rowspan": 0,
                "subcategory": "",
                "subcategory_rowspan": 0,
                "question": "",
                "unit_category": "Cost",
                "unit": "₹ (INR)",
                "is_total": True,
                "group_key": f"{category}_{subcat}"
            })

    months = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]

    return render(
        request,
        "environmental_mis/manufacturing_environment_report.html",
        {
            "report_rows": report_rows,
            "months": months
        }
    )





# 
from collections import defaultdict
from django.shortcuts import render
from django.utils import timezone
from .models import BusinessType, Domain, EnvironmentalMISReportConfig
from apps.organizations.models import Plant
from .permissions import env_module_required
from collections import defaultdict
from django.utils import timezone
from django.shortcuts import render

@env_module_required
def manufacturing_waste_report(request):

    current_year = timezone.now().year
    selected_plant = Plant.objects.first()

    business_type = BusinessType.objects.filter(
        name__iexact="Manufacturing",
        is_active=True
    ).first()

    domain = Domain.objects.filter(
        business_type=business_type,
        name__iexact="Waste",
        is_active=True
    ).first()

    configs = EnvironmentalMISReportConfig.objects.select_related(
        "category","unit","subcategory"
    ).filter(
        business_type=business_type,
        domain=domain,
        is_active=True
    ).order_by("category__name","order")

    existing_data = EnvironmentalMISQuarterlyData.objects.filter(
        plant=selected_plant,
        year=current_year
    )

    # Map by report_config first
    config_map = {
        obj.report_config_id: obj for obj in existing_data
    }

    # fallback map using category + question_text
    fallback_map = {
        (
            obj.category_id,
            (obj.question_text or "").strip().lower()
        ): obj
        for obj in existing_data
    }

    grouped = defaultdict(list)

    for obj in configs:
        grouped[obj.category.name].append(obj)

    report_rows=[]
    sl_no=1

    for category,questions in grouped.items():

        first=True

        for q in questions:

            # try config id match
            saved=config_map.get(q.id)

            # fallback match if config changed
            if not saved:

                key=(
                    q.category_id,
                    q.question_text.strip().lower()
                )

                saved=fallback_map.get(key)

            report_rows.append({

                "sl_no":sl_no if first else "",
                "category":category if first else "",
                "config_id":q.id,
                "scrap":q.question_text,
                "unit":q.unit.name if q.unit else "",
                "saved":saved,
                "is_total":False

            })

            first=False

        # total row
        report_rows.append({

            "sl_no":"",
            "category":"",
            "config_id":None,
            "scrap":"TOTAL QUANTITY",
            "unit":"",
            "saved":None,
            "is_total":True

        })

        sl_no+=1

    return render(
        request,
        "environmental_mis/manufacturing_waste_report.html",
        {
            "report_rows":report_rows,
            "selected_plant":selected_plant,
            "current_year":current_year
        }
    )



import json
from decimal import Decimal
from django.http import JsonResponse
from django.utils import timezone

@env_module_required
def save_manufacturing_waste(request):

    if request.method=="POST":

        data=json.loads(request.body)

        plant=Plant.objects.first()
        year=timezone.now().year

        for row in data:

            config_id=row.get("config_id")

            if not config_id:
                continue

            config=EnvironmentalMISReportConfig.objects.get(id=config_id)

            question_text=config.question_text

            jan_qty=Decimal(str(row.get("jan_qty",0)))
            feb_qty=Decimal(str(row.get("feb_qty",0)))
            mar_qty=Decimal(str(row.get("mar_qty",0)))

            apr_qty=Decimal(str(row.get("apr_qty",0)))
            may_qty=Decimal(str(row.get("may_qty",0)))
            jun_qty=Decimal(str(row.get("jun_qty",0)))

            jul_qty=Decimal(str(row.get("jul_qty",0)))
            aug_qty=Decimal(str(row.get("aug_qty",0)))
            sep_qty=Decimal(str(row.get("sep_qty",0)))

            oct_qty=Decimal(str(row.get("oct_qty",0)))
            nov_qty=Decimal(str(row.get("nov_qty",0)))
            dec_qty=Decimal(str(row.get("dec_qty",0)))

            jan_cost=Decimal(str(row.get("jan_cost",0)))
            feb_cost=Decimal(str(row.get("feb_cost",0)))
            mar_cost=Decimal(str(row.get("mar_cost",0)))

            apr_cost=Decimal(str(row.get("apr_cost",0)))
            may_cost=Decimal(str(row.get("may_cost",0)))
            jun_cost=Decimal(str(row.get("jun_cost",0)))

            jul_cost=Decimal(str(row.get("jul_cost",0)))
            aug_cost=Decimal(str(row.get("aug_cost",0)))
            sep_cost=Decimal(str(row.get("sep_cost",0)))

            oct_cost=Decimal(str(row.get("oct_cost",0)))
            nov_cost=Decimal(str(row.get("nov_cost",0)))
            dec_cost=Decimal(str(row.get("dec_cost",0)))

            q1_qty=jan_qty+feb_qty+mar_qty
            q2_qty=apr_qty+may_qty+jun_qty
            q3_qty=jul_qty+aug_qty+sep_qty
            q4_qty=oct_qty+nov_qty+dec_qty

            q1_cost=jan_cost+feb_cost+mar_cost
            q2_cost=apr_cost+may_cost+jun_cost
            q3_cost=jul_cost+aug_cost+sep_cost
            q4_cost=oct_cost+nov_cost+dec_cost

            total_qty=q1_qty+q2_qty+q3_qty+q4_qty
            total_cost=q1_cost+q2_cost+q3_cost+q4_cost

            EnvironmentalMISQuarterlyData.objects.update_or_create(

                plant=plant,
                year=year,
                report_config=config,

                defaults={

                    "question_text":question_text,

                    "business_type":config.business_type,
                    "domain":config.domain,
                    "category":config.category,
                    "subcategory":config.subcategory,
                    "unit":config.unit,

                    "part_code":row.get("part_code"),
                    "treatment":row.get("treatment"),

                    "jan_qty":jan_qty,
                    "feb_qty":feb_qty,
                    "mar_qty":mar_qty,

                    "apr_qty":apr_qty,
                    "may_qty":may_qty,
                    "jun_qty":jun_qty,

                    "jul_qty":jul_qty,
                    "aug_qty":aug_qty,
                    "sep_qty":sep_qty,

                    "oct_qty":oct_qty,
                    "nov_qty":nov_qty,
                    "dec_qty":dec_qty,

                    "jan_cost":jan_cost,
                    "feb_cost":feb_cost,
                    "mar_cost":mar_cost,

                    "apr_cost":apr_cost,
                    "may_cost":may_cost,
                    "jun_cost":jun_cost,

                    "jul_cost":jul_cost,
                    "aug_cost":aug_cost,
                    "sep_cost":sep_cost,

                    "oct_cost":oct_cost,
                    "nov_cost":nov_cost,
                    "dec_cost":dec_cost,

                    "q1_quantity":q1_qty,
                    "q2_quantity":q2_qty,
                    "q3_quantity":q3_qty,
                    "q4_quantity":q4_qty,

                    "q1_cost":q1_cost,
                    "q2_cost":q2_cost,
                    "q3_cost":q3_cost,
                    "q4_cost":q4_cost,

                    "total_quantity":total_qty,
                    "total_cost":total_cost
                }
            )

        return JsonResponse({"status":"success"})


@env_module_required
def non_manufacturing_waste_report(request):

    current_year = timezone.now().year
    selected_plant = Plant.objects.first()

    business_type = BusinessType.objects.filter(
        name__iexact="Non-Manufacturing",
        is_active=True
    ).first()

    domain = Domain.objects.filter(
        business_type=business_type,
        name__iexact="Waste",
        is_active=True
    ).first()

    configs = EnvironmentalMISReportConfig.objects.select_related(
        "category","unit","subcategory"
    ).filter(
        business_type=business_type,
        domain=domain,
        is_active=True
    ).order_by("category__name","order")

    existing_data = EnvironmentalMISQuarterlyData.objects.filter(
        plant=selected_plant,
        year=current_year
    )

    config_map = {
        obj.report_config_id: obj for obj in existing_data
    }

    grouped = defaultdict(list)

    for obj in configs:
        grouped[obj.category.name].append(obj)

    report_rows = []
    sl_no = 1

    for category, questions in grouped.items():

        first = True

        for q in questions:

            saved = config_map.get(q.id)

            report_rows.append({
                "sl_no": sl_no if first else "",
                "category": category if first else "",
                "config_id": q.id,
                "scrap": q.question_text,
                "unit": q.unit.name if q.unit else "",
                "saved": saved,
                "is_total": False
            })

            first = False

        report_rows.append({
            "sl_no": "",
            "category": "",
            "config_id": None,
            "scrap": "TOTAL QUANTITY",
            "unit": "",
            "saved": None,
            "is_total": True
        })

        sl_no += 1

    return render(
        request,
        "environmental_mis/non_manufacturing_waste_report.html",
        {
            "report_rows": report_rows,
            "selected_plant": selected_plant,
            "current_year": current_year
        }
    )
