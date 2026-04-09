from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from . import cart_session
from .forms import MallCheckoutForm, MallShippingAddressForm
from .models import (
    MallOrder,
    MallShippingAddress,
    Product,
    Training,
    TrainingRegistration,
    generate_mall_order_no,
    get_default_pickup_instruction,
    get_points_earn_rules_display,
)

User = get_user_model()

_JOINED_TABS = frozenset(("joined", "not_joined"))

_MY_APP_CATEGORY_TABS = frozenset(c.value for c in Training.ApplicationsCategory)


def _training_public_order(qs):
    return qs.order_by(
        "sort_order",
        F("start_at").desc(nulls_last=True),
        "-created_at",
    )


@login_required
def activity_center(request):
    """活动广场：仅培训展示 + 跳转详情报名（无其它活动分类 Tab）。"""
    qs = _training_public_order(Training.objects.filter(is_published=True))
    q = request.GET.get("q", "").strip()
    activity_status = request.GET.get("status", "").strip()
    start_date = request.GET.get("start", "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(summary__icontains=q)
            | Q(location__icontains=q)
            | Q(instructor_name__icontains=q)
            | Q(schedule_note__icontains=q)
        )

    now = timezone.now()
    # 与 Training.schedule_status 一致，并兼容「仅填时间安排说明、无开始时间」的记录
    _not_ended = Q(end_at__isnull=True) | Q(end_at__gte=now)
    if activity_status == "not_started":
        qs = qs.filter(start_at__gt=now)
    elif activity_status == "ongoing":
        qs = qs.filter(
            (Q(start_at__isnull=True) & _not_ended)
            | (Q(start_at__lte=now) & _not_ended)
        )
    elif activity_status == "ended":
        qs = qs.filter(end_at__lt=now)

    if start_date:
        try:
            from datetime import datetime

            datetime.strptime(start_date, "%Y-%m-%d")
            # 无固定开始时间的活动仍保留在结果中，避免一选日期就只剩空列表
            qs = qs.filter(
                Q(start_at__isnull=True) | Q(start_at__date__gte=start_date)
            )
        except ValueError:
            pass

    training_list = list(qs)

    pending_training_ids = frozenset()
    approved_training_ids = frozenset()
    if request.user.is_authenticated and training_list:
        tids = [t.pk for t in training_list]
        _pending = set()
        _approved = set()
        for tid, st in TrainingRegistration.objects.filter(
            employee=request.user,
            training_id__in=tids,
            status__in=(
                TrainingRegistration.Status.PENDING,
                TrainingRegistration.Status.APPROVED,
            ),
        ).values_list("training_id", "status"):
            if st == TrainingRegistration.Status.PENDING:
                _pending.add(tid)
            elif st == TrainingRegistration.Status.APPROVED:
                _approved.add(tid)
        pending_training_ids = frozenset(_pending)
        approved_training_ids = frozenset(_approved)

    return render(
        request,
        "shop/activity_center.html",
        {
            "search_q": q,
            "activity_status": activity_status,
            "start_date": start_date,
            "training_list": training_list,
            "pending_training_ids": pending_training_ids,
            "approved_training_ids": approved_training_ids,
        },
    )


@login_required
def training_detail(request, pk):
    published = Training.objects.filter(is_published=True)
    if request.user.is_authenticated and TrainingRegistration.objects.filter(
        training_id=pk, employee_id=request.user.pk
    ).exists():
        training = get_object_or_404(Training.objects.all(), pk=pk)
    else:
        training = get_object_or_404(published, pk=pk)
    my_registration = None
    if request.user.is_authenticated:
        my_registration = TrainingRegistration.objects.filter(
            training=training, employee=request.user
        ).first()
    return render(
        request,
        "shop/training_detail.html",
        {
            "training": training,
            "my_registration": my_registration,
        },
    )


@login_required
@require_POST
def training_register(request, pk):
    training = get_object_or_404(Training.objects.filter(is_published=True), pk=pk)
    detail = redirect("shop:training_detail", pk=pk)

    if not training.registration_is_open():
        messages.error(request, "当前不可报名（已截止或活动已结束）。")
        return detail
    if not training.has_capacity():
        messages.error(request, "报名名额已满。")
        return detail

    msg = (request.POST.get("message") or "").strip()[:300]

    existing = TrainingRegistration.objects.filter(
        training=training, employee=request.user
    ).first()
    if existing:
        if existing.status in (
            TrainingRegistration.Status.REJECTED,
            TrainingRegistration.Status.CANCELLED,
        ):
            existing.status = TrainingRegistration.Status.PENDING
            existing.message = msg
            existing.admin_note = ""
            existing.save(update_fields=["status", "message", "admin_note", "updated_at"])
            messages.success(request, "已重新提交报名。")
        else:
            messages.info(request, "您已报名，请勿重复提交。")
        return detail

    TrainingRegistration.objects.create(
        training=training,
        employee=request.user,
        message=msg,
        status=TrainingRegistration.Status.PENDING,
    )
    messages.success(request, "报名已提交，请等待审核。")
    return detail


@login_required
def my_applications(request):
    """我的报名：按后台「我的报名中的类型」筛选；已加入 = 审核通过，未加入 = 待审核/拒绝/取消。"""
    joined_tab = request.GET.get("joined", "joined")
    if joined_tab not in _JOINED_TABS:
        joined_tab = "joined"
    category = request.GET.get("category", Training.ApplicationsCategory.TRAINING.value)
    if category not in _MY_APP_CATEGORY_TABS:
        category = Training.ApplicationsCategory.TRAINING.value
    view_mode = request.GET.get("view", "grid")
    if view_mode not in ("grid", "list"):
        view_mode = "grid"

    qs = TrainingRegistration.objects.filter(employee=request.user).select_related("training")
    qs = qs.filter(training__applications_category=category)

    if joined_tab == "joined":
        qs = qs.filter(status=TrainingRegistration.Status.APPROVED)
    else:
        qs = qs.exclude(status=TrainingRegistration.Status.APPROVED)

    search_q = request.GET.get("q", "").strip()
    if search_q:
        qs = qs.filter(
            Q(training__title__icontains=search_q)
            | Q(training__summary__icontains=search_q)
        )

    application_list = qs.order_by("-updated_at")

    return render(
        request,
        "shop/my_applications.html",
        {
            "joined_tab": joined_tab,
            "app_category": category,
            "participation": request.GET.get("participation", ""),
            "search_q": search_q,
            "view_mode": view_mode,
            "application_list": application_list,
        },
    )


@login_required
def points_mall(request):
    qs = Product.objects.annotate(redeemed_count=Count("mall_orders", distinct=True))
    search_q = request.GET.get("q", "").strip()
    affordable = request.GET.get("affordable") == "1"
    sort_key = request.GET.get("sort", "")

    if search_q:
        qs = qs.filter(name__icontains=search_q)

    if affordable and request.user.is_authenticated:
        qs = qs.filter(points_cost__lte=request.user.points_balance)

    if sort_key == "points_asc":
        qs = qs.order_by("points_cost", "id")
    elif sort_key == "points_desc":
        qs = qs.order_by("-points_cost", "id")
    else:
        qs = qs.order_by("-id")

    order_count = 0
    if request.user.is_authenticated:
        order_count = request.user.mall_orders.count()

    cart_total_qty = cart_session.cart_total_quantity(request)
    cart_map = cart_session.get_cart(request)
    products_list = list(qs)
    for p in products_list:
        setattr(p, "cart_qty", cart_map.get(str(p.pk), 0))

    rules_text = get_points_earn_rules_display()
    points_earn_rule_lines = [ln.strip() for ln in rules_text.splitlines() if ln.strip()]

    return render(
        request,
        "shop/points_mall.html",
        {
            "products": products_list,
            "search_q": search_q,
            "affordable_only": affordable,
            "sort_key": sort_key,
            "order_count": order_count,
            "cart_total_qty": cart_total_qty,
            "points_earn_rule_lines": points_earn_rule_lines,
        },
    )


def _decrement_mall_cart_for_product(request, product_id: int, current_stock: int) -> None:
    cart = cart_session.get_cart(request)
    q = cart.get(str(product_id), 0)
    if q > 0:
        cart_session.set_quantity(request, product_id, q - 1, stock=current_stock)


def _sync_default_shipping_address(employee, name: str, phone: str, address_detail: str) -> None:
    existing = MallShippingAddress.objects.filter(employee=employee, is_default=True).first()
    if existing:
        existing.recipient_name = name[:50] if name else existing.recipient_name
        existing.recipient_phone = phone[:20] if phone else existing.recipient_phone
        existing.address_detail = address_detail
        existing.save(update_fields=["recipient_name", "recipient_phone", "address_detail", "updated_at"])
    else:
        MallShippingAddress.objects.create(
            employee=employee,
            recipient_name=name[:50] or "—",
            recipient_phone=phone[:20] or "—",
            address_detail=address_detail,
            is_default=True,
        )


@login_required
@require_http_methods(["GET", "POST"])
def mall_checkout(request, product_id):
    """兑换结算：填写地址 / 领取方式，提交后扣积分与库存。"""
    product = get_object_or_404(Product, pk=product_id)
    cost = product.points_cost

    def _return_params():
        rq = request.GET.get("return_q", "").strip() or request.POST.get("return_q", "").strip()
        ra = request.GET.get("return_affordable", "") or request.POST.get("return_affordable", "")
        rs = request.GET.get("return_sort", "").strip() or request.POST.get("return_sort", "").strip()
        return rq, ra, rs

    return_q, return_affordable, return_sort = _return_params()

    checkout_initial = {}
    if request.method != "POST":
        da = MallShippingAddress.objects.filter(employee=request.user, is_default=True).first()
        if da:
            checkout_initial = {
                "recipient_name": da.recipient_name,
                "recipient_phone": da.recipient_phone,
                "address_detail": da.address_detail,
            }

    if request.method == "GET":
        if product.stock < 1:
            messages.error(request, "该商品已售罄。")
            return redirect(_mall_url(return_q, return_affordable, return_sort))
        if request.user.points_balance < cost:
            messages.error(request, f"积分不足，需要 {cost} 分。")
            return redirect(_mall_url(return_q, return_affordable, return_sort))

    if request.method == "POST":
        form = MallCheckoutForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    locked_product = Product.objects.select_for_update().get(pk=product.pk)
                    locked_user = User.objects.select_for_update().get(pk=request.user.pk)
                    if locked_product.stock < 1:
                        messages.error(request, "该商品已售罄，请返回商城。")
                        return redirect(_mall_url(return_q, return_affordable, return_sort))
                    if locked_user.points_balance < cost:
                        messages.error(request, f"积分不足，需要 {cost} 分。")
                        return redirect(_mall_url(return_q, return_affordable, return_sort))

                    cd = form.cleaned_data
                    dt = cd["delivery_type"]
                    order_no = generate_mall_order_no()
                    while MallOrder.objects.filter(order_no=order_no).exists():
                        order_no = generate_mall_order_no()

                    if dt == MallOrder.DeliveryType.PICKUP:
                        status = MallOrder.OrderStatus.PICKUP_READY
                        pickup_note = (cd.get("pickup_location_note") or "").strip() or get_default_pickup_instruction()
                        addr = ""
                        rec_name = (cd.get("recipient_name") or "").strip()
                        rec_phone = (cd.get("recipient_phone") or "").strip()
                    else:
                        status = MallOrder.OrderStatus.SUBMITTED
                        pickup_note = ""
                        addr = (cd.get("address_detail") or "").strip()
                        rec_name = (cd.get("recipient_name") or "").strip()
                        rec_phone = (cd.get("recipient_phone") or "").strip()

                    order = MallOrder.objects.create(
                        order_no=order_no,
                        employee=locked_user,
                        product=locked_product,
                        product_name=locked_product.name,
                        points_spent=cost,
                        status=status,
                        delivery_type=dt,
                        recipient_name=rec_name,
                        recipient_phone=rec_phone,
                        address_detail=addr,
                        pickup_location_note=pickup_note,
                        buyer_remark=(cd.get("buyer_remark") or "").strip(),
                    )

                    locked_product.stock -= 1
                    locked_product.save(update_fields=["stock"])
                    locked_user.points_balance -= cost
                    locked_user.save(update_fields=["points_balance"])
            except Product.DoesNotExist:
                raise Http404 from None

            p_stock = Product.objects.only("stock").get(pk=product.pk).stock
            _decrement_mall_cart_for_product(request, product.pk, p_stock)
            cd = form.cleaned_data
            if (
                cd.get("save_address")
                and cd["delivery_type"] == MallOrder.DeliveryType.MAIL
                and (cd.get("address_detail") or "").strip()
            ):
                _sync_default_shipping_address(
                    request.user,
                    (cd.get("recipient_name") or "").strip(),
                    (cd.get("recipient_phone") or "").strip(),
                    (cd.get("address_detail") or "").strip(),
                )

            messages.success(
                request,
                f"订单已提交，订单号 {order.order_no}，已扣除 {cost} 积分。",
            )
            return redirect("shop:order_detail", pk=order.pk)

        mall_back = _mall_url(return_q, return_affordable, return_sort)
    else:
        form = MallCheckoutForm(initial=checkout_initial)
        mall_back = _mall_url(return_q, return_affordable, return_sort)

    return render(
        request,
        "shop/mall_checkout.html",
        {
            "form": form,
            "product": product,
            "points_cost": cost,
            "mall_back": mall_back,
            "return_q": return_q,
            "return_affordable": return_affordable,
            "return_sort": return_sort,
            "default_pickup_hint": get_default_pickup_instruction(),
        },
    )


def _mall_url(q: str, affordable: str, sort_key: str) -> str:
    from urllib.parse import urlencode

    query = {}
    if q:
        query["q"] = q
    if affordable == "1":
        query["affordable"] = "1"
    if sort_key:
        query["sort"] = sort_key
    base = reverse("shop:points_mall")
    if query:
        return f"{base}?{urlencode(query)}"
    return base


def _safe_redirect_path(request, candidate: str) -> str:
    if candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return reverse("shop:points_mall")


@login_required
@require_POST
def mall_cart_add(request):
    raw_next = (request.POST.get("next") or "").strip()
    next_url = _safe_redirect_path(request, raw_next)
    try:
        product_id = int(request.POST.get("product_id", ""))
    except (TypeError, ValueError):
        messages.error(request, "无效的商品。")
        return redirect(next_url)
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        messages.error(request, "商品不存在。")
        return redirect(next_url)
    if product.stock < 1:
        messages.warning(request, "该商品已售罄。")
        return redirect(next_url)
    new_qty = cart_session.add_product(request, product.pk, stock=product.stock, delta=1)
    messages.success(request, f"已将「{product.name}」加入购物车（共 {new_qty} 件）。")
    return redirect(next_url)


@login_required
def mall_cart(request):
    raw = cart_session.get_cart(request)
    ids = []
    for k in raw:
        try:
            ids.append(int(k))
        except (TypeError, ValueError):
            continue
    products_by_id = {p.pk: p for p in Product.objects.filter(pk__in=ids)} if ids else {}
    cleaned: dict[str, int] = {}
    lines = []
    for pid_str, qty in raw.items():
        try:
            pid = int(pid_str)
        except (TypeError, ValueError):
            continue
        p = products_by_id.get(pid)
        if not p or qty < 1:
            continue
        q = min(qty, max(0, p.stock))
        if q < 1:
            continue
        cleaned[str(pid)] = q
        lines.append(
            {
                "product": p,
                "qty": q,
                "line_points": p.points_cost * q,
            }
        )
    if cleaned != raw:
        cart_session.save_cart(request, cleaned)

    total_points = cart_session.line_points_total(request, products_by_id)
    return render(
        request,
        "shop/cart.html",
        {
            "lines": lines,
            "cart_total_qty": cart_session.cart_total_quantity(request),
            "cart_points_total": total_points,
        },
    )


@login_required
@require_POST
def mall_cart_update(request):
    try:
        product_id = int(request.POST.get("product_id", ""))
    except (TypeError, ValueError):
        messages.error(request, "无效的商品。")
        return redirect("shop:mall_cart")
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        messages.error(request, "商品不存在。")
        return redirect("shop:mall_cart")
    try:
        quantity = int(request.POST.get("quantity", "0"))
    except (TypeError, ValueError):
        quantity = 0
    cart_session.set_quantity(request, product_id, quantity, stock=product.stock)
    if quantity < 1:
        messages.info(request, "已从购物车移除。")
    else:
        messages.success(request, "已更新数量。")
    return redirect("shop:mall_cart")


@login_required
def my_orders(request):
    orders = request.user.mall_orders.select_related("product").order_by("-created_at")
    return render(
        request,
        "shop/my_orders.html",
        {"orders": orders},
    )


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        MallOrder.objects.select_related("product", "employee"),
        pk=pk,
        employee=request.user,
    )
    cancellable = order.status in (
        MallOrder.OrderStatus.SUBMITTED,
        MallOrder.OrderStatus.PROCESSING,
        MallOrder.OrderStatus.PICKUP_READY,
    )
    can_edit_address = (
        order.delivery_type == MallOrder.DeliveryType.MAIL
        and order.status == MallOrder.OrderStatus.SUBMITTED
    )
    return render(
        request,
        "shop/order_detail.html",
        {
            "order": order,
            "order_cancellable": cancellable,
            "order_can_edit_address": can_edit_address,
        },
    )


@login_required
def mall_addresses(request):
    addresses = MallShippingAddress.objects.filter(employee=request.user)
    if request.method == "POST":
        form = MallShippingAddressForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.employee = request.user
            obj.save()
            messages.success(request, "已保存地址。")
            return redirect("shop:mall_addresses")
    else:
        form = MallShippingAddressForm()
    return render(
        request,
        "shop/mall_addresses.html",
        {"addresses": addresses, "form": form},
    )


@login_required
@require_POST
def mall_address_delete(request, pk):
    addr = get_object_or_404(MallShippingAddress, pk=pk, employee=request.user)
    addr.delete()
    messages.info(request, "已删除该地址。")
    return redirect("shop:mall_addresses")


@login_required
@require_POST
def mall_address_set_default(request, pk):
    addr = get_object_or_404(MallShippingAddress, pk=pk, employee=request.user)
    addr.is_default = True
    addr.save()
    messages.success(request, "已设为默认收货地址。")
    return redirect("shop:mall_addresses")


@login_required
def mall_after_sales(request):
    orders = request.user.mall_orders.select_related("product").order_by("-created_at")[:100]
    return render(request, "shop/mall_after_sales.html", {"orders": orders})


@login_required
@require_POST
def mall_order_cancel(request, pk):
    order = get_object_or_404(MallOrder, pk=pk, employee=request.user)
    if order.status not in (
        MallOrder.OrderStatus.SUBMITTED,
        MallOrder.OrderStatus.PROCESSING,
        MallOrder.OrderStatus.PICKUP_READY,
    ):
        messages.error(request, "当前订单状态不可取消。")
        return redirect("shop:order_detail", pk=order.pk)
    try:
        with transaction.atomic():
            locked_o = MallOrder.objects.select_for_update().get(pk=order.pk, employee=request.user)
            if locked_o.status not in (
                MallOrder.OrderStatus.SUBMITTED,
                MallOrder.OrderStatus.PROCESSING,
                MallOrder.OrderStatus.PICKUP_READY,
            ):
                messages.error(request, "当前订单状态不可取消。")
                return redirect("shop:order_detail", pk=order.pk)
            prod = Product.objects.select_for_update().get(pk=locked_o.product_id)
            emp = User.objects.select_for_update().get(pk=request.user.pk)
            locked_o.status = MallOrder.OrderStatus.CANCELLED
            locked_o.save(update_fields=["status", "updated_at"])
            prod.stock += 1
            prod.save(update_fields=["stock"])
            emp.points_balance += locked_o.points_spent
            emp.save(update_fields=["points_balance"])
    except MallOrder.DoesNotExist:
        raise Http404 from None
    messages.success(request, f"订单已取消，已退回 {order.points_spent} 积分。")
    return redirect("shop:order_detail", pk=order.pk)


@login_required
@require_http_methods(["GET", "POST"])
def mall_order_edit_address(request, pk):
    order = get_object_or_404(
        MallOrder.objects.select_related("product"),
        pk=pk,
        employee=request.user,
    )
    if order.delivery_type != MallOrder.DeliveryType.MAIL:
        messages.error(request, "仅邮寄订单可修改收件信息。")
        return redirect("shop:order_detail", pk=order.pk)
    if order.status != MallOrder.OrderStatus.SUBMITTED:
        messages.error(request, "当前状态不可修改地址（已发货或已处理请联络管理员）。")
        return redirect("shop:order_detail", pk=order.pk)
    if request.method == "POST":
        name = (request.POST.get("recipient_name") or "").strip()
        phone = (request.POST.get("recipient_phone") or "").strip()
        addr = (request.POST.get("address_detail") or "").strip()
        if not name or not phone or not addr:
            messages.error(request, "请填写完整收件人、电话与地址。")
        else:
            order.recipient_name = name[:50]
            order.recipient_phone = phone[:20]
            order.address_detail = addr
            order.save(update_fields=["recipient_name", "recipient_phone", "address_detail", "updated_at"])
            _sync_default_shipping_address(request.user, name, phone, addr)
            messages.success(request, "收件信息已更新，并同步为默认收货地址。")
            return redirect("shop:order_detail", pk=order.pk)
    return render(
        request,
        "shop/mall_order_edit_address.html",
        {"order": order},
    )
