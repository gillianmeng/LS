from django.urls import path

from . import views

app_name = "shop"

urlpatterns = [
    path("training/<int:pk>/", views.training_detail, name="training_detail"),
    path("training/<int:pk>/register/", views.training_register, name="training_register"),
    path("center/", views.activity_center, name="activity_center"),
    path("applications/", views.my_applications, name="my_applications"),
    path("mall/", views.points_mall, name="points_mall"),
    path("mall/cart/", views.mall_cart, name="mall_cart"),
    path("mall/cart/add/", views.mall_cart_add, name="mall_cart_add"),
    path("mall/cart/line/", views.mall_cart_update, name="mall_cart_update"),
    path("mall/checkout/<int:product_id>/", views.mall_checkout, name="mall_checkout"),
    path("mall/orders/", views.my_orders, name="my_orders"),
    path("mall/orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("mall/orders/<int:pk>/cancel/", views.mall_order_cancel, name="mall_order_cancel"),
    path("mall/orders/<int:pk>/edit-address/", views.mall_order_edit_address, name="mall_order_edit_address"),
    path("mall/addresses/", views.mall_addresses, name="mall_addresses"),
    path("mall/addresses/<int:pk>/delete/", views.mall_address_delete, name="mall_address_delete"),
    path("mall/addresses/<int:pk>/default/", views.mall_address_set_default, name="mall_address_set_default"),
    path("mall/after-sales/", views.mall_after_sales, name="mall_after_sales"),
]
