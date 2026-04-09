"""积分商城购物车：存于 session，不落库。"""

SESSION_KEY = "points_mall_cart"


def get_cart(request) -> dict[str, int]:
    raw = request.session.get(SESSION_KEY) or {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        try:
            q = int(v)
            if q > 0:
                out[str(k)] = q
        except (TypeError, ValueError):
            continue
    return out


def save_cart(request, cart: dict[str, int]) -> None:
    request.session[SESSION_KEY] = {k: v for k, v in cart.items() if v > 0}
    request.session.modified = True


def cart_total_quantity(request) -> int:
    return sum(get_cart(request).values())


def add_product(request, product_id: int, *, stock: int, delta: int = 1) -> int:
    """增加数量，不超过库存；返回该商品在购物车中的数量。"""
    if stock < 1 or delta < 1:
        return get_cart(request).get(str(product_id), 0)
    cart = get_cart(request)
    key = str(product_id)
    current = cart.get(key, 0)
    new_qty = min(stock, current + delta)
    cart[key] = new_qty
    save_cart(request, cart)
    return new_qty


def set_quantity(request, product_id: int, quantity: int, *, stock: int) -> None:
    cart = get_cart(request)
    key = str(product_id)
    q = max(0, min(int(quantity), stock))
    if q == 0:
        cart.pop(key, None)
    else:
        cart[key] = q
    save_cart(request, cart)


def remove_product(request, product_id: int) -> None:
    cart = get_cart(request)
    cart.pop(str(product_id), None)
    save_cart(request, cart)


def line_points_total(request, products_by_id: dict) -> int:
    """根据已取出的 Product 映射计算购物车积分合计。"""
    total = 0
    for pid_str, qty in get_cart(request).items():
        p = products_by_id.get(int(pid_str))
        if p and qty > 0:
            total += int(p.points_cost) * qty
    return total
