from django.db.models import F, Q
from django.shortcuts import render

from django.contrib.auth.decorators import login_required

from courses.models import Course
from courses.views import get_dashboard_context, get_public_home_context
from shop.models import Product, Training


def index(request):
    if request.user.is_authenticated:
        ctx = get_dashboard_context(request)
        ctx["trainings_featured"] = list(
            Training.objects.filter(is_published=True, is_home_featured=True)
            .order_by(
                "sort_order",
                F("start_at").desc(nulls_last=True),
                "-created_at",
            )[:6]
        )
    else:
        ctx = get_public_home_context(request)
        ctx["trainings_featured"] = []
    return render(request, "index.html", ctx)


@login_required
def global_search(request):
    """全站搜索：课程名称、积分商品名称。"""
    q = request.GET.get("q", "").strip()
    courses = []
    products = []
    if q:
        courses = list(
            Course.objects.filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(article_body__icontains=q)
            )[:40]
        )
        products = list(Product.objects.filter(name__icontains=q)[:40])
    return render(
        request,
        "search_results.html",
        {
            "search_q": q,
            "search_courses": courses,
            "search_products": products,
        },
    )
